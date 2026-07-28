from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from typing import Optional, List
import os
import json
import io

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

from backend.database import init_db, get_db_connection
from backend.config import get_llm_client, DEFAULT_MODEL

app = FastAPI(
    title="PowerLink German AI Trilingual Progression API",
    description="Backend for German language learning with Dual English & Urdu (اردو) evaluation & tutoring.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_root():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "status": "online",
        "system": "German AI Trilingual Progression API (Deutsch via English + Urdu)",
        "version": "3.0.0"
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/db-status")
def db_status():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        conn.close()
        return {
            "status": "connected",
            "tables": table_names
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- USER MANAGEMENT ---

class UserCreate(BaseModel):
    user_id: str
    current_level: Optional[str] = "ZERO"

@app.post("/api/users")
def create_user(user: UserCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_id, current_level) VALUES (?, ?)",
            (user.user_id, user.current_level)
        )
        conn.commit()
        conn.close()
        return {"user_id": user.user_id, "current_level": user.current_level, "status": "created"}
    except Exception as e:
        conn.close()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET current_level = ? WHERE user_id = ?", (user.current_level, user.user_id))
        conn.commit()
        conn.close()
        return {"user_id": user.user_id, "current_level": user.current_level, "status": "updated"}

@app.get("/api/users/{user_id}")
def get_user(user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, current_level) VALUES (?, 'ZERO')", (user_id,))
        conn.commit()
        conn.close()
        return {"user_id": user_id, "current_level": "ZERO"}
    return dict(row)

# --- ANTI-REPETITION ENGINE HELPERS ---

def get_completed_topics_array(user_id: str) -> List[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT topic_summary FROM completed_topics WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [row["topic_summary"] for row in rows]

def build_anti_repetition_prompt(user_id: str) -> str:
    topics = get_completed_topics_array(user_id)
    if not topics:
        return "System Directive: Ensure 100% novel, engaging German scenarios suitable for the student."
    topics_str = ", ".join(f'"{t}"' for t in topics)
    return (
        f"System Directive: Do not generate scenarios involving the following topics as the user has already completed them: [{topics_str}]. "
        f"Ensure 100% novel scenarios."
    )

@app.get("/api/topics/{user_id}")
def get_user_topics(user_id: str):
    topics = get_completed_topics_array(user_id)
    return {"user_id": user_id, "completed_topics": topics, "count": len(topics)}

class TopicLog(BaseModel):
    user_id: str
    category: str
    topic_summary: str

@app.post("/api/topics")
def log_completed_topic(topic: TopicLog):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, ?, ?)",
        (topic.user_id, topic.category, topic.topic_summary)
    )
    conn.commit()
    conn.close()
    return {"status": "logged", "topic_summary": topic.topic_summary}

# --- CONFIG / API KEY SETTINGS ---
class APIKeyRequest(BaseModel):
    api_key: str

@app.get("/api/config/key")
def get_api_key_status():
    from backend.config import is_key_configured, GEMINI_API_KEY
    return {
        "is_configured": is_key_configured(),
        "has_key": bool(GEMINI_API_KEY and GEMINI_API_KEY != "placeholder_key")
    }

@app.post("/api/config/key")
def save_api_key(req: APIKeyRequest):
    from backend.config import set_api_key
    key = req.api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API key cannot be empty")
    set_api_key(key)
    return {"success": True, "message": "Gemini API key configured successfully!"}

# --- GERMAN TRILINGUAL CONTENT GENERATION ENGINE ---

class VocabGenRequest(BaseModel):
    user_id: str
    cefr_level: Optional[str] = "ZERO"
    count: Optional[int] = 4

CEFR_GERMAN_GUARDRAILS = {
    "ZERO": "German Level ZERO (Breakthrough): Max 500 essential words (Greetings: Guten Tag, Bitte, Danke; Numbers: eins, zwei; Basic Nouns with articles: Der Hund, Das Haus; Basic Verbs: sein, haben, kommen).",
    "A1": "German Level A1 (Beginner): Max 1,200 words (Everyday situations: Einkaufen, Essen, Familie, Zeit; Present Tense verb conjugation; Nominativ & Akkusativ).",
    "A2": "German Level A2 (Elementary): Max 2,500 words (Routine, Reisen, Arbeit, Vergangenheitsformen: Perfekt mit haben/sein; Modalverben).",
    "B1": "German Level B1 (Intermediate): Complex German sentence structures, Nebensätze (weil, dass, obwohl), Passiv, and professional/daily conversation."
}

