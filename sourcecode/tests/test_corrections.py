"""apply_corrections / BASE_CORRECTIONS / weekly corrections (incl. qwen's C1, C2)."""
import unittest

from tests._support import quiet_logging

quiet_logging()
import commonFunctions as c  # noqa: E402


def fix(text, corrections=None):
    return c.apply_corrections(text, c.BASE_CORRECTIONS if corrections is None else corrections)


class CaseOfReplacement(unittest.TestCase):  # C1
    def test_eso_es_la_vida_mid_sentence_stays_lowercase(self):
        self.assertEqual(fix("Ella dice que eso es la vida."), "Ella dice que así es la vida.")

    def test_eso_es_la_vida_at_sentence_start_is_capitalized(self):
        self.assertEqual(fix("Eso es la vida, mija."), "Así es la vida, mija.")

    def test_capital_follows_matched_text_for_other_rules(self):
        self.assertEqual(fix("Chamba, siempre chamba."), "Trabajo, siempre trabajo.")

    def test_capital_in_replacement_is_never_lowered(self):
        pairs = [(r"\bdoctora perez\b", "Dra. Pérez")]
        self.assertEqual(c.apply_corrections("llamó a la doctora perez hoy", pairs), "llamó a la Dra. Pérez hoy")

    def test_leading_punctuation_is_skipped(self):
        self.assertEqual(fix("¿Puedo tener una pera?"), "¿Me puedo comer una pera?")


class BaseCorrections(unittest.TestCase):
    def test_group_references_still_work(self):
        # These two rules rely on \1 / \2; a "literal replacement" fix for C2
        # applied to BASE_CORRECTIONS would break them.
        self.assertEqual(fix("¿puedo tener una manzana?"), "¿me puedo comer una manzana?")
        self.assertEqual(fix("Los niños se meten en el carro."), "Los niños se suben al carro.")
        self.assertEqual(fix("Ella se mete en el carro."), "Ella se sube al carro.")

    def test_calientito_all_forms(self):
        self.assertEqual(fix("mantas calientitas, café calientito, sopa calientita, panes calientitos"),
                         "mantas calientes, café caliente, sopa caliente, panes calientes")

    def test_sack_lunch(self):
        self.assertEqual(fix("un almuerzo en bolsa"), "un almuerzo para llevar")
        self.assertEqual(fix("un almuerzo en llevar"), "un almuerzo para llevar")

    def test_word_boundaries(self):
        self.assertEqual(fix("chambalo"), "chambalo")


class WeeklyCorrections(unittest.TestCase):  # C2
    @staticmethod
    def weekly(lines):
        sb = "#BEGIN DICTIONARY: WEEKLY_CORRECTIONS\n" + lines + "\n#END DICTIONARY: WEEKLY_CORRECTIONS"
        return c.parse_weekly_corrections(sb)

    def test_backslashes_are_literal(self):
        pairs = self.weekly("foo → bar\\1\nruta → C:\\temp\\x")
        self.assertEqual(c.apply_corrections("foo y ruta", pairs), "bar\\1 y C:\\temp\\x")

    def test_regex_characters_in_wrong_side_are_literal(self):
        pairs = self.weekly("presión (alta) → presión alta")
        self.assertEqual(c.apply_corrections("La presión (alta).", pairs), "La presión alta.")

    def test_normal_pair(self):
        pairs = self.weekly("manguito automático → manguito electrónico")
        self.assertEqual(c.apply_corrections("El manguito automático.", pairs), "El manguito electrónico.")

    def test_no_block_means_no_corrections(self):
        self.assertEqual(c.parse_weekly_corrections("WEEK 41"), [])


if __name__ == "__main__":
    unittest.main()
