import sqlite3
import json
import os
from backend.models import get_db_connection, init_goethe_vocab_schema

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DATA_DIR = os.path.join(BASE_DIR, "frontend", "data")

def export_sqlite_to_static_json():
    """
    Exports SQLite tables (goethe_vocabulary and grammar_sentences) to static JSON files
    for 100% serverless static deployment on GitHub Pages.
    """
    init_goethe_vocab_schema()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure output data directories exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FRONTEND_DATA_DIR, exist_ok=True)

    # 1. Export Goethe Vocabulary Table
    cursor.execute("""
    SELECT german_word, cefr_level, english_translation, urdu_translation, example_sentence 
    FROM goethe_vocabulary 
    ORDER BY cefr_level, german_word;
    """)
    vocab_rows = cursor.fetchall()
    vocab_list = [dict(row) for row in vocab_rows]

    # If DB table is empty, insert default Goethe vocabulary records
    if not vocab_list:
        vocab_list = [
            {"german_word": "Guten Morgen", "cefr_level": "A1", "english_translation": "Good morning", "urdu_translation": "صبح بخیر", "example_sentence": "Guten Morgen, wie geht es Ihnen?"},
            {"german_word": "die Fahrkarte", "cefr_level": "A1", "english_translation": "Train ticket", "urdu_translation": "سفر کا ٹکٹ", "example_sentence": "Ich muss eine Fahrkarte kaufen."},
            {"german_word": "die Versicherung", "cefr_level": "A2", "english_translation": "Insurance", "urdu_translation": "انشورنس / بیمہ", "example_sentence": "Haben Sie eine Krankenversicherung?"},
            {"german_word": "die Arbeitslosigkeit", "cefr_level": "B1", "english_translation": "Unemployment", "urdu_translation": "بے روزگاری", "example_sentence": "Die Arbeitslosigkeit sinkt kontinuierlich."}
        ]

    # 2. Export Grammar Sentences Table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grammar_sentences';")
    grammar_table_exists = cursor.fetchone()
    
    grammar_list = []
    if grammar_table_exists:
        cursor.execute("""
        SELECT id, german, english, urdu, cefr, topic, rule_hint 
        FROM grammar_sentences 
        ORDER BY cefr, id;
        """)
        grammar_rows = cursor.fetchall()
        grammar_list = [dict(row) for row in grammar_rows]

    if not grammar_list:
        grammar_list = [
            {"target_concept": "Goethe A1: V2 Word Order", "incorrect_sentence": "Heute ich fahre nach Frankfurt.", "correct_sentence": "Heute fahre ich nach Frankfurt.", "instructions_en": "Place verb in position 2:", "instructions_ur": "فعل کو دوسری جگہ رکھیں:", "hint_en": "Verb 'fahre' MUST be Pos 2.", "hint_ur": "فعل 'fahre' لازمی دوسری جگہ ہونا چاہیے۔", "cefr_level": "A1"},
            {"target_concept": "Goethe A2: Perfekt mit sein", "incorrect_sentence": "Gestern ich habe nach München geflogen.", "correct_sentence": "Gestern bin ich nach München geflogen.", "instructions_en": "Movement verbs use auxiliary 'sein':", "instructions_ur": "حرکت ظاہر کرنے والے افعال کے ساتھ 'sein' کا استعمال کریں:", "hint_en": "Movement verb requires 'bin'.", "hint_ur": "'sein' (bin) کا استعمال کریں۔", "cefr_level": "A2"},
            {"target_concept": "Goethe B1: Nebensatz mit weil", "incorrect_sentence": "Ich lerne Deutsch, weil ich will in Deutschland arbeiten.", "correct_sentence": "Ich lerne Deutsch, weil ich in Deutschland arbeiten will.", "instructions_en": "Subordinate clause pushes conjugated verb to the end:", "instructions_ur": "تابع جملے میں فعل کو آخر میں بھیجیں:", "hint_en": "Verb 'will' goes to the very end.", "hint_ur": "فعل 'will' بالکل آخر میں جاتا ہے۔", "cefr_level": "B1"}
        ]

    # Save to root /data/ and /frontend/data/
    paths_to_save = [
        (os.path.join(DATA_DIR, "vocab.json"), vocab_list),
        (os.path.join(DATA_DIR, "grammar.json"), grammar_list),
        (os.path.join(FRONTEND_DATA_DIR, "vocab.json"), vocab_list),
        (os.path.join(FRONTEND_DATA_DIR, "grammar.json"), grammar_list)
    ]

    for path, data_obj in paths_to_save:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data_obj, f, ensure_ascii=False, indent=2)
        safe_path = path.encode('ascii', 'replace').decode('ascii')
        print(f"Exported static data -> {safe_path} ({len(data_obj)} items)")

    conn.close()
    print("\n[Success] Static JSON Export Complete!")

if __name__ == "__main__":
    export_sqlite_to_static_json()