@app.post("/api/vocabulary/generate")
def generate_german_vocabulary(req: VocabGenRequest):
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    guardrail = CEFR_GERMAN_GUARDRAILS.get(level, CEFR_GERMAN_GUARDRAILS["ZERO"])
    
    # Anti-Repetition SQL Query filtered by user_id and level, limited to last 30 words
    conn = get_db_connection()
    cursor = conn.cursor()
    existing_rows = cursor.execute(
        "SELECT DISTINCT word FROM vocabulary_vault WHERE user_id = ? AND cefr_level = ?", 
        (req.user_id, level)
    ).fetchall()
    conn.close()
    
    existing_words = [r["word"] for r in existing_rows if r["word"]]
    if existing_words:
        words_str = ", ".join(f'"{w}"' for w in existing_words[-30:])
        vocab_exclusion = (
            f"CRITICAL ANTI-REPETITION DIRECTIVE: Do NOT generate any of the following previously generated German words/phrases for level {level}: [{words_str}]. "
            f"Generate 100% novel, unique vocabulary appropriate for level '{level}'."
        )
    else:
        vocab_exclusion = f"Ensure 100% novel, unique German vocabulary for level '{level}'."

    anti_rep = build_anti_repetition_prompt(req.user_id)
    
    prompt = f"""
{anti_rep}
{vocab_exclusion}
CEFR German Guardrail: {guardrail}

Generate exactly {req.count} German vocabulary words or common phrases for an Urdu & English speaker learning German at level '{level}'.
IMPORTANT: You MUST provide clear translations in BOTH English and Urdu (اردو).

Return ONLY a valid JSON array of objects with these exact keys:
- "word": string (The German word with gender article if noun, e.g. "Guten Tag", "der Apfel", "kommen")
- "definition_en": string (English definition/meaning)
- "definition_ur": string (Urdu definition/meaning in Urdu script e.g. "سلام / اچھا دن" or "سیب")
- "example_sentence": string (Example sentence in German)
- "example_translation_en": string (English translation of example sentence)
- "example_translation_ur": string (Urdu translation of example sentence in Urdu script)
- "cefr_level": string ("{level}")
- "topic": string (Theme/topic of the vocabulary item)

Example Output:
[
  {{
    "word": "Guten Tag",
    "definition_en": "Good day / Hello",
    "definition_ur": "سلام / آپ کا دن اچھا گزرے",
    "example_sentence": "Guten Tag! Wie geht es Ihnen?",
    "example_translation_en": "Good day! How are you?",
    "example_translation_ur": "سلام! آپ کا کیا حال ہے؟",
    "cefr_level": "{level}",
    "topic": "Greetings & Social"
  }}
]
Return strictly valid JSON array.
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a master German language tutor fluent in German, English, and Urdu (اردو). Output strictly valid JSON arrays."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
            
        items = json.loads(content)
        if not isinstance(items, list):
            items = []
            
        items = items[:4]
        
        # Save into SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        saved_items = []
        for item in items:
            def_combined = f"{item.get('definition_en')} | {item.get('definition_ur')}"
            cursor.execute(
                """INSERT INTO vocabulary_vault 
                (user_id, word, definition, definition_en, definition_ur, example_sentence, example_translation_en, example_translation_ur, cefr_level, mastery_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                (req.user_id, item.get("word"), def_combined, item.get("definition_en"), item.get("definition_ur"), 
                 item.get("example_sentence"), item.get("example_translation_en"), item.get("example_translation_ur"), level)
            )
            saved_items.append(item)
            
            topic_name = item.get("topic") or item.get("word")
            cursor.execute(
                "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Vocabulary', ?)",
                (req.user_id, f"German Vocab: {topic_name}")
            )
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "cefr_level": level,
            "count": len(saved_items),
            "vocabulary": saved_items
        }
    except Exception as e:
        print(f"[Gemini Vocabulary API Error]: {e}")
        all_pool = get_fallback_vocab_for_level(level)
        conn = get_db_connection()
        cursor = conn.cursor()
        existing_rows = cursor.execute(
            "SELECT DISTINCT word FROM vocabulary_vault WHERE user_id = ? AND cefr_level = ?", 
            (req.user_id, level)
        ).fetchall()
        conn.close()
        seen = [r["word"] for r in existing_rows if r["word"]]
        unseen = [item for item in all_pool if item["word"] not in seen]
        if len(unseen) < 4:
            unseen = all_pool
        import random
        selected = random.sample(unseen, min(4, len(unseen)))
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            for item in selected:
                def_combined = f"{item.get('definition_en')} | {item.get('definition_ur')}"
                cursor.execute(
                    """INSERT INTO vocabulary_vault 
                    (user_id, word, definition, definition_en, definition_ur, example_sentence, example_translation_en, example_translation_ur, cefr_level, mastery_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                    (req.user_id, item.get('word'), def_combined, item.get('definition_en'), item.get('definition_ur'),
                     item.get('example_sentence'), item.get('example_translation_en'), item.get('example_translation_ur'), level)
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

        return {
            "success": True,
            "is_fallback": True,
            "notice": f"Dynamic Pool Mode ({str(e)})",
            "cefr_level": level,
            "count": len(selected),
            "vocabulary": selected
        }

def get_fallback_vocab_for_level(level: str) -> List[dict]:
    fallbacks = {
        "ZERO": [
            {
                "word": "Guten Morgen",
                "definition_en": "Good morning",
                "definition_ur": "صبح بخیر",
                "example_sentence": "Guten Morgen, Frau Müller!",
                "example_translation_en": "Good morning, Mrs. Müller!",
                "example_translation_ur": "صبح بخیر، محترمہ ملر!",
                "cefr_level": "ZERO",
                "topic": "Greetings"
            },
            {
                "word": "Danke schön",
                "definition_en": "Thank you very much",
                "definition_ur": "بہت بہت شکریہ",
                "example_sentence": "Vielen Dank für Ihre Hilfe!",
                "example_translation_en": "Thank you very much for your help!",
                "example_translation_ur": "آپ کی مدد کا بہت بہت شکریہ!",
                "cefr_level": "ZERO",
                "topic": "Polite Expressions"
            },
            {
                "word": "das Wasser",
                "definition_en": "The water",
                "definition_ur": "پانی",
                "example_sentence": "Ich trinke kaltes Wasser.",
                "example_translation_en": "I drink cold water.",
                "example_translation_ur": "میں ٹھنڈا پانی پیتا ہوں۔",
                "cefr_level": "ZERO",
                "topic": "Food & Drinks"
            },
            {
                "word": "Entschuldigung",
                "definition_en": "Excuse me / Sorry",
                "definition_ur": "معذرت خواہ ہوں / معاف کیجیے گا",
                "example_sentence": "Entschuldigung, wo ist der Bahnhof?",
                "example_translation_en": "Excuse me, where is the train station?",
                "example_translation_ur": "معاف کیجیے گا، ریلوے اسٹیشن کہاں ہے؟",
                "cefr_level": "ZERO",
                "topic": "Directions"
            },
            {
                "word": "der Apfel",
                "definition_en": "The apple",
                "definition_ur": "سیب",
                "example_sentence": "Der Apfel ist rot und süß.",
                "example_translation_en": "The apple is red and sweet.",
                "example_translation_ur": "سیب سرخ اور میٹھا ہے۔",
                "cefr_level": "ZERO",
                "topic": "Food"
            },
            {
                "word": "Auf Wiedersehen",
                "definition_en": "Goodbye",
                "definition_ur": "خدا حافظ / دوبارہ ملیں گے",
                "example_sentence": "Auf Wiedersehen und einen schönen Tag!",
                "example_translation_en": "Goodbye and have a nice day!",
                "example_translation_ur": "خدا حافظ اور آپ کا دن اچھا گزرے!",
                "cefr_level": "ZERO",
                "topic": "Farewell"
            },
            {
                "word": "das Haus",
                "definition_en": "The house",
                "definition_ur": "گھر / مکان",
                "example_sentence": "Das Haus ist groß und schön.",
                "example_translation_en": "The house is big and beautiful.",
                "example_translation_ur": "گھر بڑا اور خوبصورت ہے۔",
                "cefr_level": "ZERO",
                "topic": "Home"
            },
            {
                "word": "der Hund",
                "definition_en": "The dog",
                "definition_ur": "کتا",
                "example_sentence": "Der Hund spielt im Garten.",
                "example_translation_en": "The dog plays in the garden.",
                "example_translation_ur": "کتا باغ میں کھیل رہا ہے۔",
                "cefr_level": "ZERO",
                "topic": "Animals"
            }
        ],
        "A1": [
            {
                "word": "einkaufen",
                "definition_en": "To go shopping",
                "definition_ur": "خریداری کرنا",
                "example_sentence": "Ich kaufe am Samstag im Supermarkt ein.",
                "example_translation_en": "I go shopping at the supermarket on Saturday.",
                "example_translation_ur": "میں ہفتے کے دن سپر مارکیٹ سے خریداری کرتا ہوں۔",
                "cefr_level": "A1",
                "topic": "Daily Shopping"
            },
            {
                "word": "die Familie",
                "definition_en": "The family",
                "definition_ur": "خاندان / کنبہ",
                "example_sentence": "Meine Familie wohnt in Berlin.",
                "example_translation_en": "My family lives in Berlin.",
                "example_translation_ur": "میرا خاندان برلن میں رہتا ہے۔",
                "cefr_level": "A1",
                "topic": "Family"
            },
            {
                "word": "die Zeitung",
                "definition_en": "The newspaper",
                "definition_ur": "اخبار",
                "example_sentence": "Er liest jeden Morgen die Zeitung.",
                "example_translation_en": "He reads the newspaper every morning.",
                "example_translation_ur": "وہ ہر صبح اخبار پڑھتا ہے۔",
                "cefr_level": "A1",
                "topic": "Daily Routine"
            },
            {
                "word": "schlafen",
                "definition_en": "To sleep",
                "definition_ur": "سونا",
                "example_sentence": "Ich schlafe gewöhnlich um 22 Uhr.",
                "example_translation_en": "I usually sleep at 10 PM.",
                "example_translation_ur": "میں معمول کے مطابق رات 10 بجے سوتا ہوں۔",
                "cefr_level": "A1",
                "topic": "Sleep Routine"
            },
            {
                "word": "der Schlüssel",
                "definition_en": "The key",
                "definition_ur": "چابی",
                "example_sentence": "Wo ist mein Schlüssel?",
                "example_translation_en": "Where is my key?",
                "example_translation_ur": "میری چابی کہاں ہے؟",
                "cefr_level": "A1",
                "topic": "Objects"
            },
            {
                "word": "die Fahrkarte",
                "definition_en": "The transit ticket",
                "definition_ur": "سفر کا ٹکٹ",
                "example_sentence": "Ich brauche eine Fahrkarte nach Hamburg.",
                "example_translation_en": "I need a ticket to Hamburg.",
                "example_translation_ur": "مجھے ہیمبرگ کے لیے ٹکٹ کی ضرورت ہے۔",
                "cefr_level": "A1",
                "topic": "Transit"
            }
        ],
        "A2": [
            {
                "word": "der Ausflug",
                "definition_en": "The excursion / trip",
                "definition_ur": "تفریحی سفر / سیر",
                "example_sentence": "Wir machen am Wochenende einen Ausflug nach München.",
                "example_translation_en": "We are making a trip to Munich on the weekend.",
                "example_translation_ur": "ہم ہفتے کے اختتام پر میونخ کا سفر کر رہے ہیں۔",
                "cefr_level": "A2",
                "topic": "Travel"
            },
            {
                "word": "die Bewerbung",
                "definition_en": "The job application",
                "definition_ur": "نوکری کی درخواست",
                "example_sentence": "Ich habe meine Bewerbung per E-Mail geschickt.",
                "example_translation_en": "I sent my application via email.",
                "example_translation_ur": "میں نے اپنی درخواست ای میل کے ذریعے بھیجی۔",
                "cefr_level": "A2",
                "topic": "Work & Career"
            },
            {
                "word": "vereinbaren",
                "definition_en": "To arrange / schedule",
                "definition_ur": "طے کرنا / وقت مقرر کرنا",
                "example_sentence": "Ich möchte einen Termin beim Arzt vereinbaren.",
                "example_translation_en": "I would like to schedule an appointment with the doctor.",
                "example_translation_ur": "میں ڈاکٹر کے پاس وقت طے کرنا چاہتا ہوں۔",
                "cefr_level": "A2",
                "topic": "Appointments"
            },
            {
                "word": "die Gesundheit",
                "definition_en": "Health",
                "definition_ur": "صحت",
                "example_sentence": "Gesundheit ist das Wichtigste im Leben.",
                "example_translation_en": "Health is the most important thing in life.",
                "example_translation_ur": "صحت زندگی کی سب سے اہم چیز ہے۔",
                "cefr_level": "A2",
                "topic": "Health"
            }
        ],
        "B1": [
            {
                "word": "die Herausforderung",
                "definition_en": "The challenge",
                "definition_ur": "چیلنج / آزمائش",
                "example_sentence": "Deutsch lernen ist eine spannende Herausforderung.",
                "example_translation_en": "Learning German is an exciting challenge.",
                "example_translation_ur": "جرمن سیکھنا ایک دلچسپ چیلنج ہے۔",
                "cefr_level": "B1",
                "topic": "Education"
            },
            {
                "word": "die Verantwortung",
                "definition_en": "The responsibility",
                "definition_ur": "ذمہ داری",
                "example_sentence": "Er übernimmt die Verantwortung für das Projekt.",
                "example_translation_en": "He takes responsibility for the project.",
                "example_translation_ur": "وہ پروجیکٹ کی ذمہ داری لیتا ہے۔",
                "cefr_level": "B1",
                "topic": "Professional Work"
            },
            {
                "word": "entscheiden",
                "definition_en": "To decide",
                "definition_ur": "فیصلہ کرنا",
                "example_sentence": "Wir müssen uns für eine Option entscheiden.",
                "example_translation_en": "We must decide on one option.",
                "example_translation_ur": "ہمیں ایک اختیار کا فیصلہ کرنا ہوگا۔",
                "cefr_level": "B1",
                "topic": "Decision Making"
            },
            {
                "word": "die Überzeugung",
                "definition_en": "The conviction / belief",
                "definition_ur": "عزم / پختہ یقین",
                "example_sentence": "Aus vollster Überzeugung habe ich zugestimmt.",
                "example_translation_en": "With full conviction I agreed.",
                "example_translation_ur": "مکمل یقین کے ساتھ میں نے اتفاق کیا۔",
                "cefr_level": "B1",
                "topic": "Opinions"
            }
        ]
    }
    return fallbacks.get(level.upper(), fallbacks["ZERO"])

@app.get("/api/vocabulary/{user_id}")
def get_user_vocabulary(user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM vocabulary_vault WHERE user_id = ? ORDER BY vocab_id DESC", (user_id,)
    ).fetchall()
    conn.close()
    return {"user_id": user_id, "vocabulary": [dict(r) for r in rows]}

DYNAMIC_GRAMMAR_EXERCISES = {
    "ZERO": [
        {
            "instructions_en": "Correct the grammatical error in the German sentence below:",
            "instructions_ur": "درج ذیل جرمن جملے میں گرائمر کی غلطی کو درست کریں:",
            "incorrect_sentence": "Ich kommt aus Deutschland.",
            "target_concept": "Verb Conjugation: 'kommen' (First-Person Singular 'Ich')",
            "hint_en": "For 'Ich' (I), the verb ending should be '-e' (Ich komme), not '-t'.",
            "hint_ur": "ضمیر 'Ich' (میں) کے لیے فعل کا آخر '-e' (Ich komme) ہوتا ہے، '-t' نہیں۔",
            "topic": "Verb Conjugation"
        },
        {
            "instructions_en": "Fix the wrong article (der/die/das) for the German noun 'Apfel':",
            "instructions_ur": "جرمن اسم 'Apfel' (سیب) کے لیے غلط حرفِ تعریف درست کریں:",
            "incorrect_sentence": "Das Apfel ist rot.",
            "target_concept": "Noun Genders: Masculine Article 'der'",
            "hint_en": "'Apfel' is masculine, so it takes 'der Apfel', not 'das'.",
            "hint_ur": "'Apfel' مذكر اسم ہے، اس لیے اس کے ساتھ 'der Apfel' استعمال ہوتا ہے۔",
            "topic": "Noun Gender Articles"
        },
        {
            "instructions_en": "Fix the verb position in this simple German question:",
            "instructions_ur": "اس سادہ جرمن سوال میں فعل کی جگہ درست کریں:",
            "incorrect_sentence": "Wo du wohnst?",
            "target_concept": "German V2 Word Order in W-Questions",
            "hint_en": "In German W-questions, the verb must come in position 2: 'Wo wohnst du?'",
            "hint_ur": "جرمن سوالیہ جملوں میں فعل دوسرے نمبر پر آتا ہے: 'Wo wohnst du؟'",
            "topic": "Sentence Word Order"
        },
        {
            "instructions_en": "Correct the verb conjugation for 'haben' (to have):",
            "instructions_ur": "فعل 'haben' (پاس ہونا) کی گردان درست کریں:",
            "incorrect_sentence": "Du hat ein Buch.",
            "target_concept": "Verb Conjugation: 'haben' (Second-Person 'du')",
            "hint_en": "For 'du' (you singular), 'haben' conjugated is 'du hast'.",
            "hint_ur": "ضمیر 'du' (تم) کے ساتھ 'haben' کا صیغہ 'du hast' ہوتا ہے۔",
            "topic": "Irregular Verb Conjugation"
        }
    ],
    "A1": [
        {
            "instructions_en": "Fix the accusative case article for masculine nouns in German:",
            "instructions_ur": "مذکر اسم کے لیے مفعولی حالت (Accusative) کا حرفِ تعریف درست کریں:",
            "incorrect_sentence": "Ich kaufe der Tisch.",
            "target_concept": "Akkusativ Case: Masculine 'den'",
            "hint_en": "In the accusative case, direct object 'der Tisch' becomes 'den Tisch'.",
            "hint_ur": "مفعولی حالت (Akkusativ) میں 'der' بدل کر 'den' ہو جاتا ہے (den Tisch)۔",
            "topic": "Accusative Articles"
        },
        {
            "instructions_en": "Correct the past participle position for Perfect tense:",
            "instructions_ur": "ماضی قریب (Perfekt) میں فعل کے تیسرے صیغے کی جگہ درست کریں:",
            "incorrect_sentence": "Ich habe gekauft ein Auto.",
            "target_concept": "Perfekt Tense Sentence Structure (Partizip II at end)",
            "hint_en": "In Perfekt tense, Partizip II ('gekauft') must go to the very end: 'Ich habe ein Auto gekauft.'",
            "hint_ur": "ماضی قریب میں فعل کا تیسرا صیغہ جملے کے آخر میں آتا ہے: 'Ich habe ein Auto gekauft.'",
            "topic": "Past Perfekt Tense"
        }
    ],
    "A2": [
        {
            "instructions_en": "Fix modal verb word order in past tense sentence:",
            "instructions_ur": "ماضی کے جملے میں امدادی فعل کی جگہ درست کریں:",
            "incorrect_sentence": "Ich konnte gestern nicht kommen weil krank war ich.",
            "target_concept": "Subordinate Clause (Nebensatz mit 'weil')",
            "hint_en": "After 'weil', the conjugated verb goes to the end: 'weil ich krank war.'",
            "hint_ur": "لفظ 'weil' (کیونکہ) کے بعد فعل جملے کے بالکل آخر میں آتا ہے۔",
            "topic": "Subordinate Clauses"
        }
    ],
    "B1": [
        {
            "instructions_en": "Fix the passive voice construction in German:",
            "instructions_ur": "جرمن میں مجهول جملے (Passive Voice) کی ساخت درست کریں:",
            "incorrect_sentence": "Das Haus wird von dem Mann gebaut werden.",
            "target_concept": "Präsens Passiv Structure (werden + Partizip II)",
            "hint_en": "Present passive uses 'wird gebaut': 'Das Haus wird von dem Mann gebaut.'",
            "hint_ur": "حال مجهول میں 'wird + Partizip II' یعنی 'wird gebaut' استعمال ہوتا ہے۔",
            "topic": "Passive Voice"
        }
    ]
}

def get_random_unseen_grammar_exercise(user_id: str, level: str) -> dict:
    import random
    lvl = level.upper() if level else "ZERO"
    pool = DYNAMIC_GRAMMAR_EXERCISES.get(lvl, DYNAMIC_GRAMMAR_EXERCISES["ZERO"])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    grammar_rows = cursor.execute(
        "SELECT topic_summary FROM completed_topics WHERE user_id = ? AND category = 'German Grammar'", (user_id,)
    ).fetchall()
    conn.close()
    
    used_summaries = [r["topic_summary"] for r in grammar_rows if r["topic_summary"]]
    unseen = [ex for ex in pool if not any(ex["incorrect_sentence"] in s for s in used_summaries)]
    if not unseen:
        unseen = pool
    return random.choice(unseen)

class GrammarGenRequest(BaseModel):
    user_id: str
    cefr_level: Optional[str] = "ZERO"

@app.post("/api/grammar/generate")
def generate_german_grammar_exercise(req: GrammarGenRequest):
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    guardrail = CEFR_GERMAN_GUARDRAILS.get(level, CEFR_GERMAN_GUARDRAILS["ZERO"])
    
    # Query SQLite DB for previously generated grammar exercises for this user
    conn = get_db_connection()
    cursor = conn.cursor()
    grammar_rows = cursor.execute(
        "SELECT topic_summary FROM completed_topics WHERE user_id = ? AND category = 'German Grammar'", (req.user_id,)
    ).fetchall()
    conn.close()
    
    used_grammar = [r["topic_summary"] for r in grammar_rows if r["topic_summary"]]
    if used_grammar:
        grammar_str = ", ".join(f'"{g}"' for g in used_grammar[-30:])
        grammar_exclusion = (
            f"CRITICAL ANTI-REPETITION DIRECTIVE: Do NOT reuse any of the following previously generated German grammar tasks/sentences: [{grammar_str}]. "
            f"Generate a 100% novel, unique German sentence correction exercise for level '{level}'."
        )
    else:
        grammar_exclusion = "Ensure a 100% novel, unique German sentence correction exercise."

    anti_rep = build_anti_repetition_prompt(req.user_id)
    
    prompt = f"""
{anti_rep}
{grammar_exclusion}
CEFR German Guardrail: {guardrail}

Generate ONE German written grammar exercise for level '{level}'.
The task should present a German sentence containing a grammar error (e.g. incorrect verb conjugation, wrong gender article der/die/das, or word order V2 error).
Provide clear instructions and hints in BOTH English and Urdu (اردو).

Return strictly a JSON object with:
- "instructions_en": string (English instructions, e.g. "Correct the German sentence below:")
- "instructions_ur": string (Urdu instructions in Urdu script, e.g. "درج ذیل جرمن جملے میں غلطی درست کریں:")
- "incorrect_sentence": string (The incorrect German sentence)
- "target_concept": string (German grammar concept name e.g. "Verb Conjugation (kommen)")
- "hint_en": string (Helpful hint in English)
- "hint_ur": string (Helpful hint in Urdu script)
- "topic": string (Theme of the grammar exercise)

Return strictly valid JSON object.
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a German grammar tutor fluent in German, English, and Urdu (اردو). Return strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
        exercise = json.loads(content)

        # Save generated grammar exercise to SQLite DB
        conn = get_db_connection()
        cursor = conn.cursor()
        topic_summary = f"Grammar ({level}): {exercise.get('target_concept', 'Rule')} - {exercise.get('incorrect_sentence', '')}"
        cursor.execute(
            "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Grammar', ?)",
            (req.user_id, topic_summary)
        )
        conn.commit()
        conn.close()

        return {"success": True, "exercise": exercise}
    except Exception as e:
        print(f"[Gemini Grammar API Error]: {e}")
        exercise = get_random_unseen_grammar_exercise(req.user_id, level)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Grammar', ?)",
                (req.user_id, f"Grammar ({level}): {exercise.get('target_concept')} - {exercise.get('incorrect_sentence')}")
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
        return {"success": True, "is_fallback": True, "notice": f"Dynamic Pool Mode ({str(e)})", "exercise": exercise}

class GrammarSubmitRequest(BaseModel):
    user_id: str
    incorrect_sentence: str
    user_answer: str
    target_concept: str
    cefr_level: Optional[str] = "ZERO"

@app.post("/api/grammar/submit")
def submit_german_grammar_answer(req: GrammarSubmitRequest):
    prompt = f"""
Evaluate the student's German correction:
Original incorrect German sentence: "{req.incorrect_sentence}"
Student's submitted sentence: "{req.user_answer}"
Target German Grammar Concept: "{req.target_concept}"
CEFR Level: "{req.cefr_level.upper()}"

Determine if the student's correction is grammatically accurate German.
Return strictly JSON with:
- "is_correct": boolean
- "score": number out of 100
- "correct_version": string (The ideal corrected German sentence)
- "explanation_en": string (Feedback summary in English)
- "explanation_ur": string (Feedback summary in Urdu script)
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a gentle German grammar evaluator providing feedback in English and Urdu. Return strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
        eval_result = json.loads(content)
        
        if eval_result.get("is_correct"):
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Grammar', ?)",
                (req.user_id, f"Grammar: {req.target_concept}")
            )
            conn.commit()
            conn.close()
            
        return {"success": True, "evaluation": eval_result}
    except Exception as e:
        is_corr = "komme" in req.user_answer.lower()
        eval_result = {
            "is_correct": is_corr,
            "score": 100 if is_corr else 40,
            "correct_version": "Ich komme aus Deutschland.",
            "explanation_en": "Excellent job! 'Ich komme' is the correct first-person form." if is_corr else "Remember for 'Ich' (I), the verb ending is '-e' -> 'Ich komme'.",
            "explanation_ur": "بہت خوب! 'Ich komme' درست ترین شکل ہے۔" if is_corr else "یاد رکھیں 'Ich' کے ساتھ فعل کا آخر '-e' یعنی 'Ich komme' ہوتا ہے۔"
        }
        if is_corr:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Grammar', ?)",
                (req.user_id, f"Grammar: {req.target_concept}")
            )
            conn.commit()
            conn.close()
        return {"success": True, "is_fallback": True, "evaluation": eval_result}

class PingLLMRequest(BaseModel):
    prompt: Optional[str] = "Guten Tag! Introduce yourself as the German AI Trilingual Tutor."
    model: Optional[str] = None

@app.post("/api/ping-llm")
def ping_llm(request: PingLLMRequest):
    try:
        client = get_llm_client()
        model_name = request.model or DEFAULT_MODEL
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are a German language tutor teaching in English and Urdu."},
                {"role": "user", "content": request.prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        reply = response.choices[0].message.content
        return {
            "success": True,
            "model_used": model_name,
            "prompt": request.prompt,
            "response": reply
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "hint": "Check GEMINI_API_KEY in .env file or environment variables."
        }

# ==============================================================================
# PHASE 3: AUDIO PIPELINE (TTS, STT, LISTENING & SPEAKING MODULES)
# ==============================================================================

class TTSRequest(BaseModel):
    text: str
    cefr_level: Optional[str] = "ZERO"
    speed: Optional[float] = None

@app.post("/api/audio/tts")
def generate_tts_audio(req: TTSRequest):
    """
    Generates German audio pronunciation with CEFR playback speed guardrails:
    - ZERO / A1: Slow speed (slow=True / 0.75x)
    - A2: Moderate speed (slow=False / 0.9x)
    - B1: Normal speed (slow=False / 1.0x)
    """
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    is_slow = True if level in ["ZERO", "A1"] else False
    
    if req.speed is not None:
        is_slow = req.speed < 0.85
        
    if GTTS_AVAILABLE:
        try:
            tts = gTTS(text=req.text, lang='de', slow=is_slow)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            fp.seek(0)
            return Response(content=fp.getvalue(), media_type="audio/mpeg")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"gTTS audio generation error: {str(e)}")
    else:
        raise HTTPException(status_code=501, detail="gTTS engine is not available on backend. Use Web Speech API on frontend.")


# --- MODULE 3: LISTENING COMPREHENSION ---

DYNAMIC_LISTENING_SCENARIOS = [
    {
        "title": "Guten Tag im Café (At the Café)",
        "narrative_de": "Hallo! Mein Name ist Maria. Ich bin im Café in Berlin. Ich trinke einen Kaffee und esse einen Kuchen. Es schmeckt sehr gut!",
        "narrative_en": "Hello! My name is Maria. I am at the café in Berlin. I am drinking a coffee and eating a cake. It tastes very good!",
        "narrative_ur": "ہیلو! میرا نام ماریا ہے۔ میں برلن کے کیفے میں ہوں۔ میں کافی پی رہی ہوں اور کیک کھا رہی ہوں۔ یہ بہت مزیدار ہے!",
        "topic": "Cafe Conversation",
        "questions": [
            {"question_de": "Wo ist Maria?", "question_en": "Where is Maria?", "question_ur": "ماریا کہاں ہے؟", "options": ["Im Café in Berlin", "Im Supermarkt", "Zu Hause", "Im Bahnhof"], "correct_option": 0, "explanation_en": "Maria states she is at the café in Berlin.", "explanation_ur": "ماریا کہتی ہے کہ وہ برلن کے کیفے میں ہے۔"},
            {"question_de": "Was trinkt Maria?", "question_en": "What is Maria drinking?", "question_ur": "ماریا کیا پی رہی ہے؟", "options": ["Tee", "Einen Kaffee", "Wasser", "Milch"], "correct_option": 1, "explanation_en": "She says 'Ich trinke einen Kaffee'.", "explanation_ur": "وہ کہتی ہے 'Ich trinke einen Kaffee' (میں کافی پی رہی ہوں)۔"},
            {"question_de": "Was isst Maria?", "question_en": "What is Maria eating?", "question_ur": "ماریا کیا کھا رہی ہے؟", "options": ["Brot", "Einen Kuchen", "Pizza", "Apfel"], "correct_option": 1, "explanation_en": "She says 'esse einen Kuchen'.", "explanation_ur": "وہ کہتی ہے کہ وہ کیک کھا رہی ہے۔"},
            {"question_de": "In welcher Stadt ist Maria?", "question_en": "In which city is Maria?", "question_ur": "ماریا کس شہر میں ہے؟", "options": ["München", "Hamburg", "Berlin", "Frankfurt"], "correct_option": 2, "explanation_en": "She is in Berlin.", "explanation_ur": "وہ برلن میں ہے۔"},
            {"question_de": "Wie schmeckt das Essen?", "question_en": "How does the food taste?", "question_ur": "کھانا کیسا لگ رہا ہے؟", "options": ["Nicht gut", "Sehr gut", "Schlecht", "Kalt"], "correct_option": 1, "explanation_en": "She says 'Es schmeckt sehr gut!'", "explanation_ur": "وہ کہتی ہے 'Es schmeckt sehr gut!' (یہ بہت مزیدار ہے)۔"}
        ]
    },
    {
        "title": "Fahrkarte am Bahnhof (Train Ticket)",
        "narrative_de": "Guten Tag! Ich fahre heute nach München. Der Zug fährt um vierzehn Uhr ab. Eine Fahrkarte kostet fünfzig Euro.",
        "narrative_en": "Good day! I am traveling to Munich today. The train departs at 2 PM. A ticket costs fifty euros.",
        "narrative_ur": "دن کا سلام! میں آج میونخ کا سفر کر رہا ہوں۔ ٹرین دوپہر 2 بجے روانہ ہوتی ہے۔ ٹکٹ پچاس یورو کی ہے۔",
        "topic": "Train Travel",
        "questions": [
            {"question_de": "Wohin fährt die Person?", "question_en": "Where is the person traveling to?", "question_ur": "شخص کہاں سفر کر رہا ہے؟", "options": ["Nach Berlin", "Nach München", "Nach Hamburg", "Nach Köln"], "correct_option": 1, "explanation_en": "Traveling to Munich.", "explanation_ur": "میونخ کا سفر۔"},
            {"question_de": "Wann fährt der Zug ab?", "question_en": "When does the train depart?", "question_ur": "ٹرین کب روانہ ہوتی ہے؟", "options": ["Um 10 Uhr", "Um 12 Uhr", "Um 14 Uhr", "Um 18 Uhr"], "correct_option": 2, "explanation_en": "At 14:00 (2 PM).", "explanation_ur": "14:00 (دوپہر 2 بجے)۔"},
            {"question_de": "Wie viel kostet die Fahrkarte?", "question_en": "How much does the ticket cost?", "question_ur": "ٹکٹ کتنے کی ہے؟", "options": ["20 Euro", "50 Euro", "100 Euro", "Kostenlos"], "correct_option": 1, "explanation_en": "Fifty Euros.", "explanation_ur": "پچاس یورو۔"},
            {"question_de": "Welches Verkehrsmittel wird benutzt?", "question_en": "Which transportation is used?", "question_ur": "کون سی سواری استعمال کی گئی ہے؟", "options": ["Das Auto", "Der Bus", "Der Zug", "Das Flugzeug"], "correct_option": 2, "explanation_en": "The train (Der Zug).", "explanation_ur": "ٹرین (Der Zug)۔"},
            {"question_de": "Wann macht die Person diese Reise?", "question_en": "When is the trip happening?", "question_ur": "سفر کب ہو رہا ہے؟", "options": ["Gestern", "Heute", "Morgen", "Nächste Woche"], "correct_option": 1, "explanation_en": "Today (Heute).", "explanation_ur": "آج (Heute)۔"}
        ]
    },
    {
        "title": "Im Supermarkt einkaufen (Grocery Shopping)",
        "narrative_de": "Thomas kauft im Supermarkt ein. Er braucht frisches Brot, Käsestücke und süße Äpfel. Das Brot kostet zwei Euro.",
        "narrative_en": "Thomas is shopping at the supermarket. He needs fresh bread, pieces of cheese, and sweet apples. The bread costs two euros.",
        "narrative_ur": "تھامس سپر مارکیٹ میں خریداری کر رہا ہے۔ اسے تازہ روٹی، پنیر اور میٹھے سیب چاہیے۔ روٹی دو یورو کی ہے۔",
        "topic": "Supermarket Shopping",
        "questions": [
            {"question_de": "Wer kauft im Supermarkt ein?", "question_en": "Who is shopping at the supermarket?", "question_ur": "سپر مارکیٹ سے کون خریداری کر رہا ہے؟", "options": ["Maria", "Thomas", "Ali", "Frau Müller"], "correct_option": 1, "explanation_en": "Thomas is shopping.", "explanation_ur": "تھامس خریداری کر رہا ہے۔"},
            {"question_de": "Was für ein Brot braucht Thomas?", "question_en": "What kind of bread does Thomas need?", "question_ur": "تھامس کو کس قسم کی روٹی چاہیے؟", "options": ["Altes Brot", "Frisches Brot", "Kaltes Brot", "Gar kein Brot"], "correct_option": 1, "explanation_en": "Fresh bread.", "explanation_ur": "تازہ روٹی۔"},
            {"question_de": "Was für ein Obst kauft Thomas?", "question_en": "What fruit does Thomas buy?", "question_ur": "تھامس کون سا پھل خریدتا ہے؟", "options": ["Bananen", "Süße Äpfel", "Orangen", "Trauben"], "correct_option": 1, "explanation_en": "Sweet apples.", "explanation_ur": "میٹھے سیب۔"},
            {"question_de": "Wie viel kostet das Brot?", "question_en": "How much does the bread cost?", "question_ur": "روٹی کی قیمت کیا ہے؟", "options": ["Einen Euro", "Zwei Euro", "Fünf Euro", "Zehn Euro"], "correct_option": 1, "explanation_en": "Two euros.", "explanation_ur": "دو یورو۔"},
            {"question_de": "Wo ist Thomas?", "question_en": "Where is Thomas?", "question_ur": "تھامس کہاں ہے؟", "options": ["Im Park", "Im Supermarkt", "Zu Hause", "Im Café"], "correct_option": 1, "explanation_en": "In the supermarket.", "explanation_ur": "سپر مارکیٹ میں۔"}
        ]
    },
    {
        "title": "Beim Arzt in der Praxis (At the Doctor's)",
        "narrative_de": "Anna ist krank. Sie hat Kopfschmerzen und geht zum Arzt. Der Arzt sagt: 'Trinken Sie viel Wasser und ruhen Sie sich aus.'",
        "narrative_en": "Anna is sick. She has a headache and goes to the doctor. The doctor says: 'Drink plenty of water and get rest.'",
        "narrative_ur": "آنا بیمار ہے۔ اسے سر درد ہے اور وہ ڈاکٹر کے پاس جاتی ہے۔ ڈاکٹر کہتا ہے: 'زیادہ پانی پیئں اور آرام کریں۔'",
        "topic": "Doctor & Health",
        "questions": [
            {"question_de": "Wie geht es Anna?", "question_en": "How is Anna feeling?", "question_ur": "آنا کی طبیعت کیسی ہے؟", "options": ["Sehr gut", "Sie ist krank", "Müde aber gesund", "Glücklich"], "correct_option": 1, "explanation_en": "Anna is sick.", "explanation_ur": "آنا بیمار ہے۔"},
            {"question_de": "Was für Schmerzen hat Anna?", "question_en": "What pain does Anna have?", "question_ur": "آنا کو کیا تکلیف ہے؟", "options": ["Bauchschmerzen", "Kopfschmerzen", "Zahnschmerzen", "Rückenschmerzen"], "correct_option": 1, "explanation_en": "Headache (Kopfschmerzen).", "explanation_ur": "سر درد (Kopfschmerzen)۔"},
            {"question_de": "Zu wem geht Anna?", "question_en": "Who does Anna go to?", "question_ur": "آنا کس کے پاس جاتی ہے؟", "options": ["Zum Lehrer", "Zum Arzt", "Zum Chef", "Zur Mutter"], "correct_option": 1, "explanation_en": "To the doctor.", "explanation_ur": "ڈاکٹر کے پاس۔"},
            {"question_de": "Was soll Anna trinken?", "question_en": "What should Anna drink?", "question_ur": "آنا کو کیا پینا چاہیے؟", "options": ["Kaffee", "Viel Wasser", "Saft", "Milch"], "correct_option": 1, "explanation_en": "Plenty of water.", "explanation_ur": "زیادہ پانی۔"},
            {"question_de": "Was empfiehlt der Arzt noch?", "question_en": "What else does the doctor recommend?", "question_ur": "ڈاکٹر اور کیا مشورہ دیتا ہے؟", "options": ["Sport machen", "Ausruhen", "Einkaufen", "Arbeiten"], "correct_option": 1, "explanation_en": "Get rest (Ausruhen).", "explanation_ur": "آرام کریں (Ausruhen)۔"}
        ]
    }
]

def get_random_unseen_listening_scenario(user_id: str) -> dict:
    import random
    conn = get_db_connection()
    cursor = conn.cursor()
    completed_rows = cursor.execute(
        "SELECT topic_summary FROM completed_topics WHERE user_id = ? AND category = 'German Listening'", (user_id,)
    ).fetchall()
    conn.close()
    
    seen_titles = [r["topic_summary"] for r in completed_rows if r["topic_summary"]]
    unseen = [s for s in DYNAMIC_LISTENING_SCENARIOS if not any(s["title"] in t for t in seen_titles)]
    if not unseen:
        unseen = DYNAMIC_LISTENING_SCENARIOS
    return random.choice(unseen)

class ListeningGenRequest(BaseModel):
    user_id: str
    cefr_level: Optional[str] = "ZERO"

@app.post("/api/listening/generate")
def generate_listening_scenario(req: ListeningGenRequest):
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    guardrail = CEFR_GERMAN_GUARDRAILS.get(level, CEFR_GERMAN_GUARDRAILS["ZERO"])
    anti_rep = build_anti_repetition_prompt(req.user_id)

    prompt = f"""
{anti_rep}
CEFR German Guardrail: {guardrail}

Generate ONE German Listening Comprehension Scenario suitable for level '{level}'.
Provide a 2 to 3 sentence German narrative story/scenario and 5 multiple-choice comprehension questions.
Include English and Urdu (اردو) translations for explanations and questions.

Return ONLY a valid JSON object with exact keys:
- "title": string (Scenario title in German with English translation e.g. "Im Café (At the Café)")
- "narrative_de": string (The full German audio script text to be read aloud)
- "narrative_en": string (English translation of script)
- "narrative_ur": string (Urdu translation of script in Urdu script)
- "topic": string (Theme topic of scenario)
- "questions": array of 5 objects, each containing:
    - "question_de": string (Question in German)
    - "question_en": string (Question in English)
    - "question_ur": string (Question in Urdu)
    - "options": array of 4 strings (Option choices in German)
    - "correct_option": integer (0, 1, 2, or 3 representing the zero-indexed correct option)
    - "explanation_en": string (Why this option is correct in English)
    - "explanation_ur": string (Why this option is correct in Urdu script)
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a master German listening exam author fluent in German, English, and Urdu (اردو). Return strictly valid JSON objects."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
        scenario = json.loads(content)
        return {"success": True, "scenario": scenario}
    except Exception as e:
        print(f"[Gemini Listening API Error]: {e}")
        scenario = get_random_unseen_listening_scenario(req.user_id)
        return {"success": True, "is_fallback": True, "notice": f"Dynamic Pool Mode ({str(e)})", "scenario": scenario}


class ListeningSubmitRequest(BaseModel):
    user_id: str
    scenario_title: str
    user_answers: List[int]
    correct_answers: List[int]
    cefr_level: Optional[str] = "ZERO"

@app.post("/api/listening/submit")
def submit_listening_answers(req: ListeningSubmitRequest):
    total = len(req.correct_answers)
    if total == 0:
        return {"success": False, "error": "No questions provided"}
    
    correct_count = 0
    for u_ans, c_ans in zip(req.user_answers, req.correct_answers):
        if u_ans == c_ans:
            correct_count += 1
            
    score_percentage = round((correct_count / total) * 100, 1)
    passed = score_percentage >= 70.0
    
    # Log completed topic
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Listening', ?)",
        (req.user_id, f"Listening: {req.scenario_title}")
    )
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "score_percentage": score_percentage,
        "correct_count": correct_count,
        "total_questions": total,
        "passed": passed,
        "feedback_en": f"You scored {score_percentage}% ({correct_count}/{total} correct). Great listening practice!" if passed else f"You scored {score_percentage}%. Try listening again to catch key details.",
        "feedback_ur": f"آپ نے {score_percentage}% اسکور حاصل کیا ({correct_count}/{total} درست)۔ شاندار مشق!" if passed else f"آپ نے {score_percentage}% اسکور حاصل کیا۔ دوبارہ غور سے سنیں۔"
    }


