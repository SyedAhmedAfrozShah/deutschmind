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

def run_phase4_tests():
    print("=" * 70)
    print("RUNNING PHASE 4 PROMOTION EXAM GATEWAY TEST SUITE")
    print("=" * 70)

    user_id = "phase4_exam_user"

    # 1. User Setup
    print("\n[Test 1] Initializing user record for German ZERO level...")
    user_res = client.post("/api/users", json={"user_id": user_id, "current_level": "ZERO"})
    assert user_res.status_code == 200, f"User creation failed: {user_res.text}"
    print(f"PASSED: User setup: {user_res.json()}")

    # 2. Exam Generation Test
    print("\n[Test 2] Testing Promotion Exam Generator (/api/exam/generate)...")
    gen_res = client.post("/api/exam/generate", json={"user_id": user_id, "cefr_level": "ZERO"})
    assert gen_res.status_code == 200, f"Exam gen failed: {gen_res.text}"
    gen_data = gen_res.json()
    assert gen_data.get("success") is True, "Exam generation failed"
    assert gen_data.get("target_promotion_level") == "A1", f"Expected target promotion level A1, got {gen_data.get('target_promotion_level')}"
    
    exam = gen_data.get("exam", {})
    assert "module1_vocab" in exam, "Missing module1_vocab"
    assert "module2_grammar" in exam, "Missing module2_grammar"
    assert "module3_listening" in exam, "Missing module3_listening"
    assert "module4_speaking" in exam, "Missing module4_speaking"

    m1 = exam.get("module1_vocab", [])
    m2 = exam.get("module2_grammar", [])
    m3 = exam.get("module3_listening", {})
    m4 = exam.get("module4_speaking", {})

    assert len(m1) == 10, f"Expected 10 vocab questions, got {len(m1)}"
    assert len(m2) == 10, f"Expected 10 grammar tasks, got {len(m2)}"
    assert len(m3.get("questions", [])) == 5, f"Expected 5 listening MCQs, got {len(m3.get('questions', []))}"
    print("PASSED: 4 Exam Modules generated with correct structure & targets.")

    # 3. Exam Submission Test (Passing Case -> Promotion to A1)
    print("\n[Test 3] Testing Exam Submission & Gatekeeper Evaluation (Passing Case)...")
    vocab_ans = [q.get("correct_option", 0) for q in m1]
    grammar_ans = [g.get("correct_sentence", "Ich komme aus Deutschland.") for g in m2]
    listening_ans = [q.get("correct_option", 0) for q in m3.get("questions", [])]

    eval_payload = {
        "user_id": user_id,
        "cefr_level": "ZERO",
        "vocab_user_answers": vocab_ans,
        "vocab_correct_answers": vocab_ans,
        "grammar_user_answers": grammar_ans,
        "grammar_correct_sentences": grammar_ans,
        "listening_user_answers": listening_ans,
        "listening_correct_answers": listening_ans,
        "speaking_prompt_text": m4.get("prompt_de", "Stellen Sie sich vor."),
        "speaking_user_transcript": "Ich heiße Ali. Ich komme aus Pakistan und wohne in Berlin. Ich lerne Deutsch sehr gerne."
    }

    eval_res = client.post("/api/exam/evaluate", json=eval_payload)
    assert eval_res.status_code == 200, f"Exam eval failed: {eval_res.text}"
    eval_data = eval_res.json()
    print("Exam Evaluation Payload:")
    print(json.dumps(eval_data, indent=2, ensure_ascii=False))

    diag = eval_data.get("evaluation", {})
    assert diag.get("passed") is True, "Exam should pass"
    assert diag.get("overall_score") >= 80.0, "Overall score should be >= 80%"
    assert diag.get("promoted_level") == "A1", f"Expected promoted_level A1, got {diag.get('promoted_level')}"
    print(f"PASSED: Exam passed with overall score {diag.get('overall_score')}%! Promoted level: {diag.get('promoted_level')}")

    # 4. Database Level Check
    print("\n[Test 4] Verifying database user level promotion in SQLite 'users' table...")
    u_db = client.get(f"/api/users/{user_id}")
    assert u_db.status_code == 200, f"User fetch failed: {u_db.text}"
    user_db_data = u_db.json()
    assert user_db_data.get("current_level") == "A1", f"Expected SQLite current_level 'A1', got {user_db_data.get('current_level')}"
    print(f"PASSED: SQLite user level promoted to '{user_db_data.get('current_level')}' in database!")

    # 5. Exam History Fetch
    print("\n[Test 5] Fetching SQLite Exam History Log (/api/exam/history/{user_id})...")
    hist_res = client.get(f"/api/exam/history/{user_id}")
    assert hist_res.status_code == 200, f"History fetch failed: {hist_res.text}"
    h_data = hist_res.json()
    exam_records = h_data.get("exam_history", [])
    assert len(exam_records) > 0, "No exam records found in history"
    first_rec = exam_records[0]
    assert first_rec.get("passed") == 1 or first_rec.get("passed") is True, "Exam record should show passed"
    print(f"PASSED: Exam history logged cleanly in SQLite ({len(exam_records)} exam attempt).")

    print("\n" + "=" * 70)
    print("PHASE 4 PROMOTION EXAM GATEWAY VERIFIED SUCCESSFULLY!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = run_phase4_tests()
    if not success:
        sys.exit(1)
