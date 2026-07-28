import os
import sqlite3
import json
import asyncio
from backend.models import get_db_connection

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DATA_DIR = os.path.join(BASE_DIR, "frontend", "data")

# =========================================================================
# GOETHE-INSTITUT CERTIFIED GRAMMAR LAB DATASET (CEFR A1, A2, B1)
# =========================================================================

GRAMMAR_DATASET = [
  # --- A1 LEVEL GRAMMAR ---
  {
    "id": "g_a1_001",
    "german": "Ich kaufe keinen Apfel, sondern eine Birne.",
    "english": "I am not buying an apple, but a pear.",
    "urdu": "میں سیب نہیں بلکہ ناشپاتی خرید رہا ہوں۔",
    "cefr": "A1",
    "topic": "Negation (nicht vs kein)",
    "rule_hint": "'keinen' negates the masculine direct object 'Apfel' in the accusative case."
  },
  {
    "id": "g_a1_002",
    "german": "Heute fahre ich nach Berlin.",
    "english": "Today I am driving to Berlin.",
    "urdu": "آج میں برلن جا رہا ہوں۔",
    "cefr": "A1",
    "topic": "Sentence Structure (V2 Rule)",
    "rule_hint": "In German main clauses, the conjugated verb 'fahre' MUST occupy position 2, causing subject-verb inversion."
  },
  {
    "id": "g_a1_003",
    "german": "Er hat einen neuen Hund.",
    "english": "He has a new dog.",
    "urdu": "اس کے پاس ایک نیا کتا ہے۔",
    "cefr": "A1",
    "topic": "Akkusativ Case Direct Objects",
    "rule_hint": "The masculine noun 'Hund' changes from 'ein' to 'einen' in the accusative case as a direct object."
  },
  {
    "id": "g_a1_004",
    "german": "Wir müssen jeden Tag Deutsch lernen.",
    "english": "We must learn German every day.",
    "urdu": "ہمیں ہر روز جرمن سیکھنی چاہیے۔",
    "cefr": "A1",
    "topic": "Core Modal Verbs (müssen)",
    "rule_hint": "The conjugated modal verb 'müssen' takes position 2, and pushes the main infinitive 'lernen' to the end."
  },
  {
    "id": "g_a1_005",
    "german": "Kannst du mir bitte helfen?",
    "english": "Can you please help me?",
    "urdu": "کیا آپ برائے مہربانی میری مدد کر سکتے ہیں؟",
    "cefr": "A1",
    "topic": "Core Modal Verbs (können)",
    "rule_hint": "In yes/no questions, the conjugated modal verb 'kannst' moves to position 1."
  },
  {
    "id": "g_a1_006",
    "german": "Das ist mein Vater und das ist meine Mutter.",
    "english": "That is my father and that is my mother.",
    "urdu": "یہ میرے والد ہیں اور یہ میری والدہ ہیں۔",
    "cefr": "A1",
    "topic": "Possessive Articles (mein/meine)",
    "rule_hint": "Feminine nouns like 'Mutter' require the possessive ending -e ('meine')."
  },
  {
    "id": "g_a1_007",
    "german": "Ich trinke nicht Kaffee, sondern Tee.",
    "english": "I am not drinking coffee, but tea.",
    "urdu": "میں کافی نہیں بلکہ چائے پی رہا ہوں۔",
    "cefr": "A1",
    "topic": "Negation (nicht vs kein)",
    "rule_hint": "'nicht' is used when contrasting specific actions or specific nouns with 'sondern'."
  },
  {
    "id": "g_a1_008",
    "german": "Sie sucht ihren Schlüssel.",
    "english": "She is looking for her key.",
    "urdu": "وہ اپنی چابی تلاش کر رہی ہے۔",
    "cefr": "A1",
    "topic": "Possessive Articles in Akkusativ",
    "rule_hint": "Masculine 'Schlüssel' takes the accusative possessive ending -en ('ihren')."
  },
  {
    "id": "g_a1_009",
    "german": "Morgen besuchen wir unsere Großeltern.",
    "english": "Tomorrow we are visiting our grandparents.",
    "urdu": "کل ہم اپنے دادا دادی سے ملنے جا رہے ہیں۔",
    "cefr": "A1",
    "topic": "Sentence Structure & Plural Akkusativ",
    "rule_hint": "Adverb 'Morgen' takes Position 1; verb 'besuchen' takes Position 2."
  },
  {
    "id": "g_a1_010",
    "german": "Ich möchte ein Glas Wasser trinken.",
    "english": "I would like to drink a glass of water.",
    "urdu": "میں ایک گلاس پانی پینا چاہتا ہوں۔",
    "cefr": "A1",
    "topic": "Core Modal Verbs (möchten)",
    "rule_hint": "Modal verb 'möchte' goes to position 2 and main verb 'trinken' goes to the clause end."
  },

  # --- A2 LEVEL GRAMMAR ---
  {
    "id": "g_a2_001",
    "german": "Er stellt das Buch auf den Tisch, weil er lesen will.",
    "english": "He puts the book on the table because he wants to read.",
    "urdu": "وہ کتاب میز پر رکھتا ہے کیونکہ وہ پڑھنا چاہتا ہے۔",
    "cefr": "A2",
    "topic": "Two-Way Prepositions & Subordinate Clauses",
    "rule_hint": "'auf den Tisch' takes Akkusativ for direction/movement, and 'weil' pushes the conjugated modal verb 'will' to the end."
  },
  {
    "id": "g_a2_002",
    "german": "Ich fahre jeden Morgen mit dem Bus zur Arbeit.",
    "english": "I ride the bus to work every morning.",
    "urdu": "میں ہر صبح بس کے ذریعے کام پر جاتا ہوں۔",
    "cefr": "A2",
    "topic": "Strict Dativ Prepositions (mit, zu)",
    "rule_hint": "Preposition 'mit' ALWAYS requires Dative ('dem Bus') and 'zu' requires Dative ('zur Arbeit')."
  },
  {
    "id": "g_a2_003",
    "german": "Gestern bin ich um sieben Uhr aufgestanden.",
    "english": "Yesterday I got up at seven o'clock.",
    "urdu": "کل میں سات بجے اٹھا تھا۔",
    "cefr": "A2",
    "topic": "Perfekt Tense (sein auxiliary) & Separable Verbs",
    "rule_hint": "Verbs of motion/state-change like 'aufstehen' take 'sein' (bin) as auxiliary in Perfekt."
  },
  {
    "id": "g_a2_004",
    "german": "Sie ruft ihre Mutter jeden Abend an.",
    "english": "She calls her mother every evening.",
    "urdu": "وہ ہر شام اپنی ماں کو فون کرتی ہے۔",
    "cefr": "A2",
    "topic": "Separable Prefix Verbs (anrufen)",
    "rule_hint": "The prefix 'an-' separates from 'rufen' and moves to the very end of the main clause."
  },
  {
    "id": "g_a2_005",
    "german": "Das Buch liegt auf dem Tisch.",
    "english": "The book is lying on the table.",
    "urdu": "کتاب میز پر پڑی ہے۔",
    "cefr": "A2",
    "topic": "Two-Way Prepositions (Location = Dativ)",
    "rule_hint": "Because 'liegen' describes a stationary location (where?), 'auf' takes Dative ('dem Tisch')."
  },
  {
    "id": "g_a2_006",
    "german": "Ich weiß, dass du gestern viel gearbeitet hast.",
    "english": "I know that you worked a lot yesterday.",
    "urdu": "میں جانتا ہوں کہ آپ نے کل بہت کام کیا تھا۔",
    "cefr": "A2",
    "topic": "Subordinate Clauses with 'dass'",
    "rule_hint": "Conjunction 'dass' creates a subordinate clause, pushing conjugated auxiliary 'hast' to the end."
  },
  {
    "id": "g_a2_007",
    "german": "Wir haben das schöne Wetter genossen.",
    "english": "We enjoyed the beautiful weather.",
    "urdu": "ہم نے خوبصورت موسم کا لطف اٹھایا۔",
    "cefr": "A2",
    "topic": "Perfekt Tense (haben auxiliary)",
    "rule_hint": "Transitive verbs like 'genießen' take 'haben' as auxiliary in Perfekt."
  },
  {
    "id": "g_a2_008",
    "german": "Er wohnt bei seinen Eltern seit einem Jahr.",
    "english": "He has been living with his parents for a year.",
    "urdu": "وہ ایک سال سے اپنے والدین کے ساتھ رہ رہا ہے۔",
    "cefr": "A2",
    "topic": "Strict Dativ Prepositions (bei, seit)",
    "rule_hint": "'bei' and 'seit' strictly govern Dative ('seinen Eltern', 'einem Jahr')."
  },
  {
    "id": "g_a2_009",
    "german": "Der Zug kommt um 08:30 Uhr am Bahnhof an.",
    "english": "The train arrives at the station at 08:30.",
    "urdu": "ٹرین 08:30 بجے اسٹیشن پر پہنچتی ہے۔",
    "cefr": "A2",
    "topic": "Separable Prefix Verbs (ankommen)",
    "rule_hint": "Separable prefix 'an' moves to clause final position in present tense."
  },
  {
    "id": "g_a2_010",
    "german": "Wir gehen ins Kino, weil der Film sehr interessant ist.",
    "english": "We are going to the cinema because the movie is very interesting.",
    "urdu": "ہم سینما جا رہے ہیں کیونکہ فلم بہت دلچسپ ہے۔",
    "cefr": "A2",
    "topic": "Subordinate Clauses with 'weil'",
    "rule_hint": "'weil' sends verb 'ist' to the end of the subordinate clause."
  },

  # --- B1 LEVEL GRAMMAR ---
  {
    "id": "g_b1_001",
    "german": "Obwohl es stark regnete, ging er ohne Schirm spazieren.",
    "english": "Although it rained heavily, he went for a walk without an umbrella.",
    "urdu": "اگرچہ شدید بارش ہو رہی تھی، وہ چھتری کے بغیر سیر کے لیے گیا۔",
    "cefr": "B1",
    "topic": "Subordinate Clauses (obwohl)",
    "rule_hint": "'obwohl' introduces a concessive clause pushing verb 'regnete' to the end; the main clause starts with verb 'ging'."
  },
  {
    "id": "g_b1_002",
    "german": "Das Haus wird von dem erfahrenen Bauarbeiter gebaut.",
    "english": "The house is being built by the experienced construction worker.",
    "urdu": "گھر تجربہ کار تعمیراتی کارکن کے ذریعہ بنایا جا رہا ہے۔",
    "cefr": "B1",
    "topic": "Passive Voice in Present Tense (Passiv Präsens)",
    "rule_hint": "Passive voice is formed with conjugated 'werden' in Pos 2 + agent ('von' + Dativ) + Partizip II ('gebaut') at the end."
  },
  {
    "id": "g_b1_003",
    "german": "Ich freue mich sehr über das Geschenk, das du mir gegeben hast.",
    "english": "I am very happy about the gift that you gave me.",
    "urdu": "میں اس تحفے سے بہت خوش ہوں جو آپ نے مجھے دیا ہے۔",
    "cefr": "B1",
    "topic": "Reflexive Verbs & Relative Clauses",
    "rule_hint": "'sich freuen über' takes accusative reflexive pronoun 'mich'; relative pronoun 'das' refers back to neuter 'Geschenk'."
  },
  {
    "id": "g_b1_004",
    "german": "Trotz des schlechten Wetters machten wir einen Ausflug.",
    "english": "Despite the bad weather, we took a trip.",
    "urdu": "خراب موسم کے باوجود ہم سیر کے لیے گئے۔",
    "cefr": "B1",
    "topic": "Genitive Case & Prepositions (trotz)",
    "rule_hint": "Preposition 'trotz' strictly governs the Genitive case ('des schlechten Wetters')."
  },
  {
    "id": "g_b1_005",
    "german": "Der Mann, dessen Auto gestohlen wurde, rief die Polizei an.",
    "english": "The man whose car was stolen called the police.",
    "urdu": "وہ آدمی جس کی کار چوری ہو گئی تھی، اس نے پولیس کو فون کیا۔",
    "cefr": "B1",
    "topic": "Genitive Relative Pronouns (dessen)",
    "rule_hint": "'dessen' is the possessive genitive relative pronoun for masculine singular antecedent ('der Mann')."
  },
  {
    "id": "g_b1_006",
    "german": "Während der Konferenz durften die Teilnehmer keine Fotos machen.",
    "english": "During the conference, participants were not allowed to take photos.",
    "urdu": "کانفرنس کے دوران شرکاء کو تصاویر لینے کی اجازت نہیں تھی۔",
    "cefr": "B1",
    "topic": "Genitive Prepositions (während)",
    "rule_hint": "'während' strictly requires the Genitive case ('der Konferenz')."
  },
  {
    "id": "g_b1_007",
    "german": "Falls Sie Fragen haben, können Sie mich jederzeit anrufen.",
    "english": "If you have any questions, you can call me anytime.",
    "urdu": "اگر آپ کے کوئی سوالات ہیں تو آپ مجھے کسی بھی وقت فون کر سکتے ہیں۔",
    "cefr": "B1",
    "topic": "Conditional Subordinate Clauses (falls)",
    "rule_hint": "Conditional conjunction 'falls' puts 'haben' at clause end; main clause begins immediately with modal 'können'."
  },
  {
    "id": "g_b1_008",
    "german": "Er wäscht sich vor dem Essen die Hände.",
    "english": "He washes his hands before eating.",
    "urdu": "وہ کھانے سے پہلے ہاتھ دھوتا ہے۔",
    "cefr": "B1",
    "topic": "Reflexive Verbs with Dativ Pronouns",
    "rule_hint": "When a specific body part ('die Hände') is the direct object, the reflexive pronoun becomes Dativ ('sich')."
  },
  {
    "id": "g_b1_009",
    "german": "Wegen der Verspätung des Zuges verpasste sie den Anschluss.",
    "english": "Because of the train delay, she missed the connection.",
    "urdu": "ٹرین میں تاخیر کی وجہ سے وہ کنیکٹنگ ٹرین سے رہ گئی۔",
    "cefr": "B1",
    "topic": "Genitive Prepositions (wegen)",
    "rule_hint": "'wegen' governs Genitive case ('der Verspätung des Zuges')."
  },
  {
    "id": "g_b1_010",
    "german": "Das Problem, über das wir gesprochen haben, ist gelöst.",
    "english": "The problem about which we spoke has been solved.",
    "urdu": "وہ مسئلہ جس کے بارے میں ہم نے بات کی تھی حل ہو گیا ہے۔",
    "cefr": "B1",
    "topic": "Prepositional Relative Clauses",
    "rule_hint": "Relative clause incorporates preposition + relative pronoun ('über das'), pushing conjugated 'haben' to the end."
  }
]

