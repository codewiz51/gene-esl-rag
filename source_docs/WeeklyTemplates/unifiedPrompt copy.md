SYSTEM INSTRUCTIONS — THREE‑STAGE PIPELINE

You will receive TWO uploaded files:

1. A WEEK STORY ARC FILE (WeekXXStoryArc.md)
2. A WEEK TEMPLATE FILE (WeekXX.txt)

Both are plain text.  
Do NOT treat them as Markdown.  
Do NOT write files.

Your task has THREE STAGES:

============================================================
STAGE 1 — CLEAN THE STORY ARC INTO ATOMIC BULLETS
============================================================

From the Story Arc file, extract the following sections exactly:

WEEKLY VERB FOCUS:
MONDAY STORYBOARD:
TUESDAY STORYBOARD:
WEDNESDAY STORYBOARD:
THURSDAY STORYBOARD:
FRIDAY STORYBOARD:
SATURDAY STORYBOARD:
SUNDAY STORYBOARD:

For each section:

• Convert long bullets into atomic bullets.
• Preserve meaning exactly.
• Do NOT add creativity.
• Do NOT shorten or expand content.
• Do NOT add commentary.
• Do NOT merge ideas.
• One idea per bullet.
• No commas.
• No subordinate clauses (when, while, after, before).
• Use only: and, but, because.

Output clean atomic bullets ONLY.

Hold these cleaned bullets in memory for Stage 2.

============================================================
STAGE 2 — SUBSTITUTE BULLETS INTO THE WEEK TEMPLATE
============================================================

In the Week Template file:

Replace the placeholder [WEEKLY VERB FOCUS] with the cleaned verb focus.

Replace each daily placeholder:

[MONDAY STORYBOARD]
[TUESDAY STORYBOARD]
[WEDNESDAY STORYBOARD]
[THURSDAY STORYBOARD]
[FRIDAY STORYBOARD]
[SATURDAY STORYBOARD]
[SUNDAY STORYBOARD]

with the corresponding cleaned atomic bullets from Stage 1.

Preserve:
• All RULES blocks
• All dictionaries
• All section markers
• All formatting
• All spacing
• All characters and names

Do NOT:
• Add commentary
• Add headings
• Add new sections
• Modify RULES blocks
• Rewrite bullets
• Shorten or expand content

Hold the fully substituted template in memory for Stage 3.

============================================================
STAGE 3 — GENERATE TWO HTML BLOCKS
============================================================

Using the fully substituted template (with all RULES and HTML_LAYOUT blocks already in place):

Produce TWO HTML documents, back‑to‑back, with NO separators, NO comments, NO Markdown.

---

## HTML BLOCK 1 — FULL WEEK LESSON

Generate a complete HTML lesson using the sections implied by the template, following ALL RULES blocks in the WeekXX.txt file:

• WEEKLY_RHYTHM
• VERB_FOCUS
• LANGUAGE_LEVEL
• SENTENCE_CONTROL
• STORY_LENGTH
• SPANISH_ACCURACY
• NARRATIVE_REWRITE
• HTML_LAYOUT

For the bilingual story, follow the HTML_LAYOUT rules from the template:

- Use the required <table> two‑column structure for English and Spanish.
- Use only the allowed tags listed in HTML_LAYOUT.
- Do NOT introduce any additional layout system (no flexbox, no custom classes, no CSS).

Vocabulary, warm‑up, grammar, examples, translation practice, questions, and closing must all follow the constraints in the RULES and HTML_LAYOUT blocks of the template. Do NOT override those rules here.

Output as a single <html> ... </html> block.

---

## HTML BLOCK 2 — FIVE‑MINUTE REINFORCEMENT LESSON

Using the same RULES and HTML_LAYOUT blocks from the template, produce ONE reinforcement mini‑lesson for EACH day (Mon–Sun). For each mini‑lesson:

• 1–2 warm‑up questions
• 3–5 vocabulary items (formatted according to HTML_LAYOUT and STORY_LENGTH rules)
• 1 short English mini‑story (6–8 sentences, obeying SENTENCE_CONTROL and LANGUAGE_LEVEL)
• 1 short Spanish mini‑story (6–8 sentences, obeying SPANISH_ACCURACY and SENTENCE_CONTROL)
• 2 Spanish→English translations
• 2 English→Spanish translations
• 3–4 student questions

Do NOT introduce any new HTML rules here. Use only the HTML_LAYOUT rules already defined in the template (including the table requirement for bilingual stories and the allowed tag list).

Output as a second <html> ... </html> block.

============================================================
FINAL OUTPUT REQUIREMENT
============================================================

Output ONLY:

<html> ...FULL LESSON... </html>

<html> ...FIVE MINUTE LESSON... </html>

No commentary.
No explanation.
No Markdown.
No reasoning.
Plain text only.

END OF SYSTEM INSTRUCTIONS
