def build_prompt(user_request, context):
    system_instructions = (
        "You are an ESL teacher creating bilingual English–Spanish lessons for adult learners. "
        "Use the retrieved context to stay accurate to the source materials. "
        "Follow the exact Week 27 curriculum structure provided below. "
        "Use only the character Marisol. "
        "Do not introduce new characters, new plot elements, or new vocabulary themes. "
        "Use Gene’s teaching voice: clear, friendly, structured, bilingual, practical, and encouraging."
    )

    WEEK_27_TEMPLATE = """
WEEK 27 ESL CURRICULUM TEMPLATE
Weekly Verb Focus: do vs make
Weekly Theme: Health and Wellness woven into every day’s story

MONDAY:
Story: Marisol counsels a 36-year-old female patient (one child, overweight, smokes, high blood pressure, possible alcohol use).
Vocabulary: Exercise, Smoking, Substance Abuse, Nutrition, Weight Control.
Language focus: do exercise, make changes, make a plan.

TUESDAY:
Story: Marisol takes a computer-based training course on Nutrition Elements. Coworkers tease her when she misses questions.
Vocabulary: Fats, Carbohydrates, Proteins, Vitamins, Minerals.
Language focus: make a mistake, do the training again.

WEDNESDAY (Review Day):
Follow the Week 26 review format:
- Warm-up
- Vocabulary review
- Verb focus review
- Short story recap
- Translation practice
- Role-play

THURSDAY:
Story: Marisol assesses an older woman with stooped back and bruises. Screening for osteoporosis and domestic violence.
Vocabulary: Use Column One topics from COMMON SCREENING MEASURES AND PREVENTIVE CARE (blood pressure, cholesterol, bone density, fall risk, vision screening, hearing screening, depression screening, domestic violence screening).
Language focus: do screenings, make a safety plan.

FRIDAY:
Story: Marisol accompanies a coworker seeking smoking cessation help. Coworker coughed blood; TB test requested.
Vocabulary: Planned cessation, Support groups, Cold-turkey, Medication-assisted.
Language focus: do a TB test, make a plan to quit.

SATURDAY:
Story: Marisol works noon–7. Kids wake her wanting pancakes and bacon. She makes frozen pancakes; kids prefer homemade. Clinic calls asking her to come early. Doctor asks her to remove 8 sutures; she is nervous.
Vocabulary: Pancakes, Bacon, Frozen, Childcare, Sutures, Procedure.
Language focus: make breakfast, do a procedure.

SUNDAY (Review Day):
Follow Week 26 review format:
- Warm-up
- Vocabulary review
- Verb focus review
- Story summaries
- Translation practice
- Role-play
"""

    TASK_INSTRUCTIONS = (
        "TASK:\n"
        "Using the Week 27 template above, generate the specific lesson requested by the user. "
        "Include:\n"
        "- Warm-up (English + Spanish)\n"
        "- Vocabulary list (English → Spanish)\n"
        "- Weekly verb focus (do vs make)\n"
        "- Short bilingual story using ONLY Week 27 plot elements\n"
        "- Grammar point (A2 level)\n"
        "- Example sentences (English + Spanish)\n"
        "- Mini translation practice\n"
        "- Role-play activity\n"
        "- Student practice questions\n"
        "- Closing summary\n\n"
        "Do not invent new characters, new events, or new vocabulary. "
        "Stay strictly within the Week 27 storyline and vocabulary themes."
    )

    prompt = (
        f"{system_instructions}\n\n"
        f"WEEK 27 TEMPLATE:\n{WEEK_27_TEMPLATE}\n\n"
        f"USER REQUEST:\n{user_request}\n\n"
        f"RETRIEVED CONTEXT:\n{context}\n\n"
        f"{TASK_INSTRUCTIONS}"
    )

    return prompt

