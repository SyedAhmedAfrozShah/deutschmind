import sys
import os
import json

if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import init_db, get_db_connection
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def run_trilingual_tests():
    print("=" * 70)
    print("RUNNING TRILINGUAL GERMAN LEARNING ENGINE TEST SUITE (German + EN + UR)")
    print("=" * 70)
    
    user_id = "trilingual_test_user"
    
    # 1. User setup
    print("\n[Test 1] Initializing user record for German ZERO level...")
    user_res = client.post("/api/users", json={"user_id": user_id, "current_level": "ZERO"})
    assert user_res.status_code == 200, f"User creation failed: {user_res.text}"
    print(f"PASSED: User setup response: {user_res.json()}")
    
    # 2. Trilingual German Vocabulary Generation
    print("\n[Test 2] Testing Trilingual German Vocabulary Generator (DE + EN + Urdu)...")
    vocab_res = client.post("/api/vocabulary/generate", json={"user_id": user_id, "cefr_level": "ZERO", "count": 4})
    assert vocab_res.status_code == 200, f"Vocab generation failed: {vocab_res.text}"
    vocab_data = vocab_res.json()
    print("Trilingual German Vocabulary Payload:")
    print(json.dumps(vocab_data, indent=2, ensure_ascii=False))
    
    assert vocab_data.get("success") is True, "Vocabulary generation failed"
    items = vocab_data.get("vocabulary", [])
    assert len(items) > 0, "No vocabulary items returned"
    
    first_item = items[0]
    assert "word" in first_item, "Missing German word"
    print(f"PASSED: German Word: '{first_item.get('word')}' | EN: '{first_item.get('definition_en')}' | UR: '{first_item.get('definition_ur')}'")
    
    # 3. Vault Check
    print("\n[Test 3] Verifying SQLite Vault Storage...")
    vault_res = client.get(f"/api/vocabulary/{user_id}")
    assert vault_res.status_code == 200, f"Vault fetch failed: {vault_res.text}"
    vault_data = vault_res.json()
    print(f"PASSED: Vault contains {len(vault_data.get('vocabulary', []))} German vocabulary records.")
    
    # 4. Trilingual German Grammar Generator
    print("\n[Test 4] Testing Trilingual German Grammar Challenge Generator...")
    grammar_gen = client.post("/api/grammar/generate", json={"user_id": user_id, "cefr_level": "ZERO"})
    assert grammar_gen.status_code == 200, f"Grammar gen failed: {grammar_gen.text}"
    grammar_data = grammar_gen.json()
    print("Grammar Challenge Payload:")
    print(json.dumps(grammar_data, indent=2, ensure_ascii=False))
    assert grammar_data.get("success") is True, "Grammar exercise generation failed"
    ex = grammar_data.get("exercise", {})
    assert "instructions_en" in ex or "instructions" in ex, "Missing English instructions"
    assert "incorrect_sentence" in ex, "Missing German incorrect sentence"
    print("PASSED: Trilingual German Grammar Generator working properly.")
    
    # 5. Grammar Answer Submission
    print("\n[Test 5] Submitting Correction for German Grammar Evaluation...")
    submit_payload = {
        "user_id": user_id,
        "incorrect_sentence": ex.get("incorrect_sentence", "Ich kommt aus Deutschland."),
        "user_answer": "Ich komme aus Deutschland.",
        "target_concept": ex.get("target_concept", "Verb Conjugation"),
        "cefr_level": "ZERO"
    }
    submit_res = client.post("/api/grammar/submit", json=submit_payload)
    assert submit_res.status_code == 200, f"Grammar submit failed: {submit_res.text}"
    eval_data = submit_res.json()
    print("Evaluation Payload:")
    print(json.dumps(eval_data, indent=2, ensure_ascii=False))
    assert eval_data.get("success") is True, "Grammar evaluation failed"
    print("PASSED: Trilingual German Grammar submission & evaluation working properly.")

    # 6. Anti-Repetition Check
    print("\n[Test 6] Verifying Anti-Repetition Engine Topics Array...")
    topic_res = client.get(f"/api/topics/{user_id}")
    assert topic_res.status_code == 200, f"Topic fetch failed: {topic_res.text}"
    topic_data = topic_res.json()
    print("Anti-Repetition Logged Topics:")
    print(json.dumps(topic_data, indent=2, ensure_ascii=False))
    assert len(topic_data.get("completed_topics", [])) > 0, "No topics logged into completed_topics"
    print("PASSED: German topics successfully tracked in SQLite.")

    print("\n" + "=" * 70)
    print("TRILINGUAL GERMAN LEARNING ENGINE VERIFIED SUCCESSFULLY!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = run_trilingual_tests()
    if not success:
        sys.exit(1)
