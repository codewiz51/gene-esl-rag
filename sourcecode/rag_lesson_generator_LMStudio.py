import chromadb
from chromadb.config import Settings
import requests

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

CHROMA_PATH = "/Users/gene/Documents/RAG/chroma"
COLLECTIONS = ["mometrix_english", "mometrix_spanish", "esl_lessons"]
LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5"

TOP_K = 4

# ---------------------------------------------------------
# INSERT YOUR build_prompt() HERE
# ---------------------------------------------------------

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



# ---------------------------------------------------------
# RETRIEVAL
# ---------------------------------------------------------

def get_client():
    return chromadb.PersistentClient(
        path=CHROMA_PATH,
        settings=Settings(anonymized_telemetry=False)
    )

def retrieve_context(client, query):
    all_chunks = []

    for name in COLLECTIONS:
        col = client.get_collection(name)
        results = col.query(query_texts=[query], n_results=TOP_K)

        docs = results["documents"][0]
        metas = results["metadatas"][0]

        for doc, meta in zip(docs, metas):
            source = meta.get("source", "unknown")
            all_chunks.append(f"[{name} | {source}]\n{doc}\n")

    return "\n\n".join(all_chunks)


# ---------------------------------------------------------
# LM STUDIO CALL
# ---------------------------------------------------------

def call_lm_studio(prompt):
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are a helpful ESL lesson generator."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 1500
    }

    resp = requests.post(LM_STUDIO_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------
# MAIN LESSON GENERATOR
# ---------------------------------------------------------

def generate_lesson(user_request):
    print("Retrieving context...")
    client = get_client()
    context = retrieve_context(client, user_request)

    print("Building prompt...")
    prompt = build_prompt(user_request, context)

    print("Calling LM Studio...")
    lesson = call_lm_studio(prompt)

    print("\n=== GENERATED LESSON ===\n")
    print(lesson)


# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == "__main__":
    print("RAG ESL Lesson Generator")
    user_request = input("Describe the lesson you want:\n> ")
    generate_lesson(user_request)

