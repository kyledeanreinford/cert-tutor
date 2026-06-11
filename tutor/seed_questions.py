import json
import random
import re
from pathlib import Path

# Keywords that reliably precede an option-letter reference, e.g. "Option B",
# "Options A, C, and D", "Distractor D", "Choice A".
_KEYWORD = r"(?:options?|distractors?|choices?|answers?)"
# A letter, or a comma/conjunction-joined list of letters. The separator run
# (`(?:,|and|or|&|/)`-with-spaces, one-or-more) handles "B and C", "A, C, and D"
# (note the combined ", and ") and "A/B".
_LETTER_LIST = r"[A-D](?:(?:\s*(?:,|and|or|&|/)\s*)+[A-D])*"

# Each entry matches a span that names an option by letter; remap_span() then
# rewrites only the standalone A-D tokens inside the matched span.
_REFERENCE_PATTERNS = (
    # "Option B", "Options A, C, and D", "Distractor D"
    rf"(?i)\b{_KEYWORD}\s+{_LETTER_LIST}",
    # verdict labels: "Correct: A", "Wrong: B", "Incorrect: C"
    r"(?i)\b(?:correct|incorrect|wrong|right):\s*[A-D]\b",
    # "answer is C", "the correct approach is B", "option is D"
    r"(?i)\b(?:answer|approach|option|choice)\s+is\s+[A-D]\b",
    # clause-initial verdicts: "B is wrong", "A is incorrect" (anchored to a
    # sentence/line/colon boundary so scenario proper nouns like "Agent C is
    # inefficient" are NOT matched)
    r"(?i)(?:^|[.:\n]\s*)[A-D]\s+is\s+(?:wrong|incorrect|correct|right)\b",
    # comparison: "unlike B"
    r"(?i)\bunlike\s+[A-D]\b",
    # parenthesized: "(D)"
    r"\([A-D]\)",
)

SEED_FILE = Path(__file__).parent.parent / "claude_certified_architect_question_bank.json"

DOMAIN_NAMES: dict[str, str] = {
    "d1": "Agentic Architecture & Orchestration",
    "d2": "Tool Design & MCP Integration",
    "d3": "Claude Code Configuration & Workflows",
    "d4": "Prompt Engineering & Structured Output",
    "d5": "Context Management & Reliability",
}


def _remap_explanation(text: str, mapping: dict[str, str]) -> str:
    """Rewrite option-letter references in explanation prose to match the new
    letter assignments. Only touches letters anchored to one of the
    _REFERENCE_PATTERNS (an option keyword, a verdict phrase, a clause-initial
    verdict, "unlike X", or a parenthesized form) — so the English article "A"
    and scenario proper nouns like "Warehouse B and C" or "Agent C" are left
    untouched."""
    if not text:
        return text

    # Collect every span (on the *original* text) that names an option by
    # letter. Patterns can overlap — a header "...are wrong:" abutting a
    # clause-initial "B is wrong" is matched by two patterns — so we gather all
    # spans first, then remap in a single pass. Remapping pattern-by-pattern
    # instead would touch an overlapped letter twice and scramble it.
    spans = [
        m.span()
        for pattern in _REFERENCE_PATTERNS
        for m in re.finditer(pattern, text)
    ]

    def remap(m: re.Match) -> str:
        # Only remap a standalone letter that sits inside a reference span;
        # never letters embedded in an anchor word (the "D" in "Distractor")
        # or unanchored letters (the article "A", "Agent C").
        if any(start <= m.start() < end for start, end in spans):
            return mapping.get(m.group(), m.group())
        return m.group()

    return re.sub(r"\b[A-D]\b", remap, text)


def _shuffle_choices(q: dict) -> dict:
    """Randomly remap A/B/C/D, updating the correct answer letter and any
    letter references in the explanation to match."""
    choices = q["choices"]
    correct_text = choices.get(q["correct"], "")
    items = list(choices.items())
    random.shuffle(items)
    new_choices = {}
    mapping: dict[str, str] = {}
    for new_letter, (old_letter, text) in zip("ABCD", items):
        new_choices[new_letter] = text
        mapping[old_letter] = new_letter
        if text == correct_text:
            q["correct"] = new_letter
    q["choices"] = new_choices
    q["explanation"] = _remap_explanation(q.get("explanation", ""), mapping)
    return q


def _normalize(q: dict) -> dict:
    """Normalize claude_certified_architect_question_bank.json format to the internal question format."""
    domain_id = q.get("domain", "")
    return {
        "id": q["id"],
        "cert": "architect",
        "domain": DOMAIN_NAMES.get(domain_id, domain_id),
        "topic": q.get("task_statement", ""),
        "question": q["question"],
        "choices": q.get("options", q.get("choices", {})),
        "correct": q.get("correct_answer", q.get("correct", "")),
        "explanation": q.get("explanation", ""),
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
    asked_ids: list[str],
    weak_domains: set[str] | None = None,
    cert: str = "architect",
    only_domain: str | None = None,
    weak_bias: float = 0.65,
) -> dict | None:
    questions = load_seed_questions(cert)
    unasked = [q for q in questions if q["id"] not in asked_ids]
    if only_domain is not None:
        unasked = [q for q in unasked if q.get("domain") == only_domain]
    if not unasked:
        return None

    # Weak domains are a *bias*, not a hard filter: most of the time we pull
    # from a weak domain, but the rest of the time we pull from any unasked
    # question so other (and never-yet-seen) domains keep surfacing. A hard
    # filter here pins the whole session to the first domain to dip below the
    # threshold.
    if weak_domains:
        weak_matches = [q for q in unasked if q.get("domain") in weak_domains]
        if weak_matches and random.random() < weak_bias:
            return _shuffle_choices(random.choice(weak_matches))

    return _shuffle_choices(random.choice(unasked))
