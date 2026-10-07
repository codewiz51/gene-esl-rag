# Main Lesson Template (Claude)

Claude's spec for the weekly Main lesson. The qwen files (MainLessonTemplate.txt, promptMain.md) stay as the offline backup and are not used here. The storyboard wins when it conflicts with this file.

## The learners

Cuban women, 28-36, mothers of one or two children, green card holders. University-trained in Cuba (some were headed for medicine, law, economics); now cleaning houses and similar work far below their training, often underpaid. A2/A2+ after about 30 weeks. Working toward clinic jobs (medical assistant). Their lives are brittle: health care, food, rent, electricity. The lessons must be useful at work and must not overwhelm a tired working mother.

## The week

Three verbs per week, given in the storyboard's WEEKLY VERB FOCUS.

- Monday (long day): low cognitive load; students likely worked Sunday. Introduce verb 1. In-person class.
- Tuesday (short day): no class, self study. Introduce verb 2. Everyday errands: grocery store, bills, insurance, internet, kids' schoolwork.
- Wednesday (short day): no class, self study. Light review of verbs 1 and 2. Same everyday settings as Tuesday.
- Thursday (long day): heavier. A clinic patient case built on a Mometrix CMA study guide topic. Introduce verb 3.
- Friday and Saturday (long days): heaviest. Review all three verbs through examples and grammar. In-person classes.
- Sunday (short day): Marisol remembers the week. Past tense, a quiet moment, no new events. In-person class.

Mix in personal, non-clinic storylines now and then, the way real life goes.

## Language level

- A2/A2+ throughout. The week's medical vocabulary may be B1; the prose around it stays A2.
- Tenses: simple present, simple past, going to, will, can, should, simple first conditional. No present perfect, past perfect, or complex conditionals.
- Story prose reads like a graded reader: short, plain sentences, one idea each. No dashes, no figurative language, no long medical explanations.
- No Spanish words in English narration (uncle, not tío). Spanish may appear in English dialogue only when the scene is about that word.
- Spanish is natural, spoken Cuban Spanish. Translate what the English means in everyday talk, not the words. See Cuban register below.

## Lesson layout

Every day uses exactly this skeleton, in this order. Day headings are `# MONDAY` etc.; one blank line between days, no `---`. "**English:**" and "**Spanish:**" are the only bold text. No `###`, tables, italics, or bullets; the only nested list is the a) b) c) choices under Student Questions. Leave a blank line between a label and the list after it (pandoc merges them otherwise).

```
# MONDAY

## Warmup

1. I ___ ... (hint)

## Vocabulary

1. English word – palabra en español

## Story

**English:**

Paragraphs.

**Spanish:**

Paragraphs.

## Grammar

Explanation paragraph.

Pattern Practice:

1. ... ___ ... (hint)

## Examples

1. Sentence.
2. Name and Name talk at the front desk:
Name: "Line."
Name: "Line."

## Translation Practice

Spanish → English

1. ...

English → Spanish

1. ...

## Student Questions

1. Question?
   a) Choice.
   b) Choice.
   c) Choice.
```

## Section rules

Counts are long day / short day. Long days: Mon, Thu, Fri, Sat. Short days: Tue, Wed, Sun.

Warmup (1-3 / 1-2)
- Blanks test the week's verbs. At least one first-person prompt where the student talks about herself ("I ___ before work.").

Vocabulary (4-6 / 3-5)
- Exactly the day's storyboard VOCAB block, same items, same order, same formal/casual pairs. Word or short phrase pairs, not sentences.

Story
- Long days 140-180 English words; short days 6-8 sentences (9 is fine, 5 is not). Do not pad.
- Long days: one main event, one moment of Marisol's interiority, one small conflict or surprise (a wrong cuff, a missed turn, a spilled coffee, not a crisis), one sensory detail, one line of direct speech. One patient per main clinical interaction, except Friday.
- Short days: one character voice moment. Even a recap is Marisol living it (a porch, a drive), not a list.
- Events come from the storyboard bullets only. Write them as a story, not a transcript of the bullets.
- Humor when it fits naturally; none in a tense story.
- Spanish half: a faithful, natural Cuban translation of the English.

Grammar (Pattern Practice 3 / 2)
- Explanation in Cuban Spanish, max 3 sentences, quoted English verbs and examples kept in English. Include the -s rule for he/she/it (has for have) with a short Spanish note.
- Pattern Practice frames use the week's verb focus.

