import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tutor.session import RETRY_QUEUE_MAX, Session


class TestSessionRecord(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.history_file = Path(self.tmp.name) / "history.json"
        self.session = Session(self.history_file)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_record_correct_answer(self) -> None:
        self.session.record(
            question="What is Cloud Run?",
            choices={"A": "Serverless", "B": "VM", "C": "Database", "D": "Storage"},
            user_answer="A",
            correct_answer="A",
            domain="Designing and Planning",
            topic="Compute",
            explanation="Cloud Run is serverless.",
        )
        self.assertEqual(self.session.total_questions, 1)
        self.assertEqual(self.session.total_correct, 1)
        self.assertEqual(self.session.domains["Designing and Planning"]["asked"], 1)
        self.assertEqual(self.session.domains["Designing and Planning"]["correct"], 1)

    def test_record_incorrect_answer(self) -> None:
        self.session.record(
            question="What is Cloud Run?",
            choices={"A": "Serverless", "B": "VM", "C": "Database", "D": "Storage"},
            user_answer="B",
            correct_answer="A",
            domain="Designing and Planning",
            topic="Compute",
            explanation="",
        )
        self.assertEqual(self.session.total_questions, 1)
        self.assertEqual(self.session.total_correct, 0)
        self.assertEqual(self.session.domains["Designing and Planning"]["correct"], 0)

    def test_record_case_insensitive(self) -> None:
        self.session.record(
            question="Q?",
            choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="a",
            correct_answer="A",
            domain="Security",
            topic="IAM",
            explanation="",
        )
        self.assertEqual(self.session.total_correct, 1)

    def test_record_multi_select_correct(self) -> None:
        self.session.record(
            question="Pick two.",
            choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer=["A", "C"],
            correct_answer=["C", "A"],
            domain="Security",
            topic="IAM",
            explanation="",
        )
        self.assertEqual(self.session.total_correct, 1)

    def test_record_multi_select_incorrect(self) -> None:
        self.session.record(
            question="Pick two.",
            choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer=["A", "B"],
            correct_answer=["A", "C"],
            domain="Security",
            topic="IAM",
            explanation="",
        )
        self.assertEqual(self.session.total_correct, 0)

    def test_record_tracks_topics(self) -> None:
        self.session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="Networking", explanation="",
        )
        self.session.record(
            question="Q2?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="B", correct_answer="A",
            domain="D", topic="Networking", explanation="",
        )
        self.assertEqual(self.session.topics["Networking"]["asked"], 2)
        self.assertEqual(self.session.topics["Networking"]["correct"], 1)

    def test_record_tracks_products(self) -> None:
        self.session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="",
            products=["Cloud Run", "Cloud Build"],
        )
        self.assertEqual(self.session.products["Cloud Run"]["asked"], 1)
        self.assertEqual(self.session.products["Cloud Run"]["correct"], 1)
        self.assertEqual(self.session.products["Cloud Build"]["asked"], 1)

    def test_record_appends_to_history(self) -> None:
        self.session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="Explained.",
        )
        self.assertEqual(len(self.session.history), 1)
        entry = self.session.history[0]
        self.assertEqual(entry["question"], "Q?")
        self.assertEqual(entry["explanation"], "Explained.")
        self.assertIn("timestamp", entry)


class TestSessionSaveLoad(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.history_file = Path(self.tmp.name) / "history.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_save_creates_file(self) -> None:
        session = Session(self.history_file)
        session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="",
        )
        session.save()
        self.assertTrue(self.history_file.exists())

    def test_round_trip(self) -> None:
        session = Session(self.history_file)
        session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="",
            products=["Spanner"],
        )
        session.asked_seed_ids = ["official-01", "community-05", "community-10"]
        session.save()

        loaded = Session.load(self.history_file)
        self.assertEqual(loaded.total_questions, 1)
        self.assertEqual(loaded.total_correct, 1)
        self.assertEqual(loaded.domains, {"D": {"asked": 1, "correct": 1}})
        self.assertEqual(loaded.asked_seed_ids, ["official-01", "community-05", "community-10"])
        self.assertEqual(loaded.products, {"Spanner": {"asked": 1, "correct": 1}})
        self.assertEqual(len(loaded.history), 1)

    def test_load_missing_file_returns_empty(self) -> None:
        loaded = Session.load(self.history_file)
        self.assertEqual(loaded.total_questions, 0)
        self.assertEqual(loaded.history, [])

    def test_save_creates_parent_dirs(self) -> None:
        nested = Path(self.tmp.name) / "a" / "b" / "history.json"
        session = Session(nested)
        session.save()
        self.assertTrue(nested.exists())


