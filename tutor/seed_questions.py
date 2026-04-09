import json
import random
from pathlib import Path

SEED_FILE = Path(__file__).parent.parent / "sample_questions.json"


def load_seed_questions(cert: str = "architect") -> list[dict]:
    if not SEED_FILE.exists():
        return []
    data = json.loads(SEED_FILE.read_text())
    questions = data.get("questions", [])
    return [q for q in questions if q.get("cert", "architect") == cert]


def get_unasked_seed(
    asked_ids: list[int], weak_domains: set[str] | None = None, cert: str = "architect"
) -> dict | None:
    questions = load_seed_questions(cert)
    unasked = [q for q in questions if q["id"] not in asked_ids]
    if not unasked:
        return None

    if weak_domains:
        weak_matches = [q for q in unasked if q.get("domain") in weak_domains]
        if weak_matches:
            return random.choice(weak_matches)

    return random.choice(unasked)


def get_style_examples(count: int = 2, cert: str = "architect") -> list[dict]:
    questions = load_seed_questions(cert)
    single_answer = [q for q in questions if not q.get("multi_select")]
    if len(single_answer) <= count:
        return single_answer
    return random.sample(single_answer, count)
