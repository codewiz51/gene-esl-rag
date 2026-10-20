"""Day splitting, validation, truncation, self-review guard (incl. qwen's C9)."""
import unittest

from tests._support import quiet_logging

quiet_logging()
import commonFunctions as c  # noqa: E402
import runlog  # noqa: E402

MAIN = c.MAIN_REQUIRED_SECTIONS


def week(days=None, sections=None, body="ok text", skip=None):
    out = []
    for d in days or c.ALL_DAYS:
        if d == skip:
            continue
        out.append(f"# {d}\n" + "".join(f"\n## {s}\n\n{body}\n" for s in (sections or MAIN)))
    return "\n".join(out)


class SplitDays(unittest.TestCase):
    def test_splits_seven_days(self):
        self.assertEqual(list(c.split_markdown_days(week())), c.ALL_DAYS)

    def test_heading_case_insensitive(self):
        self.assertIn("MONDAY", c.split_markdown_days("# Monday\ntext\n"))

    def test_duplicate_heading_keeps_longer_block_and_warns(self):  # C9
        quiet_logging()
        text = "# MONDAY\nshort\n# MONDAY\nthe longer, complete block\n"
        self.assertEqual(c.split_markdown_days(text)["MONDAY"], "# MONDAY\nthe longer, complete block")
        self.assertTrue(any("appears more than once" in w for w in runlog.collected_warnings()))

    def test_duplicate_heading_earlier_longer_block_wins(self):  # C9
        text = "# MONDAY\nthe longer, complete block\n# MONDAY\ncut\n"
        self.assertEqual(c.split_markdown_days(text)["MONDAY"], "# MONDAY\nthe longer, complete block")


class Validate(unittest.TestCase):
    def test_complete_week_has_no_structural_problems(self):
        self.assertEqual(c.validate_markdown(week(body="está bien"), "t", MAIN), [])

    def test_missing_day(self):
        problems = c.validate_markdown(week(skip="WEDNESDAY", body="está"), "t", MAIN)
        self.assertEqual(problems, ["t: WEDNESDAY is missing entirely"])

    def test_missing_and_empty_sections(self):
        text = week(body="está").replace("## Grammar\n\nestá", "## Grammar\n\n", 1)
        text = text.replace("## Student Questions\n\nestá", "", 1)
        problems = c.validate_markdown(text, "t", MAIN)
        self.assertTrue(any("missing sections: ['Student Questions']" in p for p in problems))
        self.assertTrue(any("empty section(s): ['Grammar']" in p for p in problems))

    def test_markdown_looks_truncated_last_day(self):
        self.assertTrue(c.markdown_looks_truncated(week(skip="SUNDAY"), c.ALL_DAYS))
        self.assertFalse(c.markdown_looks_truncated(week(), c.ALL_DAYS))


class ReviewGuard(unittest.TestCase):
    def setUp(self):
        self.original = week(body="Una frase de prueba con texto suficiente.")

    def test_accepts_equivalent_review(self):
        reviewed = self.original.replace("prueba", "práctica")
        out, ok = c.accept_full_week_review(self.original, reviewed, MAIN, "t")
        self.assertTrue(ok)
        self.assertEqual(out, reviewed)

    def test_rejects_empty(self):
        out, ok = c.accept_full_week_review(self.original, "", MAIN, "t")
        self.assertFalse(ok)
        self.assertEqual(out, self.original)

    def test_rejects_cut_off_review(self):
        out, ok = c.accept_full_week_review(self.original, self.original[: len(self.original) // 3], MAIN, "t")
        self.assertFalse(ok)

    def test_rejects_review_that_drops_a_section(self):
        reviewed = self.original.replace("## Examples", "## Ejemplos")
        out, ok = c.accept_full_week_review(self.original, reviewed, MAIN, "t")
        self.assertFalse(ok)


class DayHeadingFormat(unittest.TestCase):
    def test_exact_headings_pass(self):
        self.assertEqual(c.check_day_heading_format(week()), [])

    def test_wrong_level_is_reported(self):
        problems = c.check_day_heading_format(week().replace("# FRIDAY", "## FRIDAY"))
        self.assertEqual(len(problems), 1)


if __name__ == "__main__":
    unittest.main()
