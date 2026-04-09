import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from tutor.question_pool import QuestionPool, _parse_question_json, _parse_explanations_json, _shuffle_choices, _strip_markdown_fences


class TestStripMarkdownFences(unittest.TestCase):
    def test_no_fences(self) -> None:
        self.assertEqual(_strip_markdown_fences('{"key": "value"}'), '{"key": "value"}')

    def test_json_fences(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        self.assertEqual(_strip_markdown_fences(raw), '{"key": "value"}')

    def test_plain_fences(self) -> None:
        raw = '```\n{"key": "value"}\n```'
        self.assertEqual(_strip_markdown_fences(raw), '{"key": "value"}')

    def test_strips_whitespace(self) -> None:
        raw = '  \n```json\n{"a": 1}\n```\n  '
        self.assertEqual(_strip_markdown_fences(raw), '{"a": 1}')


class TestParseQuestionJson(unittest.TestCase):
    def _valid_json(self, **overrides) -> str:
        import json
        data = {
            "domain": "Security",
            "topic": "IAM",
            "question": "What is IAM?",
            "choices": {"A": "Identity", "B": "Storage", "C": "Compute", "D": "Network"},
            "correct": "A",
            "explanation": "IAM is Identity and Access Management.",
        }
        data.update(overrides)
        return json.dumps(data)

    def test_valid_json(self) -> None:
        result = _parse_question_json(self._valid_json())
        self.assertIsNotNone(result)
        self.assertEqual(result["domain"], "Security")

    def test_with_markdown_fences(self) -> None:
        raw = f"```json\n{self._valid_json()}\n```"
        result = _parse_question_json(raw)
        self.assertIsNotNone(result)

    def test_missing_required_field(self) -> None:
        import json
        data = {"domain": "D", "question": "Q?"}
        self.assertIsNone(_parse_question_json(json.dumps(data)))

    def test_invalid_json(self) -> None:
        self.assertIsNone(_parse_question_json("not json at all"))

    def test_empty_string(self) -> None:
        self.assertIsNone(_parse_question_json(""))

    def test_extra_fields_allowed(self) -> None:
        result = _parse_question_json(self._valid_json(products=["Spanner"], case_study="Cymbal"))
        self.assertIsNotNone(result)
        self.assertEqual(result["products"], ["Spanner"])


class TestParseExplanationsJson(unittest.TestCase):
    def test_valid(self) -> None:
        import json
        data = {"A": "Correct because...", "B": "Wrong because...", "C": "Wrong...", "D": "Wrong..."}
        result = _parse_explanations_json(json.dumps(data))
        self.assertEqual(result["A"], "Correct because...")

    def test_missing_key(self) -> None:
        import json
        data = {"A": "a", "B": "b", "C": "c"}
        self.assertIsNone(_parse_explanations_json(json.dumps(data)))

    def test_with_fences(self) -> None:
        import json
        data = {"A": "a", "B": "b", "C": "c", "D": "d"}
        raw = f"```json\n{json.dumps(data)}\n```"
        self.assertIsNotNone(_parse_explanations_json(raw))

    def test_invalid_json(self) -> None:
        self.assertIsNone(_parse_explanations_json("{broken"))

    def test_not_a_dict(self) -> None:
        self.assertIsNone(_parse_explanations_json('["A", "B", "C", "D"]'))


class TestShuffleChoices(unittest.TestCase):
    def test_correct_answer_tracks(self) -> None:
        question = {
            "question": "Q?",
            "choices": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"},
            "correct": "B",
        }
        original_correct_text = question["choices"]["B"]

        _shuffle_choices(question)

        new_correct_letter = question["correct"]
        self.assertEqual(question["choices"][new_correct_letter], original_correct_text)

    def test_all_four_choices_preserved(self) -> None:
        question = {
            "question": "Q?",
            "choices": {"A": "alpha", "B": "beta", "C": "gamma", "D": "delta"},
            "correct": "A",
        }
        _shuffle_choices(question)
        self.assertEqual(set(question["choices"].keys()), {"A", "B", "C", "D"})
        self.assertEqual(set(question["choices"].values()), {"alpha", "beta", "gamma", "delta"})

    def test_correct_is_valid_letter(self) -> None:
        question = {
            "question": "Q?",
            "choices": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct": "C",
        }
        _shuffle_choices(question)
        self.assertIn(question["correct"], "ABCD")


class TestQuestionPoolDedup(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.pool_path = Path(self.tmp.name) / "questions.json"
        self.pool = QuestionPool(
            pool_path=self.pool_path,
            chat_client=MagicMock(),
            embedder=MagicMock(),
            chroma_dir="",
            top_k=5,
            weak_spots=[],
            asked_questions={"Already asked this"},
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _q(self, text: str) -> dict:
        return {
            "question": text,
            "choices": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct": "A",
            "domain": "D",
            "topic": "T",
            "explanation": "E",
        }

    def test_pop_skips_already_asked(self) -> None:
        self.pool.questions = [
            self._q("Already asked this"),
            self._q("Fresh question"),
        ]
        result = self.pool.pop()
        self.assertEqual(result["question"], "Fresh question")

    def test_pop_returns_none_when_all_asked(self) -> None:
        self.pool.questions = [self._q("Already asked this")]
        result = self.pool.pop()
        self.assertIsNone(result)

    def test_mark_asked_prevents_future_pop(self) -> None:
        self.pool.questions = [self._q("New question")]
        self.pool.mark_asked("New question")
        result = self.pool.pop()
        self.assertIsNone(result)

    def test_pop_without_asked_set_returns_all(self) -> None:
        pool = QuestionPool(
            pool_path=self.pool_path,
            chat_client=MagicMock(),
            embedder=MagicMock(),
            chroma_dir="",
            top_k=5,
            weak_spots=[],
        )
        pool.questions = [self._q("Any question")]
        result = pool.pop()
        self.assertEqual(result["question"], "Any question")


class TestQuestionPoolDifficulty(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.pool_path = Path(self.tmp.name) / "questions.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _q(self, text: str, difficulty: int = 2) -> dict:
        return {
            "question": text,
            "choices": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct": "A",
            "domain": "D",
            "topic": "T",
            "explanation": "E",
            "difficulty": difficulty,
        }

    def test_pop_prefers_matching_difficulty(self) -> None:
        pool = QuestionPool(
            pool_path=self.pool_path, chat_client=MagicMock(), embedder=MagicMock(),
            chroma_dir="", top_k=5, weak_spots=[], difficulty=1,
        )
        pool.questions = [self._q("Hard", 3), self._q("Easy", 1), self._q("Medium", 2)]
        result = pool.pop()
        self.assertEqual(result["question"], "Easy")

    def test_pop_falls_back_when_no_matching_difficulty(self) -> None:
        pool = QuestionPool(
            pool_path=self.pool_path, chat_client=MagicMock(), embedder=MagicMock(),
            chroma_dir="", top_k=5, weak_spots=[], difficulty=3,
        )
        pool.questions = [self._q("Easy", 1), self._q("Medium", 2)]
        result = pool.pop()
        self.assertIsNotNone(result)

    def test_update_difficulty_changes_preference(self) -> None:
        pool = QuestionPool(
            pool_path=self.pool_path, chat_client=MagicMock(), embedder=MagicMock(),
            chroma_dir="", top_k=5, weak_spots=[], difficulty=1,
        )
        pool.questions = [self._q("Easy", 1), self._q("Hard", 3)]
        pool.update_difficulty(3)
        result = pool.pop()
        self.assertEqual(result["question"], "Hard")

    def test_questions_without_difficulty_default_to_2(self) -> None:
        pool = QuestionPool(
            pool_path=self.pool_path, chat_client=MagicMock(), embedder=MagicMock(),
            chroma_dir="", top_k=5, weak_spots=[], difficulty=2,
        )
        no_diff = {"question": "No diff", "choices": {"A": "a", "B": "b", "C": "c", "D": "d"},
                    "correct": "A", "domain": "D", "topic": "T", "explanation": "E"}
        pool.questions = [self._q("Has diff 1", 1), no_diff]
        result = pool.pop()
        self.assertEqual(result["question"], "No diff")


if __name__ == "__main__":
    unittest.main()
