import random
import re
import unittest

from tutor.seed_questions import _remap_explanation, _shuffle_choices

# Each choice carries a distinctive keyword that also appears in that choice's
# explanation sentence, so we can assert the prose stays glued to its choice
# across shuffles.
CHOICES = {
    "A": "Use fork_session to branch state.",
    "B": "Call tools in a single turn.",
    "C": "Create new sessions from scratch.",
    "D": "Make redundant API calls.",
}
KEYWORDS = {
    "A": "fork_session",
    "B": "single turn",
    "C": "new sessions",
    "D": "API calls",
}


def make_question() -> dict:
    return {
        "id": "q1",
        "correct": "A",
        "choices": dict(CHOICES),
        "explanation": (
            "Option A is correct because fork_session isolates failures. "
            "Option B is wrong because a single turn shares one context. "
            "Option C is wrong because new sessions lose history. "
            "Option D is wrong because redundant API calls corrupt state."
        ),
    }


class TestShuffleChoices(unittest.TestCase):
    def test_correct_letter_tracks_correct_text(self) -> None:
        """Across every permutation, the correct letter must point at the
        original correct text and no choice text may be lost."""
        for seed in range(50):
            q = make_question()
            original_correct_text = q["choices"][q["correct"]]
            original_texts = set(q["choices"].values())

            random.seed(seed)
            shuffled = _shuffle_choices(q)

            self.assertEqual(set(shuffled["choices"].values()), original_texts)
            self.assertEqual(
                shuffled["choices"][shuffled["correct"]], original_correct_text
            )

    def test_explanation_verdict_matches_correct_letter(self) -> None:
        """The 'Option X is correct' phrase must name the new correct letter."""
        for seed in range(50):
            q = make_question()
            random.seed(seed)
            shuffled = _shuffle_choices(q)

            m = re.search(r"Option ([A-D]) is correct", shuffled["explanation"])
            self.assertIsNotNone(m)
            self.assertEqual(m.group(1), shuffled["correct"])

    def test_explanation_prose_stays_glued_to_its_choice(self) -> None:
        """For each letter, the explanation sentence at that letter must
        describe the choice now sitting at that letter."""
        for seed in range(50):
            q = make_question()
            random.seed(seed)
            shuffled = _shuffle_choices(q)

            for letter, text in shuffled["choices"].items():
                keyword = next(kw for kw in KEYWORDS.values() if kw in text)
                m = re.search(
                    rf"Option {letter} is \w+ because (.*?)\.",
                    shuffled["explanation"],
                )
                self.assertIsNotNone(m, f"no explanation sentence for {letter}")
                self.assertIn(keyword, m.group(1))


