import json
from datetime import datetime
from pathlib import Path
from typing import Any


RETRY_QUEUE_MAX = 50
RETRY_COOLDOWN = 5


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
        self.session_runs: list[dict[str, Any]] = []
        self.current_run_start: str | None = None
        self.exam_runs: list[dict[str, Any]] = []

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
            session.session_runs = data.get("session_runs", [])
            session.current_run_start = data.get("current_run_start", None)
            session.exam_runs = data.get("exam_runs", [])
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
            "session_runs": self.session_runs,
            "current_run_start": self.current_run_start,
            "exam_runs": self.exam_runs,
        }
        self.history_file.write_text(json.dumps(data, indent=2))

    def record(
        self,
        question: str,
        choices: dict[str, str],
        user_answer: str,
        correct_answer: str,
        domain: str,
        topic: str,
        explanation: str,
    ) -> None:
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

        self.history.append({
            "question": question,
            "choices": choices,
            "correct_answer": correct_answer,
            "user_answer": user_answer.upper(),
            "domain": domain,
            "topic": topic,
            "explanation": explanation,
            "timestamp": datetime.now().isoformat(),
        })

    def add_to_retry_queue(self, question_data: dict[str, Any]) -> None:
        question_text = question_data["question"]
        for entry in self.retry_queue:
            if entry["question"] == question_text:
                entry["retry_count"] += 1
                entry["missed_at"] = datetime.now().isoformat()
                entry["not_before"] = self.total_questions + RETRY_COOLDOWN
                return

        entry = {
            "question": question_data["question"],
            "choices": question_data["choices"],
            "correct": question_data["correct"],
            "domain": question_data.get("domain", ""),
            "topic": question_data.get("topic", ""),
            "explanation": question_data.get("explanation", ""),
            "missed_at": datetime.now().isoformat(),
            "retry_count": 0,
            "not_before": self.total_questions + RETRY_COOLDOWN,
        }
        self.retry_queue.append(entry)

        if len(self.retry_queue) > RETRY_QUEUE_MAX:
            self.retry_queue = self.retry_queue[-RETRY_QUEUE_MAX:]

    def get_retry_question(
        self, weak_domains: set[str] | None = None, only_domain: str | None = None
    ) -> dict[str, Any] | None:
        eligible = [
            i for i, e in enumerate(self.retry_queue)
            if e.get("not_before", 0) <= self.total_questions
        ]
        if only_domain is not None:
            eligible = [i for i in eligible if self.retry_queue[i].get("domain") == only_domain]
        if not eligible:
            return None
        if weak_domains:
            for i in eligible:
                if self.retry_queue[i].get("domain") in weak_domains:
                    return self.retry_queue.pop(i)
        return self.retry_queue.pop(eligible[0])

    def retry_queue_size(self) -> int:
        return len(self.retry_queue)

    def eligible_retry_count(self, only_domain: str | None = None) -> int:
        return sum(
            1 for e in self.retry_queue
            if e.get("not_before", 0) <= self.total_questions
            and (only_domain is None or e.get("domain") == only_domain)
        )

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

    def weak_domains(self, threshold: float, recent_n: int = 0) -> list[str]:
        """Return domain names whose accuracy is below threshold, weakest first."""
        if recent_n > 0 and self.history:
            stats: dict[str, dict[str, int]] = {}
            for entry in self.history[-recent_n:]:
                domain = entry.get("domain", "")
                if not domain:
                    continue
                if domain not in stats:
                    stats[domain] = {"asked": 0, "correct": 0}
                stats[domain]["asked"] += 1
                if entry["user_answer"] == entry["correct_answer"]:
                    stats[domain]["correct"] += 1
        else:
            stats = self.domains

        weak: list[tuple[str, float]] = []
        for domain, s in stats.items():
            if s["asked"] > 0:
                rate = s["correct"] / s["asked"]
                if rate < threshold:
                    weak.append((domain, rate))
        weak.sort(key=lambda x: x[1])
        return [domain for domain, _ in weak]

    def record_exam_run(
        self,
        score: int,
        total: int,
        elapsed_seconds: float,
        per_domain: dict[str, dict[str, int]],
    ) -> None:
        self.exam_runs.append({
            "ended": datetime.now().isoformat(),
            "score": score,
            "total": total,
            "elapsed_seconds": int(elapsed_seconds),
            "per_domain": per_domain,
        })

    def summary(self) -> dict[str, Any]:
        rate = (self.total_correct / self.total_questions * 100) if self.total_questions > 0 else 0.0
        return {
            "total_questions": self.total_questions,
            "total_correct": self.total_correct,
            "rate": rate,
            "domains": self.domains,
            "topics": self.topics,
        }
