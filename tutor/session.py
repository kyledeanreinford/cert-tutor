import json
from datetime import datetime
from pathlib import Path
from typing import Any


RETRY_QUEUE_MAX = 50


class Session:
    def __init__(self, history_file: Path) -> None:
        self.history_file = history_file
        self.total_questions: int = 0
        self.total_correct: int = 0
        self.domains: dict[str, dict[str, int]] = {}
        self.topics: dict[str, dict[str, int]] = {}
        self.history: list[dict[str, Any]] = []
        self.asked_seed_ids: list[str] = []
        self.retry_queue: list[dict[str, Any]] = []
        self.products: dict[str, dict[str, int]] = {}
        self.session_runs: list[dict[str, Any]] = []
        self.current_run_start: str | None = None
        self.current_level: int = 1
        self.level_history: list[dict[str, Any]] = []

    @classmethod
    def load(cls, history_file: Path) -> "Session":
        session = cls(history_file)
        if history_file.exists():
            data = json.loads(history_file.read_text())
            session.total_questions = data.get("total_questions", 0)
            session.total_correct = data.get("total_correct", 0)
            session.domains = data.get("domains", {})
            session.topics = data.get("topics", {})
            session.history = data.get("history", [])
            session.asked_seed_ids = data.get("asked_seed_ids", [])
            session.retry_queue = data.get("retry_queue", [])
            session.products = data.get("products", {})
            session.session_runs = data.get("session_runs", [])
            session.current_run_start = data.get("current_run_start", None)
            session.current_level = data.get("current_level", 1)
            session.level_history = data.get("level_history", [])
        return session

    def save(self) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_questions": self.total_questions,
            "total_correct": self.total_correct,
            "domains": self.domains,
            "topics": self.topics,
            "history": self.history,
            "asked_seed_ids": self.asked_seed_ids,
            "retry_queue": self.retry_queue,
            "products": self.products,
            "session_runs": self.session_runs,
            "current_run_start": self.current_run_start,
            "current_level": self.current_level,
            "level_history": self.level_history,
        }
        self.history_file.write_text(json.dumps(data, indent=2))

    def record(
        self,
        question: str,
        choices: dict[str, str],
        user_answer: str | list[str],
        correct_answer: str | list[str],
        domain: str,
        topic: str,
        explanation: str,
        products: list[str] | None = None,
        difficulty: int = 2,
    ) -> None:
        if isinstance(correct_answer, list):
            is_correct = set(user_answer) == set(correct_answer)
        else:
            is_correct = user_answer.upper() == correct_answer.upper()
        self.total_questions += 1
        if is_correct:
            self.total_correct += 1

        if domain not in self.domains:
            self.domains[domain] = {"asked": 0, "correct": 0}
        self.domains[domain]["asked"] += 1
        if is_correct:
            self.domains[domain]["correct"] += 1

        if topic not in self.topics:
            self.topics[topic] = {"asked": 0, "correct": 0}
        self.topics[topic]["asked"] += 1
        if is_correct:
            self.topics[topic]["correct"] += 1

        for product in (products or []):
            if product not in self.products:
                self.products[product] = {"asked": 0, "correct": 0}
            self.products[product]["asked"] += 1
            if is_correct:
                self.products[product]["correct"] += 1

        self.history.append({
            "question": question,
            "choices": choices,
            "correct_answer": correct_answer,
            "user_answer": [a.upper() for a in user_answer] if isinstance(user_answer, list) else user_answer.upper(),
            "domain": domain,
            "topic": topic,
            "explanation": explanation,
            "products": products or [],
            "difficulty": difficulty,
            "timestamp": datetime.now().isoformat(),
        })

    def add_to_retry_queue(self, question_data: dict[str, Any]) -> None:
        question_text = question_data["question"]
        for entry in self.retry_queue:
            if entry["question"] == question_text:
                entry["retry_count"] += 1
                entry["missed_at"] = datetime.now().isoformat()
                return

        entry = {
            "question": question_data["question"],
            "choices": question_data["choices"],
            "correct": question_data["correct"],
            "domain": question_data.get("domain", ""),
            "topic": question_data.get("topic", ""),
            "explanation": question_data.get("explanation", ""),
            "explanations": question_data.get("explanations"),
            "case_study": question_data.get("case_study"),
            "products": question_data.get("products", []),
            "missed_at": datetime.now().isoformat(),
            "retry_count": 0,
        }
        self.retry_queue.append(entry)

        if len(self.retry_queue) > RETRY_QUEUE_MAX:
            self.retry_queue = self.retry_queue[-RETRY_QUEUE_MAX:]

    def get_retry_question(self, weak_domains: set[str] | None = None) -> dict[str, Any] | None:
        if not self.retry_queue:
            return None
        if weak_domains:
            for i, entry in enumerate(self.retry_queue):
                if entry.get("domain") in weak_domains:
                    return self.retry_queue.pop(i)
        return self.retry_queue.pop(0)

    def retry_queue_size(self) -> int:
        return len(self.retry_queue)

    def start_run(self) -> None:
        self.current_run_start = datetime.now().isoformat()

    def end_run(self) -> None:
        if not self.current_run_start:
            return

        run_history = [
            h for h in self.history
            if h.get("timestamp", "") >= self.current_run_start
        ]
        if not run_history:
            self.current_run_start = None
            return

        run_correct = sum(1 for h in run_history if h["user_answer"] == h["correct_answer"])
        self.session_runs.append({
            "started": self.current_run_start,
            "ended": datetime.now().isoformat(),
            "questions_asked": len(run_history),
            "questions_correct": run_correct,
        })
        self.current_run_start = None

    def weak_spots(self, threshold: float, recent_n: int = 0) -> list[str]:
        if recent_n > 0 and self.history:
            recent = self.history[-recent_n:]
            topic_stats: dict[str, dict[str, int]] = {}
            for entry in recent:
                topic = entry.get("topic", entry.get("domain", ""))
                if topic not in topic_stats:
                    topic_stats[topic] = {"asked": 0, "correct": 0}
                topic_stats[topic]["asked"] += 1
                if entry["user_answer"] == entry["correct_answer"]:
                    topic_stats[topic]["correct"] += 1
        else:
            topic_stats = self.topics

        weak: list[tuple[str, float]] = []
        for topic, stats in topic_stats.items():
            if stats["asked"] > 0:
                rate = stats["correct"] / stats["asked"]
                if rate < threshold:
                    weak.append((topic, rate))
        weak.sort(key=lambda x: x[1])
        return [topic for topic, _ in weak]

    def weak_products(self, threshold: float) -> list[tuple[str, float, int]]:
        weak: list[tuple[str, float, int]] = []
        for product, stats in self.products.items():
            if stats["asked"] >= 2:
                rate = stats["correct"] / stats["asked"]
                if rate < threshold:
                    weak.append((product, rate, stats["asked"]))
        weak.sort(key=lambda x: x[1])
        return weak

    def check_level_change(
        self, promote_threshold: float, demote_threshold: float, window_size: int
    ) -> int | None:
        recent_at_level = [
            h for h in self.history
            if h.get("difficulty", 2) == self.current_level
        ][-window_size:]

        if len(recent_at_level) < window_size:
            return None

        correct = sum(
            1 for h in recent_at_level
            if h["user_answer"] == h["correct_answer"]
        )
        rate = correct / len(recent_at_level)

        if rate >= promote_threshold and self.current_level < 3:
            return self.current_level + 1
        if rate <= demote_threshold and self.current_level > 1:
            return self.current_level - 1
        return None

    def set_level(self, new_level: int) -> None:
        self.level_history.append({
            "from": self.current_level,
            "to": new_level,
            "timestamp": datetime.now().isoformat(),
            "total_questions": self.total_questions,
        })
        self.current_level = new_level

    def summary(self) -> dict[str, Any]:
        rate = (self.total_correct / self.total_questions * 100) if self.total_questions > 0 else 0.0
        return {
            "total_questions": self.total_questions,
            "total_correct": self.total_correct,
            "rate": rate,
            "domains": self.domains,
            "topics": self.topics,
        }