# --- MODULE 4: SPEAKING & PRONUNCIATION ---

class SpeakingGenRequest(BaseModel):
    user_id: str
    cefr_level: Optional[str] = "ZERO"

@app.post("/api/speaking/generate")
def generate_speaking_prompt(req: SpeakingGenRequest):
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    guardrail = CEFR_GERMAN_GUARDRAILS.get(level, CEFR_GERMAN_GUARDRAILS["ZERO"])
    anti_rep = build_anti_repetition_prompt(req.user_id)

    prompt = f"""
{anti_rep}
CEFR German Guardrail: {guardrail}

Generate ONE German Speaking & Pronunciation Prompt for level '{level}'.
The prompt should ask the user to respond in spoken German (e.g. self introduction, describing their day, ordering food, or sharing hobbies).

Return strictly JSON with exact keys:
- "topic": string (Theme title)
- "prompt_de": string (Speaking task prompt in German)
- "prompt_en": string (English translation and instructions)
- "prompt_ur": string (Urdu translation and instructions in Urdu script)
- "sample_phrases": array of strings (3-4 suggested German phrases to include)
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a master German speaking test prompt creator fluent in German, English, and Urdu (اردو). Return strictly valid JSON objects."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=400
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
        prompt_data = json.loads(content)
        return {"success": True, "prompt": prompt_data}
    except Exception as e:
        fallback_prompt = {
            "topic": "Sich Vorstellen (Self Introduction)",
            "prompt_de": "Stellen Sie sich kurz auf Deutsch vor (Name, Woher Sie kommen, Wohnort).",
            "prompt_en": "Briefly introduce yourself in German (Name, Where you are from, Where you live).",
            "prompt_ur": "جرمن میں اپنا مختصر تعارف کروائیں (نام، آپ کہاں سے ہیں، آپ کہاں رہتے ہیں)۔",
            "sample_phrases": ["Ich heiße...", "Ich komme aus...", "Ich wohne in..."]
        }
        return {"success": True, "is_fallback": True, "prompt": fallback_prompt}


class SpeakingEvalRequest(BaseModel):
    user_id: str
    cefr_level: Optional[str] = "ZERO"
    prompt_text: str
    user_transcript: str

@app.post("/api/speaking/evaluate")
def evaluate_speaking_response(req: SpeakingEvalRequest):
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    
    grading_prompt = f"""
