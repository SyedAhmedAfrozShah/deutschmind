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

def run_phase3_tests():
    print("=" * 70)
    print("RUNNING PHASE 3 AUDIO PIPELINE & LISTENING/SPEAKING TEST SUITE")
    print("=" * 70)

    user_id = "phase3_test_user"

    # 1. Setup User
    print("\n[Test 1] Initializing user record for German ZERO level...")
    user_res = client.post("/api/users", json={"user_id": user_id, "current_level": "ZERO"})
    assert user_res.status_code == 200, f"User creation failed: {user_res.text}"
    print(f"PASSED: User setup: {user_res.json()}")

    # 2. TTS Audio Generation Test
    print("\n[Test 2] Testing TTS Audio Generation Endpoint (/api/audio/tts)...")
    tts_payload = {"text": "Guten Tag! Wie geht es Ihnen?", "cefr_level": "ZERO"}
    tts_res = client.post("/api/audio/tts", json=tts_payload)
    if tts_res.status_code == 200:
        print(f"PASSED: Received audio stream MP3 bytes ({len(tts_res.content)} bytes).")
    elif tts_res.status_code == 501:
        print("NOTICE: Backend gTTS not installed/enabled. Frontend Web Speech API fallback active.")
    else:
        print(f"TTS response status: {tts_res.status_code}")

    # 3. Listening Scenario Generator Test
    print("\n[Test 3] Testing Module 3 Listening Scenario Generator (/api/listening/generate)...")
    listening_gen = client.post("/api/listening/generate", json={"user_id": user_id, "cefr_level": "ZERO"})
    assert listening_gen.status_code == 200, f"Listening gen failed: {listening_gen.text}"
    l_data = listening_gen.json()
    print("Listening Scenario Payload:")
    print(json.dumps(l_data, indent=2, ensure_ascii=False))

    assert l_data.get("success") is True, "Listening generation failed"
    sc = l_data.get("scenario", {})
    assert "narrative_de" in sc, "Missing German narrative script"
    assert "questions" in sc, "Missing questions"
    questions = sc.get("questions", [])
    assert len(questions) == 5, f"Expected 5 questions, got {len(questions)}"
    print("PASSED: Module 3 Listening Scenario generated with 5 MCQs.")

    # 4. Listening Answers Submission Test
    print("\n[Test 4] Testing Module 3 Listening Test Submission (/api/listening/submit)...")
    correct_opts = [q.get("correct_option", 0) for q in questions]
    submit_payload = {
        "user_id": user_id,
        "scenario_title": sc.get("title", "Im Café"),
        "user_answers": correct_opts,
        "correct_answers": correct_opts,
        "cefr_level": "ZERO"
    }
    l_submit = client.post("/api/listening/submit", json=submit_payload)
    assert l_submit.status_code == 200, f"Listening submit failed: {l_submit.text}"
    l_result = l_submit.json()
    print("Listening Evaluation Result:")
    print(json.dumps(l_result, indent=2, ensure_ascii=False))
    assert l_result.get("score_percentage") == 100.0, "Expected 100% score for correct answers"
    assert l_result.get("passed") is True, "Listening test should pass"
    print("PASSED: Listening submission evaluation verified.")

    # 5. Speaking Prompt Generator Test
    print("\n[Test 5] Testing Module 4 Speaking Prompt Generator (/api/speaking/generate)...")
    speaking_gen = client.post("/api/speaking/generate", json={"user_id": user_id, "cefr_level": "ZERO"})
    assert speaking_gen.status_code == 200, f"Speaking prompt gen failed: {speaking_gen.text}"
    sp_data = speaking_gen.json()
    print("Speaking Prompt Payload:")
    print(json.dumps(sp_data, indent=2, ensure_ascii=False))
    assert sp_data.get("success") is True, "Speaking prompt generation failed"
    prompt_obj = sp_data.get("prompt", {})
    assert "prompt_de" in prompt_obj, "Missing German prompt text"
    print("PASSED: Module 4 Speaking prompt generated.")

    # 6. Speaking Evaluation Test (4 LLM criteria: Accuracy, Range, Relevance, Fluency)
    print("\n[Test 6] Testing Module 4 Speaking 4-Criterion Evaluation (/api/speaking/evaluate)...")
    sp_eval_payload = {
        "user_id": user_id,
        "cefr_level": "ZERO",
        "prompt_text": prompt_obj.get("prompt_de", "Stellen Sie sich vor."),
        "user_transcript": "Ich heiße Ali. Ich komme aus Pakistan und ich wohne in Berlin. Ich lerne Deutsch."
    }
    sp_eval_res = client.post("/api/speaking/evaluate", json=sp_eval_payload)
    assert sp_eval_res.status_code == 200, f"Speaking eval failed: {sp_eval_res.text}"
    sp_eval_data = sp_eval_res.json()
    print("Speaking Evaluation Result Payload:")
    print(json.dumps(sp_eval_data, indent=2, ensure_ascii=False))

    ev = sp_eval_data.get("evaluation", {})
    assert "grammatical_accuracy" in ev, "Missing grammatical_accuracy score"
    assert "vocabulary_range" in ev, "Missing vocabulary_range score"
    assert "task_relevance" in ev, "Missing task_relevance score"
    assert "fluency" in ev, "Missing fluency score"
    assert "overall_score" in ev, "Missing overall_score"
    print(f"PASSED: Speaking 4-Criterion AI Grader scores: Accuracy={ev.get('grammatical_accuracy')}, Range={ev.get('vocabulary_range')}, Relevance={ev.get('task_relevance')}, Fluency={ev.get('fluency')}, Overall={ev.get('overall_score')}")

    # 7. Verify SQLite Anti-Repetition Vault logging
    print("\n[Test 7] Verifying anti-repetition logging for Listening & Speaking topics...")
    topic_res = client.get(f"/api/topics/{user_id}")
    assert topic_res.status_code == 200, f"Topic fetch failed: {topic_res.text}"
    topics = topic_res.json().get("completed_topics", [])
    print("Logged topics in SQLite:", topics)
    assert len(topics) >= 2, "Expected at least 2 completed topics logged for Phase 3"
    print("PASSED: Phase 3 topics successfully logged in SQLite anti-repetition vault.")

    print("\n" + "=" * 70)
    print("PHASE 3 AUDIO PIPELINE & LISTENING/SPEAKING MODULES VERIFIED SUCCESSFULLY!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = run_phase3_tests()
    if not success:
        sys.exit(1)
