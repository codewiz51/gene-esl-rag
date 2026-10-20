"""Storyboard parsing, including the Week 35+ verb-focus header fix."""
import os
import unittest

from tests._support import TEMPLATES, quiet_logging, read

quiet_logging()
import storyboard_utils as s  # noqa: E402
from config import ALL_DAYS  # noqa: E402

SAMPLE = """WEEK 99 – STORY BOARD

WEEKLY VERB FOCUS (reference only — old wording):
Feel – I feel fine. – Me siento bien. (sentirse)
Tell – She tells me. – Ella me dice.

# === WEEK NOTES ===
Clinic hours: 9:30 to 7.
# === END WEEK NOTES ===

# MONDAY STORYBOARD

Introduce "feel" – "sentirse"
Examples:
I feel fine. – Me siento bien.

# === VOCAB MONDAY ===
light-headed – mareado
# === END VOCAB MONDAY ===

1 - Marisol arrives.

# === STUDY NOTES MONDAY ===
Question 1: fact.
# === END STUDY NOTES MONDAY ===

# TUESDAY STORYBOARD

Light review of "feel"
2 - Second day.
"""


class VerbFocus(unittest.TestCase):
    def test_old_reference_only_header_is_read(self):
        focus = s.extract_weekly_verb_focus(SAMPLE)
        self.assertTrue(focus.startswith("Feel"))
        self.assertIn("Tell", focus)

    def test_block_stops_at_first_hash_line(self):
        self.assertNotIn("WEEK NOTES", s.extract_weekly_verb_focus(SAMPLE))
        self.assertNotIn("MONDAY", s.extract_weekly_verb_focus(SAMPLE))

    def test_plain_header_and_weekly_vocabulary_terminator(self):
        text = "WEEKLY VERB FOCUS:\ndream - x\nplan - y\n\nWEEKLY VOCABULARY (C)\nheat\n"
        self.assertEqual(s.extract_weekly_verb_focus(text), "dream - x\nplan - y")

    def test_missing_header_gives_empty(self):
        self.assertEqual(s.extract_weekly_verb_focus("no focus here"), "")


class DayBlocks(unittest.TestCase):
    def test_requirements_strip_vocab_and_study_notes(self):
        req = s.extract_day_story_requirements(SAMPLE)["MONDAY"]
        self.assertIn("Marisol arrives", req)
        self.assertNotIn("light-headed", req)
        self.assertNotIn("Question 1", req)

    def test_vocab_and_study_notes(self):
        self.assertEqual(s.extract_day_vocab_suggestions(SAMPLE)["MONDAY"], "light-headed – mareado")
        self.assertEqual(s.extract_day_study_notes(SAMPLE), {"MONDAY": "Question 1: fact."})

    def test_week_notes(self):
        self.assertEqual(s.extract_week_notes(SAMPLE), "Clinic hours: 9:30 to 7.")

    def test_day_focus_lines(self):
        focus = s.extract_day_focus(s.extract_day_story_requirements(SAMPLE))
        self.assertEqual(focus["MONDAY"], 'Introduce "feel" – "sentirse"')


class Week41Storyboard(unittest.TestCase):
    """The real Week 41 storyboard parses completely (regression guard)."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(TEMPLATES, "Week41StoryBoard.md")
        if not os.path.exists(path):
            raise unittest.SkipTest("Week41StoryBoard.md not present")
        cls.text = read(path)

    def test_every_day_has_bullets_and_vocab(self):
        req = s.extract_day_story_requirements(self.text)
        vocab = s.extract_day_vocab_suggestions(self.text)
        for day in ALL_DAYS:
            self.assertTrue(req[day].strip(), day)
            self.assertTrue(vocab[day].strip(), day)

    def test_verb_focus_and_week_notes_present(self):
        self.assertIn("Bring", s.extract_weekly_verb_focus(self.text))
        self.assertTrue(s.extract_week_notes(self.text))


if __name__ == "__main__":
    unittest.main()