def init_grammar_schema():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS grammar_sentences (
        id TEXT PRIMARY KEY,
        german TEXT NOT NULL,
        english TEXT NOT NULL,
        urdu TEXT NOT NULL,
        cefr TEXT NOT NULL,
        topic TEXT NOT NULL,
        rule_hint TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_grammar_cefr ON grammar_sentences(cefr);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_grammar_topic ON grammar_sentences(topic);")

    conn.commit()
    conn.close()

def seed_grammar_sentences():
    init_grammar_schema()
    conn = get_db_connection()
    cursor = conn.cursor()

    inserted = 0
    for item in GRAMMAR_DATASET:
        try:
            cursor.execute("""
            INSERT OR REPLACE INTO grammar_sentences (id, german, english, urdu, cefr, topic, rule_hint)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                item["id"],
                item["german"],
                item["english"],
                item["urdu"],
                item["cefr"],
                item["topic"],
                item["rule_hint"]
            ))
            inserted += 1
        except sqlite3.Error as e:
            print(f"Error inserting grammar sentence {item['id']}: {e}")

    conn.commit()
    conn.close()

    # Save to data/grammar.json and frontend/data/grammar.json
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FRONTEND_DATA_DIR, exist_ok=True)

    paths = [
        os.path.join(DATA_DIR, "grammar.json"),
        os.path.join(FRONTEND_DATA_DIR, "grammar.json")
    ]

    for p in paths:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(GRAMMAR_DATASET, f, ensure_ascii=False, indent=2)
        safe_p = p.encode('ascii', 'replace').decode('ascii')
        print(f"Exported static grammar dataset -> {safe_p} ({len(GRAMMAR_DATASET)} items)")

    print(f"\n[Success] Grammar Lab Dataset 2 Seeding Complete! Total sentences: {inserted}")

if __name__ == "__main__":
    seed_grammar_sentences()