Evaluate this transcribed speech for a {level} German learner.
Task Prompt: "{req.prompt_text}"
User Transcribed Speech: "{req.user_transcript}"

Grade the following 4 criteria out of 100 based on CEFR level '{level}' expectations:
1. Grammatical Accuracy (0-100)
2. Vocabulary Range (0-100)
3. Task Relevance (0-100)
4. Fluency (based on sentence structure cohesion, 0-100)

Return strictly valid JSON with exact keys:
- "grammatical_accuracy": integer (0-100)
- "vocabulary_range": integer (0-100)
- "task_relevance": integer (0-100)
- "fluency": integer (0-100)
- "overall_score": integer (0-100, average of the 4 scores)
- "passed": boolean (true if overall_score >= 70)
- "feedback_en": string (2-sentence feedback summary in English highlighting strengths & improvements)
- "feedback_ur": string (2-sentence feedback summary in Urdu script)
- "ideal_response_de": string (A clean, natural German example response)
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional German speech evaluator. Return strictly valid JSON."},
                {"role": "user", "content": grading_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
        eval_result = json.loads(content)
        
        # Log completed topic
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Speaking', ?)",
            (req.user_id, f"Speaking: {req.prompt_text[:30]}")
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "evaluation": eval_result}
    except Exception as e:
        # Fallback grading logic
        text_len = len(req.user_transcript.strip().split())
        base_score = min(100, max(50, text_len * 15))
        eval_result = {
            "grammatical_accuracy": base_score,
            "vocabulary_range": base_score,
            "task_relevance": base_score + 5 if base_score < 95 else 100,
            "fluency": base_score - 5 if base_score > 55 else 50,
            "overall_score": base_score,
            "passed": base_score >= 70,
            "feedback_en": f"Good effort! You spoke {text_len} words clearly in German.",
            "feedback_ur": f"بہت اچھی کوشش! آپ نے جرمن میں {text_len} الفاظ بولے۔",
            "ideal_response_de": "Ich heiße Ali. Ich komme aus Pakistan und ich wohne in Berlin."
        }
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO completed_topics (user_id, category, topic_summary) VALUES (?, 'German Speaking', ?)",
            (req.user_id, f"Speaking: {req.prompt_text[:30]}")
        )
        conn.commit()
        conn.close()
        return {"success": True, "is_fallback": True, "evaluation": eval_result}


