#!/usr/bin/env python3
"""
qa_utils.py - cheap, no-model checks that print warnings about a finished
lesson. They never change the lesson text.
"""

import logging
import re

log = logging.getLogger("esl")

_ENGLISH_HINT_WORDS = {
    "the", "a", "an", "to", "of", "and", "is", "are", "it", "back", "tight", "hang", "hold",
    "get", "give", "have", "take", "check", "reading", "patient", "doctor", "claim", "chart",
}

# ir a + infinitive, with an optional object/reflexive pronoun in front:
# "voy a traer", "me voy a sentir", "le va a decir", "nos vamos a ir".
_IR_A_FUTURE = re.compile(
    r"^(?:(?:me|te|se|le|les|lo|la|los|las|nos)\s+)?(?:voy|vas|va|vamos|van)\s+a\s+\w+(?:r|rse|rlo|rla|rle)$",
    re.IGNORECASE,
)


def lint_hints(markdown_text, label="lesson"):
    """Warn about hints that are too long or look English. Hint = last (...) on a numbered line."""
    warnings = []
    day = "?"
    section = ""
    for line in markdown_text.splitlines():
        m_day = re.match(r"^#\s+([A-Z]+)\s*$", line)
        if m_day:
            day = m_day.group(1)
            continue
        m_sec = re.match(r"^##\s+(.*)$", line)
        if m_sec:
            section = m_sec.group(1).strip()
            continue
        if section not in ("Warmup", "Grammar", "Student Questions"):
            continue
        m = re.match(r"^\s*\d+[.)]\s+.*\(([^()]+)\)\s*$", line)
        if not m:
            continue
        hint = m.group(1).strip()
        words = hint.split()
        # The Spanish "going to" future is one fixed phrase but can take four
        # words with a pronoun: "(me voy a sentir)", "(le va a decir)". Allow
        # it (Oct 20, 2026: the 3-word limit flagged correct future hints).
        limit = 4 if _IR_A_FUTURE.match(hint) else 3
        if len(words) > limit:
            warnings.append(f"{day} {section}: hint has {len(words)} words: ({hint})")
        elif all(w.lower() in _ENGLISH_HINT_WORDS for w in words):
            warnings.append(f"{day} {section}: hint looks English: ({hint})")
    for w in warnings:
        log.warning(f"HINT [{label}]: {w}")
    if not warnings:
        log.info(f"Hint check [{label}]: no problems found.")
    return warnings


# ---------------------------------------------------------------------------
# Added Oct 20, 2026 after the Week 41 review. Warn only, like lint_hints().
# ---------------------------------------------------------------------------

# Marisol's own family and friends. A question or first-person prompt that
# puts one of these in the STUDENT's life ("Did you spend time with Camy
# today?") treats the student as Marisol. Coworkers are not listed: the
# clinic and its staff are real places the students work in.
PERSONAL_CAST = ["Camy", "Donna", "Marisa", "Ernesto", "Virginia", "Jorge"]

_SECOND_PERSON = re.compile(r"\b(you|your|yours)\b", re.IGNORECASE)
_FIRST_PERSON = re.compile(r"^\s*\d+[.)]\s+(I|My|my)\b")


def _sections(markdown_text):
    """Yield (day, section, line) for every line under a '## ' section."""
    day, section = "?", ""
    for line in markdown_text.splitlines():
        m_day = re.match(r"^#\s+([A-Z]+)\s*$", line)
        if m_day:
            day, section = m_day.group(1), ""
            continue
        m_sec = re.match(r"^##\s+(.*?)\s*$", line)
        if m_sec:
            section = m_sec.group(1)
            continue
        yield day, section, line


