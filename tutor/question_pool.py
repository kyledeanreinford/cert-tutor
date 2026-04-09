import json
import random
import threading
from pathlib import Path

from tutor.openai_client import OpenAIChatClient, OpenAIEmbedder
from tutor.prompter import build_all_explanations_prompt, build_question_prompt
from tutor.retriever import retrieve
from tutor.seed_questions import get_style_examples

POOL_SIZE = 20
INITIAL_BATCH = 5
REFILL_THRESHOLD = 10
REFILL_AMOUNT = 10


class QuestionPool:
    def __init__(
        self,
        pool_path: Path,
        chat_client: OpenAIChatClient,
        embedder: OpenAIEmbedder,
        chroma_dir: str,
        top_k: int,
        weak_spots: list[str],
        asked_questions: set[str] | None = None,
        difficulty: int = 2,
    ) -> None:
        self.pool_path = pool_path
        self.chat_client = chat_client
        self.embedder = embedder
        self.chroma_dir = chroma_dir
        self.top_k = top_k
        self.weak_spots = weak_spots
        self.asked_questions: set[str] = asked_questions or set()
        self.difficulty = difficulty
        self.questions: list[dict] = []
        self._lock = threading.Lock()
        self._refilling = False
        self._load()

    def _load(self) -> None:
        if self.pool_path.exists():
            self.questions = json.loads(self.pool_path.read_text())

    def _save(self) -> None:
        self.pool_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self.pool_path.write_text(json.dumps(self.questions, indent=2))

    def pop(self) -> dict | None:
        with self._lock:
            question = None
            fallback = None
            remaining = []
            for candidate in self.questions:
                if candidate["question"] in self.asked_questions:
                    continue
                if question is None and candidate.get("difficulty", 2) == self.difficulty:
                    question = candidate
                elif fallback is None:
                    fallback = candidate
                else:
                    remaining.append(candidate)
            picked = question or fallback
            if picked is None:
                self.questions = remaining
            else:
                self.questions = [
                    q for q in self.questions if q is not picked
                ]
        if picked is None:
            return None
        self._save()
        if len(self.questions) < REFILL_THRESHOLD and not self._refilling:
            self._refill_background(REFILL_AMOUNT)
        return picked

    def mark_asked(self, question_text: str) -> None:
        self.asked_questions.add(question_text)

    def count(self) -> int:
        return len(self.questions)

    def update_weak_spots(self, weak_spots: list[str]) -> None:
        self.weak_spots = weak_spots

    def update_difficulty(self, difficulty: int) -> None:
        self.difficulty = difficulty

    def generate_one(self) -> dict | None:
        query = self._make_query()
        chunks = retrieve(query, self.embedder, self.chroma_dir, self.top_k)
        if not chunks:
            return None

        examples = get_style_examples(2)
        messages = build_question_prompt(chunks, self.weak_spots, examples, self.difficulty)
        question = None
        for _ in range(3):
            raw = self.chat_client.chat(messages)
            question = _parse_question_json(raw)
            if question:
                break
        if not question:
            return None

        _shuffle_choices(question)
        question["difficulty"] = self.difficulty

        explanations = self._generate_explanations(question)
        if explanations:
            question["explanations"] = explanations

        return question

    def _generate_explanations(self, question: dict) -> dict[str, str] | None:
        messages = build_all_explanations_prompt(
            question["question"], question["choices"], question["correct"]
        )
        for _ in range(3):
            raw = self.chat_client.chat(messages)
            parsed = _parse_explanations_json(raw)
            if parsed:
                return parsed
        return None

    def fill(self, count: int, on_progress: callable = None) -> None:
        for i in range(count):
            question = self.generate_one()
            if question and question["question"] not in self.asked_questions:
                with self._lock:
                    self.questions.append(question)
                self._save()
            if on_progress:
                on_progress(i + 1, count)

    def _refill_background(self, count: int) -> None:
        self._refilling = True

        def _work() -> None:
            self.fill(count)
            self._refilling = False

        thread = threading.Thread(target=_work, daemon=True)
        thread.start()

    def _make_query(self) -> str:
        if self.weak_spots and random.random() < 0.7:
            return f"certification exam topic: {random.choice(self.weak_spots)}"
        topics = [
            "solution architecture", "network design", "storage systems",
            "compute provisioning", "security controls", "IAM",
            "cost optimization", "CI/CD deployment", "monitoring and observability",
            "disaster recovery", "migration planning", "compliance",
        ]
        return f"certification exam topic: {random.choice(topics)}"


def _shuffle_choices(question: dict) -> None:
    choices = question["choices"]
    correct_text = choices[question["correct"]]
    items = list(choices.items())
    random.shuffle(items)
    new_choices = {}
    for new_letter, (_, text) in zip("ABCD", items):
        new_choices[new_letter] = text
        if text == correct_text:
            question["correct"] = new_letter
    question["choices"] = new_choices


def _parse_question_json(raw: str) -> dict | None:
    raw = _strip_markdown_fences(raw)
    try:
        data = json.loads(raw)
        required = {"domain", "topic", "question", "choices", "correct", "explanation"}
        if required.issubset(data.keys()):
            return data
    except json.JSONDecodeError:
        pass
    return None


def _parse_explanations_json(raw: str) -> dict[str, str] | None:
    raw = _strip_markdown_fences(raw)
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and all(k in data for k in ("A", "B", "C", "D")):
            return data
    except json.JSONDecodeError:
        pass
    return None


def _strip_markdown_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(lines)
    return raw