# ==============================================================================
# PHASE 4: THE PROMOTION EXAM ENGINE (GATEKEEPER LOGIC)
# ==============================================================================

PROMOTION_MAP = {
    "ZERO": "A1",
    "A1": "A2",
    "A2": "B1",
    "B1": "B1"
}

class ExamGenRequest(BaseModel):
    user_id: str
    cefr_level: Optional[str] = "ZERO"

@app.post("/api/exam/generate")
def generate_promotion_exam(req: ExamGenRequest):
    """
    Generates a full 4-module Promotion Exam:
    1. Module 1: Vocab (10 fill-in-the-blank questions)
    2. Module 2: Written Grammar (10 sentence corrections)
    3. Module 3: Listening (Scenario + 5 MCQs)
    4. Module 4: Speaking Prompt
    """
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    guardrail = CEFR_GERMAN_GUARDRAILS.get(level, CEFR_GERMAN_GUARDRAILS["ZERO"])
    anti_rep = build_anti_repetition_prompt(req.user_id)

    prompt = f"""
{anti_rep}
CEFR German Guardrail: {guardrail}

Generate ONE complete Promotion Exam for German CEFR level '{level}'.
The exam MUST contain 4 distinct modules:

1. "module1_vocab": An array of 10 fill-in-the-blank German vocabulary questions. Each question must have:
   - "question_sentence": string (German sentence with "____" blank)
   - "options": array of 4 strings (Option choices in German)
   - "correct_option": integer (0, 1, 2, or 3)
   - "hint_en": string (English hint)
   - "hint_ur": string (Urdu hint)

2. "module2_grammar": An array of 10 German sentence correction tasks. Each item must have:
   - "incorrect_sentence": string (Incorrect German sentence)
   - "target_concept": string (German grammar rule concept)
   - "correct_sentence": string (Ideal corrected German sentence)
   - "hint_en": string
   - "hint_ur": string

3. "module3_listening": A German listening scenario object containing:
   - "title": string (Scenario title)
   - "narrative_de": string (Audio script text)
   - "narrative_en": string
   - "narrative_ur": string
   - "questions": array of 5 MCQ objects (each with question_de, question_en, question_ur, options array of 4, correct_option index 0-3, explanation_en, explanation_ur)

4. "module4_speaking": A German speaking test prompt object containing:
   - "topic": string
   - "prompt_de": string (German speaking instructions)
   - "prompt_en": string
   - "prompt_ur": string
   - "sample_phrases": array of 3 German target phrases

Return strictly valid JSON only with exact keys: "module1_vocab", "module2_grammar", "module3_listening", "module4_speaking".
"""
    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a master German CEFR exam author. Return strictly valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=2500
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join([l for l in lines if not l.startswith("```")])
        exam_data = json.loads(content)
        return {"success": True, "cefr_level": level, "target_promotion_level": PROMOTION_MAP.get(level, "A1"), "exam": exam_data}
    except Exception as e:
        fallback_exam = {
            "module1_vocab": [
                {
                    "question_sentence": "Guten ____! Wie geht es Ihnen?",
                    "options": ["Tag", "Nacht", "Wasser", "Hund"],
                    "correct_option": 0,
                    "hint_en": "Greeting for 'Good day'",
                    "hint_ur": "دن کا سلام"
                },
                {
                    "question_sentence": "Ich trinke kaltes ____.",
                    "options": ["Brot", "Wasser", "Tisch", "Auto"],
                    "correct_option": 1,
                    "hint_en": "Beverage: Water",
                    "hint_ur": "پانی"
                },
                {
                    "question_sentence": "Vielen ____ für Ihre Hilfe!",
                    "options": ["Dank", "Bitte", "Hallo", "Tschüss"],
                    "correct_option": 0,
                    "hint_en": "Thank you very much",
                    "hint_ur": "بہت شکریہ"
                },
                {
                    "question_sentence": "Wo ist der ____?",
                    "options": ["Bahnhof", "Käse", "Morgen", "Kalt"],
                    "correct_option": 0,
                    "hint_en": "Train station",
                    "hint_ur": "ریلوے اسٹیشن"
                },
                {
                    "question_sentence": "Mein ____ ist Ali.",
                    "options": ["Name", "Stuhl", "Grün", "Trinken"],
                    "correct_option": 0,
                    "hint_en": "Name",
                    "hint_ur": "نام"
                },
                {
                    "question_sentence": "Ich ____ aus Deutschland.",
                    "options": ["komme", "geht", "ist", "haben"],
                    "correct_option": 0,
                    "hint_en": "I come from...",
                    "hint_ur": "میں آ رہا ہوں / کا رہنے والا ہوں"
                },
                {
                    "question_sentence": "Das ist ein schönes ____.",
                    "options": ["Haus", "Sprechen", "Heute", "Danke"],
                    "correct_option": 0,
                    "hint_en": "House",
                    "hint_ur": "گھر"
                },
                {
                    "question_sentence": "Ich esse einen leckeren ____.",
                    "options": ["Kuchen", "Strasse", "Fenster", "Nein"],
                    "correct_option": 0,
                    "hint_en": "Cake",
                    "hint_ur": "کیک"
                },
                {
                    "question_sentence": "Wie viel ____ das?",
                    "options": ["kostet", "schreiben", "gehen", "sehr"],
                    "correct_option": 0,
                    "hint_en": "How much does it cost?",
                    "hint_ur": "اس کی قیمت کتنی ہے؟"
                },
                {
                    "question_sentence": "Auf ____!",
                    "options": ["Wiedersehen", "Morgen", "Guten", "Sehr"],
                    "correct_option": 0,
                    "hint_en": "Goodbye",
                    "hint_ur": "خدا حافظ"
                }
            ],
            "module2_grammar": [
                {
                    "incorrect_sentence": "Ich kommt aus Deutschland.",
                    "target_concept": "Verb Conjugation (kommen)",
                    "correct_sentence": "Ich komme aus Deutschland.",
                    "hint_en": "First person singular ends in -e",
                    "hint_ur": "ضمیر Ich کے ساتھ فعل کے آخر میں e آئے گا"
                },
                {
                    "incorrect_sentence": "Du habe ein Buch.",
                    "target_concept": "Verb Conjugation (haben)",
                    "correct_sentence": "Du hast ein Buch.",
                    "hint_en": "Second person singular 'Du' takes 'hast'",
                    "hint_ur": "ضمیر Du کے ساتھ hast آئے گا"
                },
                {
                    "incorrect_sentence": "Der Frau ist nett.",
                    "target_concept": "Gender Articles (die Frau)",
                    "correct_sentence": "Die Frau ist nett.",
                    "hint_en": "Frau takes feminine article 'die'",
                    "hint_ur": "خاتون کے لیے مونث حرف علت die آئے گا"
                },
                {
                    "incorrect_sentence": "Wir ist zu Hause.",
                    "target_concept": "Verb Conjugation (sein)",
                    "correct_sentence": "Wir sind zu Hause.",
                    "hint_en": "Plural 'Wir' takes 'sind'",
                    "hint_ur": "جمع Wir کے ساتھ sind آئے گا"
                },
                {
                    "incorrect_sentence": "Er trinken Kaffee.",
                    "target_concept": "Verb Conjugation (trinken)",
                    "correct_sentence": "Er trinkt Kaffee.",
                    "hint_en": "Third person 'Er' takes '-t'",
                    "hint_ur": "ضمیر Er کے ساتھ فعل کا آخر t ہوگا"
                },
                {
                    "incorrect_sentence": "Ich kaufe ein der Apfel.",
                    "target_concept": "Accusative Article (den Apfel)",
                    "correct_sentence": "Ich kaufe den Apfel.",
                    "hint_en": "Der changes to den in accusative",
                    "hint_ur": "مفعولی حالت میں der تبدیل ہو کر den بنتا ہے"
                },
                {
                    "incorrect_sentence": "Sie wohnen in Berlin?",
                    "target_concept": "Question Word Order",
                    "correct_sentence": "Wohnen Sie in Berlin?",
                    "hint_en": "In questions, verb comes first",
                    "hint_ur": "سوالیہ جملے میں فعل پہلے آتا ہے"
                },
                {
                    "incorrect_sentence": "Das Auto ist sehr schönes.",
                    "target_concept": "Adjective Predicate Form",
                    "correct_sentence": "Das Auto ist sehr schön.",
                    "hint_en": "Predicate adjectives take no ending",
                    "hint_ur": "خبر کے طور پر صفت کا کوئی اضافہ نہیں ہوتا"
                },
                {
                    "incorrect_sentence": "Mein Vater bin Lehrer.",
                    "target_concept": "Verb Conjugation (sein)",
                    "correct_sentence": "Mein Vater ist Lehrer.",
                    "hint_en": "Mein Vater is 3rd person singular 'ist'",
                    "hint_ur": "والد کے لیے ist استعمال ہوگا"
                },
                {
                    "incorrect_sentence": "Ich trinke Kaffee nicht.",
                    "target_concept": "Negation Order (keinen / nicht)",
                    "correct_sentence": "Ich trinke keinen Kaffee.",
                    "hint_en": "Use 'keinen' for indefinite nouns",
                    "hint_ur": "اسم نکرہ کی نفی کے لیے keinen استعمال کریں"
                }
            ],
            "module3_listening": {
                "title": "Guten Tag im Café (At the Café)",
                "narrative_de": "Hallo! Mein Name ist Maria. Ich bin im Café in Berlin. Ich trinke einen Kaffee und esse einen Kuchen. Es schmeckt sehr gut!",
                "narrative_en": "Hello! My name is Maria. I am at the café in Berlin. I am drinking a coffee and eating a cake. It tastes very good!",
                "narrative_ur": "ہیلو! میرا نام ماریا ہے۔ میں برلن کے کیفے میں ہوں۔ میں کافی پی رہی ہوں اور کیک کھا رہی ہوں۔ یہ بہت مزیدار ہے!",
                "topic": "Cafe Conversation",
                "questions": [
                    {
                        "question_de": "Wo ist Maria?",
                        "question_en": "Where is Maria?",
                        "question_ur": "ماریا کہاں ہے؟",
                        "options": ["Im Café in Berlin", "Im Supermarkt", "Zu Hause", "Im Bahnhof"],
                        "correct_option": 0,
                        "explanation_en": "Maria is at the café in Berlin.",
                        "explanation_ur": "ماریا برلن کے کیفے میں ہے۔"
                    },
                    {
                        "question_de": "Was trinkt Maria?",
                        "question_en": "What is Maria drinking?",
                        "question_ur": "ماریا کیا پی رہی ہے؟",
                        "options": ["Tee", "Einen Kaffee", "Wasser", "Milch"],
                        "correct_option": 1,
                        "explanation_en": "She drinks coffee.",
                        "explanation_ur": "وہ کافی پی رہی ہے۔"
                    },
                    {
                        "question_de": "Was isst Maria?",
                        "question_en": "What is Maria eating?",
                        "question_ur": "ماریا کیا کھا رہی ہے؟",
                        "options": ["Brot", "Einen Kuchen", "Pizza", "Apfel"],
                        "correct_option": 1,
                        "explanation_en": "She is eating cake.",
                        "explanation_ur": "وہ کیک کھا رہی ہے۔"
                    },
                    {
                        "question_de": "In welcher Stadt ist Maria?",
                        "question_en": "In which city is Maria?",
                        "question_ur": "ماریا کس شہر میں ہے؟",
                        "options": ["München", "Hamburg", "Berlin", "Frankfurt"],
                        "correct_option": 2,
                        "explanation_en": "In Berlin.",
                        "explanation_ur": "برلن میں۔"
                    },
                    {
                        "question_de": "Wie schmeckt das Essen?",
                        "question_en": "How does the food taste?",
                        "question_ur": "کھانا کیسا ہے؟",
                        "options": ["Nicht gut", "Sehr gut", "Schlecht", "Kalt"],
                        "correct_option": 1,
                        "explanation_en": "Very good.",
                        "explanation_ur": "بہت مزیدار۔"
                    }
                ]
            },
            "module4_speaking": {
                "topic": "Sich Vorstellen (Self Introduction)",
                "prompt_de": "Stellen Sie sich kurz auf Deutsch vor (Name, Woher Sie kommen, Wohnort).",
                "prompt_en": "Briefly introduce yourself in German (Name, Where you are from, Where you live).",
                "prompt_ur": "جرمن میں اپنا مختصر تعارف کروائیں (نام، آپ کہاں سے ہیں، آپ کہاں رہتے ہیں)۔",
                "sample_phrases": ["Ich heiße...", "Ich komme aus...", "Ich wohne in..."]
            }
        }
        return {"success": True, "is_fallback": True, "cefr_level": level, "target_promotion_level": PROMOTION_MAP.get(level, "A1"), "exam": fallback_exam}