class TestSessionSummary(unittest.TestCase):
    def test_summary_empty(self) -> None:
        session = Session(Path("/dev/null"))
        summary = session.summary()
        self.assertEqual(summary["total_questions"], 0)
        self.assertEqual(summary["rate"], 0.0)

    def test_summary_with_data(self) -> None:
        session = Session(Path("/dev/null"))
        session.total_questions = 10
        session.total_correct = 7
        session.domains = {"D1": {"asked": 10, "correct": 7}}
        summary = session.summary()
        self.assertEqual(summary["rate"], 70.0)
        self.assertEqual(summary["domains"], {"D1": {"asked": 10, "correct": 7}})


class TestRetryQueue(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Session(Path("/dev/null"))

    def _make_question(self, text: str = "Q?", domain: str = "D") -> dict:
        return {
            "question": text,
            "choices": {"A": "a", "B": "b", "C": "c", "D": "d"},
            "correct": "A",
            "domain": domain,
            "topic": "T",
        }

    def test_add_and_size(self) -> None:
        self.session.add_to_retry_queue(self._make_question())
        self.assertEqual(self.session.retry_queue_size(), 1)

    def test_duplicate_increments_retry_count(self) -> None:
        question = self._make_question()
        self.session.add_to_retry_queue(question)
        self.session.add_to_retry_queue(question)
        self.assertEqual(self.session.retry_queue_size(), 1)
        self.assertEqual(self.session.retry_queue[0]["retry_count"], 1)

    def test_get_retry_returns_fifo(self) -> None:
        self.session.add_to_retry_queue(self._make_question("First"))
        self.session.add_to_retry_queue(self._make_question("Second"))
        result = self.session.get_retry_question()
        self.assertEqual(result["question"], "First")
        self.assertEqual(self.session.retry_queue_size(), 1)

    def test_get_retry_prefers_weak_domain(self) -> None:
        self.session.add_to_retry_queue(self._make_question("Strong", "Security"))
        self.session.add_to_retry_queue(self._make_question("Weak", "Networking"))
        result = self.session.get_retry_question(weak_domains={"Networking"})
        self.assertEqual(result["question"], "Weak")

    def test_get_retry_empty_returns_none(self) -> None:
        self.assertIsNone(self.session.get_retry_question())

    def test_max_queue_size_enforced(self) -> None:
        for i in range(RETRY_QUEUE_MAX + 10):
            self.session.add_to_retry_queue(self._make_question(f"Q{i}"))
        self.assertEqual(self.session.retry_queue_size(), RETRY_QUEUE_MAX)


class TestWeakSpots(unittest.TestCase):
    def setUp(self) -> None:
        self.session = Session(Path("/dev/null"))

    def test_no_data_returns_empty(self) -> None:
        self.assertEqual(self.session.weak_spots(0.7), [])

    def test_identifies_weak_topics(self) -> None:
        self.session.topics = {
            "Networking": {"asked": 10, "correct": 3},
            "IAM": {"asked": 10, "correct": 9},
            "Storage": {"asked": 10, "correct": 5},
        }
        weak = self.session.weak_spots(0.7)
        self.assertIn("Networking", weak)
        self.assertIn("Storage", weak)
        self.assertNotIn("IAM", weak)

    def test_sorted_by_rate_ascending(self) -> None:
        self.session.topics = {
            "A": {"asked": 10, "correct": 5},
            "B": {"asked": 10, "correct": 2},
            "C": {"asked": 10, "correct": 4},
        }
        weak = self.session.weak_spots(0.7)
        self.assertEqual(weak, ["B", "C", "A"])

    def test_recent_n_uses_recent_history(self) -> None:
        self.session.topics = {
            "Networking": {"asked": 10, "correct": 3},
        }
        self.session.history = [
            {"topic": "Networking", "user_answer": "A", "correct_answer": "A"},
            {"topic": "Networking", "user_answer": "A", "correct_answer": "A"},
            {"topic": "Networking", "user_answer": "A", "correct_answer": "A"},
        ]
        weak = self.session.weak_spots(0.7, recent_n=3)
        self.assertNotIn("Networking", weak)


class TestWeakProducts(unittest.TestCase):
    def test_ignores_single_ask(self) -> None:
        session = Session(Path("/dev/null"))
        session.products = {"Spanner": {"asked": 1, "correct": 0}}
        self.assertEqual(session.weak_products(0.7), [])

    def test_identifies_weak_products(self) -> None:
        session = Session(Path("/dev/null"))
        session.products = {
            "Spanner": {"asked": 5, "correct": 1},
            "BigQuery": {"asked": 5, "correct": 4},
        }
        weak = session.weak_products(0.7)
        self.assertEqual(len(weak), 1)
        self.assertEqual(weak[0][0], "Spanner")


class TestSessionRuns(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.history_file = Path(self.tmp.name) / "history.json"
        self.session = Session(self.history_file)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_start_and_end_run(self) -> None:
        self.session.start_run()
        self.assertIsNotNone(self.session.current_run_start)

        self.session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="",
        )
        self.session.end_run()

        self.assertEqual(len(self.session.session_runs), 1)
        self.assertEqual(self.session.session_runs[0]["questions_asked"], 1)
        self.assertEqual(self.session.session_runs[0]["questions_correct"], 1)
        self.assertIsNone(self.session.current_run_start)

    def test_end_run_no_start_is_noop(self) -> None:
        self.session.end_run()
        self.assertEqual(len(self.session.session_runs), 0)

    def test_end_run_no_questions_clears_start(self) -> None:
        self.session.start_run()
        self.session.end_run()
        self.assertIsNone(self.session.current_run_start)
        self.assertEqual(len(self.session.session_runs), 0)

    def test_runs_persist_through_save_load(self) -> None:
        self.session.start_run()
        self.session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="",
        )
        self.session.end_run()
        self.session.save()

        loaded = Session.load(self.history_file)
        self.assertEqual(len(loaded.session_runs), 1)


