import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.db.database import init_db  # noqa: E402
from app.tools.vitals_rules import evaluate_vitals  # noqa: E402
from app.tools.emergency_check import check_emergency_symptoms  # noqa: E402
from app.db import memory_store  # noqa: E402

init_db()
client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_vitals_rules_normal():
    result = evaluate_vitals(heart_rate=72, sys_bp=120, dia_bp=80, oxygen=98, temperature=37.0, ecg="Normal")
    assert result["status"] == "Normal"
    assert result["flags"] == []


def test_vitals_rules_critical_low_oxygen():
    result = evaluate_vitals(heart_rate=72, sys_bp=120, dia_bp=80, oxygen=85, temperature=37.0, ecg="Normal")
    assert result["status"] == "Critical"
    assert any("Oxygen" in f for f in result["flags"])


def test_vitals_rules_extreme_value_does_not_crash():
    # No more hard Pydantic bounds - the rule engine must handle wild values gracefully.
    result = evaluate_vitals(heart_rate=999, sys_bp=1, dia_bp=1, oxygen=1, temperature=99.0, ecg="Abnormal")
    assert result["status"] == "Critical"


def test_emergency_check_positive():
    result = check_emergency_symptoms("I have severe chest pain and difficulty breathing")
    assert result["is_emergency"] is True


def test_emergency_check_negative():
    result = check_emergency_symptoms("I have a mild headache")
    assert result["is_emergency"] is False


def test_memory_store_roundtrip():
    memory_store.clear_history("test-user-123")
    memory_store.add_turn("test-user-123", "hello", "hi there")
    history = memory_store.get_history("test-user-123")
    assert history == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    memory_store.clear_history("test-user-123")
    assert memory_store.get_history("test-user-123") == []


def test_memory_store_rolls_over_when_full():
    # MAX_TURNS is 5 -> 10 stored messages max. Adding 8 turns (16 messages)
    # should leave only the most recent 5 turns; the oldest ones are dropped.
    user = "cycle-test-user"
    memory_store.clear_history(user)
    for i in range(8):
        memory_store.add_turn(user, f"question {i}", f"answer {i}")

    history = memory_store.get_history(user)
    assert len(history) == 10  # 5 turns * 2 messages
    # oldest surviving turn should be "question 3", not "question 0"
    assert history[0] == {"role": "user", "content": "question 3"}
    assert history[-1] == {"role": "assistant", "content": "answer 7"}
    memory_store.clear_history(user)


def test_assess_endpoint_no_bounds_required():
    # Values that would have been rejected by the old ge/le Pydantic bounds
    # must now be accepted at the schema level (business logic in the rule engine
    # decides what to do with them).
    payload = {
        "username": "Test User",
        "mobile_number": "9999999999",
        "age": 30,
        "heart_rate": 999,
        "sys_bp": 300,
        "dia_bp": 200,
        "oxygen": 10,
        "temperature": 50.0,
        "ecg": "Abnormal",
    }
    resp = client.post("/assess", json=payload)
    # Without OPENAI_API_KEY set in CI this still succeeds via the rule-based fallback.
    assert resp.status_code == 200
    assert resp.json()["status"] == "Critical"