Examples (4-6 / 3-4)
- Follow the storyboard's example sentences and verb counts when it gives them.
- One dialogue, 4-6 lines, characters from the list below, showing the day's grammar in natural use. At least one line that is not textbook (a joke, a sigh, "well..."). Format: `Name: "Line."`, one line per turn.

Translation Practice (S→E 6 / 2, E→S 2)
- Every item is a sentence copied from that day's story: Spanish items from the Spanish story, English items from the English story. Sentence only, no answer.
- At least one professional, clinic-relevant reading item in S→E; at least one clinic phrase in E→S.

Student Questions (4-6 / 3-4)
- Multiple choice, a) b) c), choices indented three spaces under the question. No hints. Students score about 7/10 and miss mostly fill-in items, so recognition comes before production for now.
- Real questions ending in "?". At least one asks the student about her own life. Questions may assume she works in a clinic.
- Story questions: exactly one correct choice. Wrong choices are plausible and come from the lesson (another day's detail, a wrong number, the wrong person), not tricks. Same form and similar length for all three. Vary the position of the correct answer.
- Personal questions: all three choices are valid answers written as short first-person sentences she could say ("Yes, I felt very nervous."), so the choices model the answer.

Hints (Warmup, Pattern Practice)
- One hint per blank, in parentheses at the end: the Spanish form of the answer in the right person and tense (tomo, toma, dio, tomaré). Never the English answer.
- Each blank has exactly one correct answer, and the filled sentence is correct English.

## Characters

- Marisol – clinic medical assistant, single mother. Mild interest in Rod.
- Camy – Marisol's daughter, 11, friends with Donna.
- Marisa – neighbor, energetic, walks with Marisol.
- Donna – Marisa's daughter, 12, friends with Camy.
- Dr. Doris Pérez – clinic doctor. "Dr. Pérez" in English text; "la Dra. Pérez" / "la doctora" in Spanish.
- Rosie – coworker.
- Letia – LPN.
- Amanda – receptionist; does stand-up comedy in local clubs.
- Rod – UPS driver, interested in Marisol.
- Jason – Dr. Pérez's son, born in the US; part-time bookkeeper, handles insurance coding.
- Carla – part-time medical assistant.
- Crystal – new Physician Assistant, covers weekends.
- Ernesto – Marisol's brother, Cuban immigrant, married to Virginia.
- Jorge – Marisol's oldest brother, late 40s, lives in Cuba with his wife in a nice house near where they grew up. Use family details sparingly.
- Virginia – Marisol's sister-in-law; sometimes picks up Camy and Donna from school.

Marisol and Rod: a light, occasional beat, never a storyline and never the main event. A missed chance to talk, a rushed wave, a text she means to answer. It should show, with a smile, how hard dating is on a single mother's schedule. The reader is in the same situation and should see herself in it.

Scope of practice: Marisol measures, records, and relays. She never diagnoses.

## Cuban register

- pa', pa'l, pa' la: keep (informal).
- carpool: "un rutero" or "alquilar/pagar un carro", not "irse en carro juntos".
- lunchbox: "lonchera" (the container, not the meal). Sack lunch: "almuerzo en bolsa".
- syncope: "desvanecimiento" / "desmayo".
- job: "trabajo", never "chamba".
- refill a prescription: "renovar la receta" / "renovación de la receta", never "recarga" (that is a phone top-up).
- has a fever: "tiene fiebre" / "tiene calentura", never "está caliente" or "se siente caliente" about a person.
- fussy (a child): "inquieto" / "llorón".
- discharge: "dar de alta" is the provider discharging the patient. A patient ending care is "despedir al proveedor" / "dejar al proveedor".
- work through the questions: "repasar las preguntas".
- Everyday Cuban words to use where they fit: parqueo, tranque, planilla, meseta, portal, gaveta, embullada, "le toca" (for whose turn it is).

## Conventions

- No English titles inside Spanish sentences ("el señor Navarro", not "Mr. Navarro"), and no Spanish titles inside English ones.
- English teaching phrases stay in English inside the Spanish story when the scene is about the English itself ("hang tight", "I'll look into it", "chill").
- iPad stays iPad. Straight double quotes, not «».