class TestLevelProgression(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.history_file = Path(self.tmp.name) / "history.json"
        self.session = Session(self.history_file)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _record_n(self, n: int, correct: bool, difficulty: int = 1) -> None:
        for i in range(n):
            self.session.record(
                question=f"Q{i}?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
                user_answer="A" if correct else "B", correct_answer="A",
                domain="D", topic="T", explanation="",
                difficulty=difficulty,
            )

    def test_default_level_is_1(self) -> None:
        self.assertEqual(self.session.current_level, 1)

    def test_promote_on_high_accuracy(self) -> None:
        self.session.current_level = 1
        self._record_n(10, correct=True, difficulty=1)
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertEqual(new_level, 2)

    def test_demote_on_low_accuracy(self) -> None:
        self.session.current_level = 2
        self._record_n(10, correct=False, difficulty=2)
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertEqual(new_level, 1)

    def test_no_change_in_middle(self) -> None:
        self.session.current_level = 2
        for i in range(10):
            self.session.record(
                question=f"Q{i}?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
                user_answer="A" if i < 6 else "B", correct_answer="A",
                domain="D", topic="T", explanation="", difficulty=2,
            )
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertIsNone(new_level)

    def test_insufficient_data_returns_none(self) -> None:
        self.session.current_level = 1
        self._record_n(5, correct=True, difficulty=1)
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertIsNone(new_level)

    def test_no_promote_above_3(self) -> None:
        self.session.current_level = 3
        self._record_n(10, correct=True, difficulty=3)
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertIsNone(new_level)

    def test_no_demote_below_1(self) -> None:
        self.session.current_level = 1
        self._record_n(10, correct=False, difficulty=1)
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertIsNone(new_level)

    def test_set_level_records_history(self) -> None:
        self.session.current_level = 1
        self.session.set_level(2)
        self.assertEqual(self.session.current_level, 2)
        self.assertEqual(len(self.session.level_history), 1)
        self.assertEqual(self.session.level_history[0]["from"], 1)
        self.assertEqual(self.session.level_history[0]["to"], 2)

    def test_level_persists_through_save_load(self) -> None:
        self.session.current_level = 2
        self.session.set_level(3)
        self.session.save()

        loaded = Session.load(self.history_file)
        self.assertEqual(loaded.current_level, 3)
        self.assertEqual(len(loaded.level_history), 1)

    def test_only_considers_questions_at_current_level(self) -> None:
        self.session.current_level = 2
        self._record_n(10, correct=True, difficulty=1)
        self._record_n(5, correct=False, difficulty=2)
        new_level = self.session.check_level_change(0.8, 0.4, 10)
        self.assertIsNone(new_level)

    def test_record_stores_difficulty(self) -> None:
        self.session.record(
            question="Q?", choices={"A": "a", "B": "b", "C": "c", "D": "d"},
            user_answer="A", correct_answer="A",
            domain="D", topic="T", explanation="", difficulty=3,
        )
        self.assertEqual(self.session.history[0]["difficulty"], 3)


if __name__ == "__main__":
    unittest.main()