def lint_student_life(markdown_text, label="lesson"):
    """
    Warn when a Student Questions or Warmup line addressed to the student
    ("you" / "I") treats Marisol's family as hers, or says "like Marisol".
    Questions ABOUT the story ("What does Camy need?") are not flagged.
    """
    warnings = []
    names = re.compile(r"\b(" + "|".join(PERSONAL_CAST) + r")\b")
    for day, section, line in _sections(markdown_text):
        if section not in ("Student Questions", "Warmup"):
            continue
        if not re.match(r"^\s*\d+[.)]\s+", line):
            continue
        addressed = _SECOND_PERSON.search(line) or _FIRST_PERSON.match(line)
        if not addressed:
            continue
        if names.search(line) or re.search(r"\blike Marisol\b", line, re.IGNORECASE):
            warnings.append(f"{day} {section}: treats Marisol's life as the student's: {line.strip()}")
    for w in warnings:
        log.warning(f"STUDENT [{label}]: {w}")
    return warnings


_SPANISH_WORDS = {
    "el", "la", "los", "las", "que", "de", "del", "y", "en", "es", "está", "están", "se", "un", "una",
    "por", "para", "con", "su", "sus", "le", "lo", "al", "muy", "pero", "porque", "tiene", "hay",
}
_ENGLISH_WORDS = {
    "the", "an", "is", "are", "and", "to", "of", "in", "she", "he", "her", "his", "i", "you", "it",
    "with", "for", "at", "was", "my", "not", "has", "have", "will", "does", "did",
}


def _looks(text):
    """'es', 'en' or '' (can't tell) for one translation item.

    Common function words decide first. Accents count as Spanish only
    outside capitalized words, so names like "Dr. Pérez" or "Andrés"
    don't make an English sentence look Spanish.
    """
    words = re.findall(r"[A-Za-záéíóúñÁÉÍÓÚÑ']+", text)
    lower = [w.lower() for w in words]
    es = sum(w in _SPANISH_WORDS for w in lower)
    en = sum(w in _ENGLISH_WORDS for w in lower)
    if "¿" in text or "¡" in text:
        es += 2
    es += sum(1 for w in words if w[0].islower() and re.search(r"[áéíóúñ]", w))
    if es >= 2 and es > en:
        return "es"
    if en >= 2 and en > es:
        return "en"
    return ""


def lint_translation_direction(markdown_text, label="lesson"):
    """
    Warn when an item under 'Spanish → English' looks English, or an item
    under 'English → Spanish' looks Spanish. The student translates FROM
    the label's first language, so that is the language the item must be in.
    """
    warnings = []
    part = None
    for day, section, line in _sections(markdown_text):
        if section != "Translation Practice":
            part = None
            continue
        s = line.strip()
        if re.match(r"^Spanish\s*→\s*English", s):
            part = "es"
            continue
        if re.match(r"^English\s*→\s*Spanish", s):
            part = "en"
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", s)
        if not (m and part):
            continue
        got = _looks(m.group(1))
        if got and got != part:
            want = "Spanish" if part == "es" else "English"
            warnings.append(f"{day}: item under '{'Spanish → English' if part == 'es' else 'English → Spanish'}' "
                            f"is not in {want}: {m.group(1)}")
    for w in warnings:
        log.warning(f"DIRECTION [{label}]: {w}")
    return warnings


# MainLessonTemplate STORY_LENGTH: long days 140-180 English words.
LONG_DAYS = ("MONDAY", "THURSDAY", "FRIDAY", "SATURDAY")
LONG_DAY_WORDS = (140, 180)


def lint_story_length(markdown_text, label="main lesson"):
    """Warn when a long day's English story is outside 140-180 words."""
    warnings = []
    parts = re.split(r"(?m)^#\s+(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\s*$", markdown_text)
    for i in range(1, len(parts), 2):
        day, body = parts[i], parts[i + 1]
        if day not in LONG_DAYS:
            continue
        m = re.search(r"\*\*English:\*\*(.*?)\*\*Spanish:\*\*", body, re.S)
        if not m:
            continue
        n = len(m.group(1).split())
        lo, hi = LONG_DAY_WORDS
        if not lo <= n <= hi:
            warnings.append(f"{day}: English story is {n} words (template: {lo}-{hi})")
    for w in warnings:
        log.warning(f"LENGTH [{label}]: {w}")
    return warnings
