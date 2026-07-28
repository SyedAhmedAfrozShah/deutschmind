import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # CREATE TABLE users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        current_level TEXT DEFAULT 'ZERO', 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # CREATE TABLE vocabulary_vault
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vocabulary_vault (
        vocab_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        word TEXT,
        definition TEXT,
        definition_en TEXT,
        definition_ur TEXT,
        example_sentence TEXT,
        example_translation_en TEXT,
        example_translation_ur TEXT,
        cefr_level TEXT,
        mastery_score INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)
    
    # Check if extra columns exist, add if missing for backward compatibility
    existing_cols = [r["name"] for r in cursor.execute("PRAGMA table_info(vocabulary_vault);").fetchall()]
    new_cols = {
        "definition_en": "TEXT",
        "definition_ur": "TEXT",
        "example_translation_en": "TEXT",
        "example_translation_ur": "TEXT"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE vocabulary_vault ADD COLUMN {col_name} {col_type};")

    # CREATE TABLE completed_topics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS completed_topics (
        topic_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        category TEXT, 
        topic_summary TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)
    
    # CREATE TABLE exam_history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exam_history (
        exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        target_level TEXT,
        written_score REAL,
        vocab_score REAL,
        listening_score REAL,
        speaking_score REAL,
        overall_score REAL,
        passed BOOLEAN,
        feedback_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    );
    """)
    
    conn.commit()
    conn.close()
    try:
        print("Database initialized successfully at:", DB_PATH)
    except UnicodeEncodeError:
        print("Database initialized successfully at:", DB_PATH.encode('ascii', 'replace').decode('ascii'))

if __name__ == "__main__":
    init_db()
