#!/usr/bin/env python3
"""
state.py

WeekState is the "print bed" - each pass writes one section's text for
every day into it. Nothing reads a section before the pass responsible
for producing it has run (pipeline.py enforces the order; this class
just stores the layers).
"""

ALL_DAYS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]

# Canonical section order for final assembly - must match MARKDOWN_LAYOUT
# rule 2 in MainLessonTemplate.txt.
SECTION_ORDER = [
    "Warmup",
    "Vocabulary",
    "Story",
    "Grammar",
    "Examples",
    "Translation Practice",
    "Student Questions",
]


class WeekState:
    def __init__(self):
        # sections[day][section_name] = finished markdown text for that
        # section (NOT including the "## Heading" line - assemble() adds it)
        self.sections = {day: {} for day in ALL_DAYS}

    def set_section(self, day, section_name, text):
        day = day.upper()
        if day not in self.sections:
            raise ValueError(f"Unknown day: {day}")
        self.sections[day][section_name] = text.strip()

    def get_section(self, day, section_name):
        return self.sections.get(day.upper(), {}).get(section_name, "")

    def has_section(self, day, section_name):
        return bool(self.get_section(day, section_name))

    def missing_sections(self, day):
        return [s for s in SECTION_ORDER if not self.has_section(day, s)]

    def assemble_day(self, day):
        day = day.upper()
        parts = [f"# {day}", ""]
        for section in SECTION_ORDER:
            text = self.get_section(day, section)
            if not text:
                print(f"WARNING: {day} missing '{section}' at assembly time - leaving heading with no body.")
            parts.append(f"## {section}")
            parts.append("")
            parts.append(text)
            parts.append("")
        return "\n".join(parts).strip()

    def assemble_week(self, days=None):
        days = days or ALL_DAYS
        return "\n\n".join(self.assemble_day(d) for d in days) + "\n"