class ExamSubmitRequest(BaseModel):
    user_id: str
    cefr_level: str
    vocab_user_answers: List[int]
    vocab_correct_answers: List[int]
    grammar_user_answers: List[str]
    grammar_correct_sentences: List[str]
    listening_user_answers: List[int]
    listening_correct_answers: List[int]
    speaking_prompt_text: str
    speaking_user_transcript: str

@app.post("/api/exam/evaluate")
def evaluate_promotion_exam(req: ExamSubmitRequest):
    level = req.cefr_level.upper() if req.cefr_level else "ZERO"
    
    # 1. Vocab Score (20% Weight)
    vocab_total = len(req.vocab_correct_answers)
    vocab_correct = 0
    for u_ans, c_ans in zip(req.vocab_user_answers, req.vocab_correct_answers):
        if u_ans == c_ans:
            vocab_correct += 1
    vocab_score = round((vocab_correct / vocab_total) * 100, 1) if vocab_total > 0 else 0.0

    # 2. Grammar Score (20% Weight)
    grammar_total = len(req.grammar_correct_sentences)
    grammar_correct = 0
    for u_ans, c_ans in zip(req.grammar_user_answers, req.grammar_correct_sentences):
        u_clean = u_ans.strip().lower().rstrip('.!?')
        c_clean = c_ans.strip().lower().rstrip('.!?')
        if u_clean == c_clean or c_clean in u_clean:
            grammar_correct += 1
    grammar_score = round((grammar_correct / grammar_total) * 100, 1) if grammar_total > 0 else 0.0

    # 3. Listening Score (30% Weight)
    listening_total = len(req.listening_correct_answers)
    listening_correct = 0
    for u_ans, c_ans in zip(req.listening_user_answers, req.listening_correct_answers):
        if u_ans == c_ans:
            listening_correct += 1
    listening_score = round((listening_correct / listening_total) * 100, 1) if listening_total > 0 else 0.0

    # 4. Speaking Score (30% Weight)
    words_count = len(req.speaking_user_transcript.strip().split())
    if words_count > 0:
        try:
            client = get_llm_client()
            grading_prompt = f"""
Evaluate this transcribed speech for a {level} German learner taking a promotion exam.
Prompt: "{req.speaking_prompt_text}"
Speech: "{req.speaking_user_transcript}"

Grade out of 100 for 1. Grammatical Accuracy, 2. Vocabulary Range, 3. Task Relevance, 4. Fluency.
Return strictly JSON with:
- "overall_score": integer (0-100)
- "feedback_en": string
- "feedback_ur": string
"""
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a German exam evaluator. Return strictly valid JSON."},
                    {"role": "user", "content": grading_prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                lines = content.splitlines()
                content = "\n".join([l for l in lines if not l.startswith("```")])
            sp_res = json.loads(content)
            speaking_score = float(sp_res.get("overall_score", 85.0))
            sp_feedback_en = sp_res.get("feedback_en", "Good speaking fluency demonstrated.")
            sp_feedback_ur = sp_res.get("feedback_ur", "جرمن بولنے کی اچھی صلاحیت۔")
        except Exception:
            speaking_score = float(min(100, max(50, words_count * 15)))
            sp_feedback_en = f"Clear speech recorded ({words_count} words)."
            sp_feedback_ur = f"جرمن میں {words_count} الفاظ کا جواب دیا گیا۔"
    else:
        speaking_score = 0.0
        sp_feedback_en = "No speech recorded."
        sp_feedback_ur = "کوئی آواز ریکارڈ نہیں کی گئی۔"

    # --- WEIGHTED OVERALL SCORE ---
    overall_score = round(
        (vocab_score * 0.20) + (grammar_score * 0.20) + (listening_score * 0.30) + (speaking_score * 0.30),
        1
    )

    # --- GATEKEEPER PASS CRITERIA ---
    passed = (
        overall_score >= 80.0 and
        vocab_score >= 70.0 and
        grammar_score >= 70.0 and
        listening_score >= 70.0 and
        speaking_score >= 70.0
    )

    next_level = PROMOTION_MAP.get(level, level)

    if passed and next_level != level:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET current_level = ? WHERE user_id = ?", (next_level, req.user_id))
        conn.commit()
        conn.close()

    diagnostic_report = {
        "user_id": req.user_id,
        "current_level": level,
        "promoted_level": next_level if passed else level,
        "passed": passed,
        "overall_score": overall_score,
        "pass_threshold_overall": 80.0,
        "pass_threshold_module": 70.0,
        "module_scores": {
            "vocab": {"score": vocab_score, "weight": "20%", "passed": vocab_score >= 70.0, "raw": f"{vocab_correct}/{vocab_total}"},
            "grammar": {"score": grammar_score, "weight": "20%", "passed": grammar_score >= 70.0, "raw": f"{grammar_correct}/{grammar_total}"},
            "listening": {"score": listening_score, "weight": "30%", "passed": listening_score >= 70.0, "raw": f"{listening_correct}/{listening_total}"},
            "speaking": {"score": speaking_score, "weight": "30%", "passed": speaking_score >= 70.0, "raw": f"{speaking_score}/100"}
        },
        "feedback_en": f"CONGRATULATIONS! You passed the German {level} Promotion Exam and advanced to level {next_level}!" if passed else f"Exam Not Passed. Minimum 80% overall and 70% per module required. Practice your weak modules and try again!",
        "feedback_ur": f"مبارک ہو! آپ نے جرمن {level} کا پروموشن امتحان پاس کر لیا ہے اور لیول {next_level} حاصل کر لیا ہے!" if passed else f"امتحان پاس نہیں ہو سکا۔ تمام ماڈیولز میں کم از کم 70٪ اور مجموعی طور پر 80٪ درکار ہے۔ دوبارہ کوشش کریں۔",
        "speaking_feedback_en": sp_feedback_en,
        "speaking_feedback_ur": sp_feedback_ur
    }

    # Store exam record into SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO exam_history 
        (user_id, target_level, written_score, vocab_score, listening_score, speaking_score, overall_score, passed, feedback_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (req.user_id, level, grammar_score, vocab_score, listening_score, speaking_score, overall_score, passed, json.dumps(diagnostic_report))
    )
    conn.commit()
    conn.close()

    return {"success": True, "evaluation": diagnostic_report}


@app.get("/api/exam/history/{user_id}")
def get_exam_history(user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT * FROM exam_history WHERE user_id = ? ORDER BY exam_id DESC", (user_id,)
    ).fetchall()
    conn.close()
    
    records = []
    for r in rows:
        d = dict(r)
        if d.get("feedback_json"):
            try:
                d["diagnostic"] = json.loads(d["feedback_json"])
            except Exception:
                pass
        records.append(d)
        
    return {"user_id": user_id, "exam_history": records}


