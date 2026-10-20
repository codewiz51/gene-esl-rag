"""Warn-only lesson checks in qa_utils."""
import unittest

from tests._support import quiet_logging

quiet_logging()
import qa_utils as q  # noqa: E402


class Hints(unittest.TestCase):
    def lint(self, line, section="Grammar"):
        return q.lint_hints(f"# SUNDAY\n\n## {section}\n\n{line}\n", "t")

    def test_short_spanish_hint_ok(self):
        self.assertEqual(self.lint("1. I ___ tired. (me siento)"), [])

    def test_going_to_future_may_have_four_words(self):
        self.assertEqual(self.lint("1. I ___ ready. (me voy a sentir)"), [])
        self.assertEqual(self.lint("1. She ___ him. (le va a decir)"), [])

    def test_other_four_word_hint_flagged(self):
        self.assertEqual(len(self.lint("1. Why? (dos gotas de agua)", "Student Questions")), 1)

    def test_english_hint_flagged(self):
        self.assertEqual(len(self.lint("1. I ___ the chart. (the chart)")), 1)


class StudentLife(unittest.TestCase):
    def lint(self, line, section="Student Questions"):
        return q.lint_student_life(f"# SATURDAY\n\n## {section}\n\n{line}\n", "t")

    def test_question_putting_camy_in_students_life(self):
        self.assertEqual(len(self.lint("1. Did you spend time with Camy today? (hija)")), 1)

    def test_like_marisol(self):
        self.assertEqual(len(self.lint("1. Did you choose your family, like Marisol? (familia)")), 1)

    def test_first_person_warmup_with_camy(self):
        self.assertEqual(len(self.lint("1. I ___ lazy, just like Camy. (me siento)", "Warmup")), 1)

    def test_question_about_the_story_is_fine(self):
        self.assertEqual(self.lint("1. What does Camy need for school? (cartulina)"), [])

    def test_question_about_her_own_children_is_fine(self):
        self.assertEqual(self.lint("1. Did you spend time with your children today? (hijos)"), [])


class Direction(unittest.TestCase):
    def lint(self, es_item, en_item):
        text = ("# MONDAY\n\n## Translation Practice\n\nSpanish → English\n\n1. " + es_item +
                "\n\nEnglish → Spanish\n\n1. " + en_item + "\n")
        return q.lint_translation_direction(text, "t")

    def test_correct_directions(self):
        self.assertEqual(self.lint("Me siento mareada y el pulso está alto.",
                                   "Marisol writes his words in the chart and tells Dr. Pérez."), [])

    def test_spanish_under_english_to_spanish(self):
        self.assertEqual(len(self.lint("Me siento mareada.", "Tiene retortijones en el estómago.")), 1)

    def test_english_under_spanish_to_english(self):
        self.assertEqual(len(self.lint("She has a fever and the rash is spreading.",
                                       "She brings the cuff.")), 1)

    def test_short_unclear_item_not_flagged(self):
        self.assertEqual(self.lint("Lo vamos a atender.", "Hang tight."), [])


class StoryLength(unittest.TestCase):
    def story(self, day, words):
        return f"# {day}\n\n## Story\n\n**English:**\n\n" + "word " * words + "\n\n**Spanish:**\n\npalabra\n"

    def test_long_day_in_range(self):
        self.assertEqual(q.lint_story_length(self.story("MONDAY", 160)), [])

    def test_long_day_too_long(self):
        self.assertEqual(len(q.lint_story_length(self.story("SATURDAY", 188))), 1)

    def test_short_day_not_checked(self):
        self.assertEqual(q.lint_story_length(self.story("TUESDAY", 300)), [])


if __name__ == "__main__":
    unittest.main()
