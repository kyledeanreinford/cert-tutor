import json
import random
from pathlib import Path

SEED_FILE = Path(__file__).parent.parent / "cca_question_bank.json"

DOMAIN_NAMES: dict[str, str] = {
    "d1": "Agentic Architecture & Orchestration",
    "d2": "Tool Design & MCP Integration",
    "d3": "Claude Code Configuration & Workflows",
    "d4": "Prompt Engineering & Structured Output",
    "d5": "Context Management & Reliability",
}


def _shuffle_choices(q: dict) -> dict:
    """Randomly remap A/B/C/D, updating the correct answer letter to match."""
    choices = q["choices"]
    correct = q["correct"]

    if isinstance(correct, list):
        correct_texts = {choices[c] for c in correct if c in choices}
        items = list(choices.items())
        random.shuffle(items)
        new_choices = {}
        new_correct = []
        for new_letter, (_, text) in zip("ABCD", items):
            new_choices[new_letter] = text
            if text in correct_texts:
                new_correct.append(new_letter)
        q["choices"] = new_choices
        q["correct"] = sorted(new_correct)
    else:
        correct_text = choices.get(correct, "")
        items = list(choices.items())
        random.shuffle(items)
        new_choices = {}
        for new_letter, (_, text) in zip("ABCD", items):
            new_choices[new_letter] = text
            if text == correct_text:
                q["correct"] = new_letter
        q["choices"] = new_choices

    return q


def _normalize(q: dict) -> dict:
    """Normalize cca_question_bank.json format to the internal question format."""
    domain_id = q.get("domain", "")
    key_concept = q.get("key_concept", "")
    return {
        "id": q["id"],
        "cert": "architect",
        "domain": DOMAIN_NAMES.get(domain_id, domain_id),
        "topic": q.get("task_statement", ""),
        "question": q["question"],
        "choices": q.get("options", q.get("choices", {})),
        "correct": q.get("correct_answer", q.get("correct", "")),
        "explanation": q.get("explanation", ""),
        "products": [key_concept] if key_concept else q.get("anti_patterns", []),
        "multi_select": q.get("multi_select", False),
        "scenario": q.get("scenario"),
        "source": q.get("source"),
    }


def load_seed_questions(cert: str = "architect") -> list[dict]:
    if not SEED_FILE.exists():
        return []
    data = json.loads(SEED_FILE.read_text())
    questions = data.get("questions", [])
    normalized = [_normalize(q) for q in questions]
    return [q for q in normalized if q.get("cert", "architect") == cert]


def get_unasked_seed(
    asked_ids: list[str], weak_domains: set[str] | None = None, cert: str = "architect"
) -> dict | None:
    questions = load_seed_questions(cert)
    unasked = [q for q in questions if q["id"] not in asked_ids]
    if not unasked:
        return None

    if weak_domains:
        weak_matches = [q for q in unasked if q.get("domain") in weak_domains]
        if weak_matches:
            return _shuffle_choices(random.choice(weak_matches))

    return _shuffle_choices(random.choice(unasked))


def get_style_examples(count: int = 2, cert: str = "architect") -> list[dict]:
    questions = load_seed_questions(cert)
    single_answer = [q for q in questions if not q.get("multi_select")]
    if len(single_answer) <= count:
        return single_answer
    return random.sample(single_answer, count)
