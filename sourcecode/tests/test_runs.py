"""Run folders, checkpoints and --resume lookup."""
import os
import shutil
import tempfile
import unittest

from tests._support import quiet_logging

quiet_logging()
import config  # noqa: E402
import runs  # noqa: E402
from errors import ResumeError  # noqa: E402


class Runs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "runs")
        self.input = os.path.join(self.tmp, "Week99StoryBoard.md")
        with open(self.input, "w") as f:
            f.write("storyboard v1")
        self.rt = config.Runtime(machine="studio", mode="local", base_url="http://localhost:11434",
                                 model="m", detected_by="test")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def new(self, ident="99", kind="MAIN"):
        return runs.new_run(self.root, ident, kind, {"storyboard": self.input}, self.rt, True)

    def test_two_runs_in_same_second_get_different_folders(self):
        self.assertNotEqual(self.new().path, self.new().path)

    def test_checkpoint_round_trip(self):
        run = self.new()
        run.write_checkpoint_json("state.json", {"sections": {"MONDAY": {"Story": "x"}}})
        run.mark_done("story")
        again = runs.find_run(self.root, "MAIN", "latest", identifier="99")
        self.assertTrue(again.is_done("story"))
        self.assertEqual(again.read_checkpoint_json("state.json")["sections"]["MONDAY"]["Story"], "x")

    def test_latest_skips_complete_runs_and_other_weeks(self):
        done = self.new()
        done.set_status(runs.STATUS_COMPLETE)
        self.new(ident="98")
        with self.assertRaises(ResumeError):
            runs.find_run(self.root, "MAIN", "latest", identifier="99")

    def test_kind_must_match(self):
        five = self.new(kind="FIVEMIN")
        with self.assertRaises(ResumeError):
            runs.find_run(self.root, "MAIN", five.name)

    def test_edited_input_blocks_resume(self):
        run = self.new()
        runs.check_inputs_unchanged(run)  # unchanged: fine
        with open(self.input, "w") as f:
            f.write("storyboard v2")
        with self.assertRaises(ResumeError):
            runs.check_inputs_unchanged(run)

    def test_missing_checkpoint_file(self):
        run = self.new()
        run.mark_done("story")
        with self.assertRaises(ResumeError):
            run.read_checkpoint("state.json")


if __name__ == "__main__":
    unittest.main()