class TestRemapExplanation(unittest.TestCase):
    def test_identity_mapping_is_noop(self) -> None:
        ident = {c: c for c in "ABCD"}
        text = make_question()["explanation"]
        self.assertEqual(_remap_explanation(text, ident), text)

    def test_empty_text(self) -> None:
        self.assertEqual(_remap_explanation("", {"A": "B"}), "")

    def test_remaps_keyword_anchored_letters(self) -> None:
        mapping = {"A": "C", "B": "D", "C": "A", "D": "B"}
        text = "Option A is correct. Options B and C rely on prompts. Distractor D fails."
        out = _remap_explanation(text, mapping)
        self.assertEqual(
            out,
            "Option C is correct. Options D and A rely on prompts. Distractor B fails.",
        )

    def test_remaps_verdict_and_parenthesized_forms(self) -> None:
        mapping = {"A": "D", "B": "A", "C": "B", "D": "C"}
        text = "The correct answer is A. Few-shot examples (B) add overhead. Correct: A."
        out = _remap_explanation(text, mapping)
        self.assertIn("answer is D", out)
        self.assertIn("(A)", out)
        self.assertIn("Correct: D", out)

    def test_remaps_verdict_labels(self) -> None:
        mapping = {"A": "C", "B": "D", "C": "A", "D": "B"}
        text = "Wrong: B. Incorrect: C. Right: A."
        out = _remap_explanation(text, mapping)
        self.assertEqual(out, "Wrong: D. Incorrect: A. Right: C.")

    def test_remaps_clause_initial_verdicts(self) -> None:
        mapping = {"A": "C", "B": "D", "C": "A", "D": "B"}
        text = "Why distractors are wrong:\nB is wrong because x. D is incorrect because y."
        out = _remap_explanation(text, mapping)
        self.assertIn("D is wrong because x", out)
        self.assertIn("B is incorrect because y", out)

    def test_remaps_approach_is_and_unlike(self) -> None:
        mapping = {"A": "D", "B": "A", "C": "B", "D": "C"}
        text = "The correct approach is C because it scales (unlike B)."
        out = _remap_explanation(text, mapping)
        self.assertIn("approach is B", out)
        self.assertIn("(unlike A)", out)

    def test_remaps_comma_and_list(self) -> None:
        """The ', and' separator must be handled — every letter in the list
        gets remapped, including the trailing one."""
        mapping = {"A": "B", "B": "C", "C": "D", "D": "A"}
        text = "Options A, C, and D are incorrect."
        out = _remap_explanation(text, mapping)
        self.assertEqual(out, "Options B, D, and A are incorrect.")

    def test_preserves_non_option_proper_nouns(self) -> None:
        """Bare letters not anchored to an option reference (scenario proper
        nouns like 'Warehouse B and C', 'Agent C is inefficient') must be left
        untouched."""
        mapping = {"A": "C", "B": "D", "C": "A", "D": "B"}
        text = (
            "Option A is correct. The MCP servers (Warehouse B and C) sync nightly, "
            "and Agent C is inefficient at routing."
        )
        out = _remap_explanation(text, mapping)
        self.assertIn("Warehouse B and C", out)
        self.assertIn("Agent C is inefficient", out)
        self.assertIn("Option C is correct", out)

    def test_does_not_touch_indefinite_article(self) -> None:
        mapping = {"A": "D", "B": "A", "C": "B", "D": "C"}
        text = "Option A is correct. A routing layer adds latency."
        out = _remap_explanation(text, mapping)
        self.assertIn("A routing layer", out)
        self.assertIn("Option D is correct", out)


class TestRealBankConsistency(unittest.TestCase):
    """Guards over the shipped question bank, so a future bank edit that
    introduces an unhandled letter-reference frame fails loudly."""

    def setUp(self) -> None:
        from tutor.seed_questions import load_seed_questions

        self.questions = load_seed_questions()

    def test_bank_is_loaded(self) -> None:
        self.assertGreater(len(self.questions), 0)

    def test_identity_remap_is_noop_for_every_explanation(self) -> None:
        ident = {c: c for c in "ABCD"}
        for q in self.questions:
            e = q.get("explanation", "")
            self.assertEqual(_remap_explanation(e, ident), e, q["id"])

    def test_shuffle_never_mangles_a_multichar_word(self) -> None:
        import copy

        random.seed(11)
        for q in self.questions:
            for _ in range(3):
                sh = _shuffle_choices(copy.deepcopy(q))
                before = re.findall(r"[A-Za-z]{2,}", q.get("explanation", ""))
                after = re.findall(r"[A-Za-z]{2,}", sh.get("explanation", ""))
                self.assertEqual(before, after, q["id"])

    def test_every_bare_bcd_letter_is_covered_or_proper_noun(self) -> None:
        """Every standalone B/C/D in an explanation (these can never be the
        English article) must either be inside a remap reference pattern or be
        a proper-noun reference preceded by a capitalized word. Otherwise it is
        an option reference that a shuffle would silently leave wrong."""
        from tutor.seed_questions import _REFERENCE_PATTERNS

        patterns = [re.compile(p) for p in _REFERENCE_PATTERNS]
        proper = re.compile(r"[A-Z][a-z]+\s+(?:[A-D]\s+(?:and|or|,)\s+)?$")

        def covered(text: str, pos: int) -> bool:
            return any(
                m.start() <= pos < m.end()
                for pat in patterns
                for m in pat.finditer(text)
            )

        offenders = []
        for q in self.questions:
            e = q.get("explanation", "")
            for m in re.finditer(r"\b[B-D]\b", e):
                if covered(e, m.start()):
                    continue
                before = e[max(0, m.start() - 20) : m.start()]
                if proper.search(before):
                    continue
                offenders.append(f"{q['id']}: ...{e[max(0, m.start()-20):m.start()+8]!r}")
        self.assertEqual(offenders, [], "uncovered option-letter references:\n" + "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
