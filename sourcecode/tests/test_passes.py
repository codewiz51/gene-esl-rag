"""Template check and pass-coverage detection."""
import os
import unittest

from tests._support import TEMPLATES, quiet_logging, read

quiet_logging()
import passes  # noqa: E402
from errors import TemplateError  # noqa: E402


class TemplateCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(TEMPLATES, "MainLessonTemplate.txt")
        if not os.path.exists(path):
            raise unittest.SkipTest("MainLessonTemplate.txt not present")
        cls.template = read(path)

    def test_real_template_has_every_block(self):
        passes.check_template(self.template)

    def test_missing_dictionary_is_reported(self):
        broken = self.template.replace("#BEGIN DICTIONARY: CUBAN_REGISTER", "#BEGIN DICTIONARY: GONE")
        with self.assertRaises(TemplateError) as cm:
            passes.check_template(broken, "t")
        self.assertIn("CUBAN_REGISTER", str(cm.exception))

    def test_missing_section_subblock_is_reported(self):
        broken = self.template.replace("\nStudent Questions:\n", "\nStudent Qs:\n")
        with self.assertRaises(TemplateError):
            passes.check_template(broken, "t")


class Coverage(unittest.TestCase):
    def test_complete_output(self):
        text = "\n".join(f"# {d}\n## Story\ntext" for d in passes.ALL_DAYS)
        self.assertEqual(passes._coverage_gaps(text, ["Story"]), [])

    def test_missing_day_and_empty_section(self):
        text = "\n".join(f"# {d}\n## Story\n" + ("" if d == "MONDAY" else "text")
                         for d in passes.ALL_DAYS if d != "SUNDAY")
        gaps = dict(passes._coverage_gaps(text, ["Story"]))
        self.assertEqual(gaps, {"MONDAY": ["Story"], "SUNDAY": ["Story"]})


if __name__ == "__main__":
    unittest.main()
