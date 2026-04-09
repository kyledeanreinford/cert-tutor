import unittest

from tutor.prompter import DIFFICULTY_INSTRUCTIONS, build_question_prompt


class TestBuildQuestionPromptDifficulty(unittest.TestCase):
    def _chunks(self) -> list[dict]:
        return [{"text": "GCP Cloud Run is a serverless compute platform."}]

    def test_default_difficulty_is_intermediate(self) -> None:
        messages = build_question_prompt(self._chunks(), [])
        user_content = messages[1]["content"]
        self.assertIn("INTERMEDIATE", user_content)

    def test_level_1_beginner(self) -> None:
        messages = build_question_prompt(self._chunks(), [], difficulty=1)
        user_content = messages[1]["content"]
        self.assertIn("BEGINNER", user_content)
        self.assertNotIn("INTERMEDIATE", user_content)
        self.assertNotIn("EXPERT", user_content)

    def test_level_2_intermediate(self) -> None:
        messages = build_question_prompt(self._chunks(), [], difficulty=2)
        user_content = messages[1]["content"]
        self.assertIn("INTERMEDIATE", user_content)

    def test_level_3_expert(self) -> None:
        messages = build_question_prompt(self._chunks(), [], difficulty=3)
        user_content = messages[1]["content"]
        self.assertIn("EXPERT", user_content)
        self.assertIn("SAME category", user_content)

    def test_unknown_difficulty_falls_back_to_intermediate(self) -> None:
        messages = build_question_prompt(self._chunks(), [], difficulty=99)
        user_content = messages[1]["content"]
        self.assertIn("INTERMEDIATE", user_content)

    def test_difficulty_instructions_has_all_levels(self) -> None:
        self.assertIn(1, DIFFICULTY_INSTRUCTIONS)
        self.assertIn(2, DIFFICULTY_INSTRUCTIONS)
        self.assertIn(3, DIFFICULTY_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
