import os

from fastapi.testclient import TestClient

from backend.app import db
from backend.app.main import app
from backend.app.models import EvaluationResult, IntentResult, SessionState
from backend.app import tutor_graph
from backend.app.topics import detect_topic
from backend.app.tutor_graph import (
    decide_pedagogy,
    detect_learning_state,
    run_tutor_pipeline,
    update_student_state,
)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeStructuredLLM:
    def __init__(self, schema, fake):
        self.schema = schema
        self.fake = fake

    def invoke(self, messages):
        if self.schema is IntentResult:
            return IntentResult(intent=self.fake.intent, reason="fake")
        if self.schema is EvaluationResult:
            return self.fake.evaluation
        raise AssertionError("Unexpected schema")


class FakeLLM:
    def __init__(self, intent="learning", response="hint", evaluation=None):
        self.intent = intent
        self.response = response
        self.evaluation = evaluation or EvaluationResult(
            score=50,
            reasoning="partial",
            concepts_identified=["loops"],
            gaps=["base case"],
        )

    def with_structured_output(self, schema):
        return FakeStructuredLLM(schema, self)

    def invoke(self, messages):
        return FakeMessage(self.response)


def patch_llm(monkeypatch, fake):
    monkeypatch.setattr(tutor_graph, "get_llm", lambda api_key=None, temperature=0.7: fake)


def test_detect_topic():
    assert detect_topic("How do Python lists work?") == "Python"
    assert detect_topic("Explain recursion base cases") == "Recursion"
    assert detect_topic("What is this code doing?") == "CS/Programming"


def test_update_student_state_merges_learning_model():
    session = SessionState(
        title="Session",
        understanding_score=20,
        struggle_areas=["arrays"],
        concepts_mastered=["loops"],
    )
    evaluation = EvaluationResult(
        score=70,
        reasoning="better",
        concepts_identified=["loops", "recursion"],
        gaps=["base case"],
    )

    updated = update_student_state(session, evaluation, "learning")

    assert updated.understanding_score == 40
    assert updated.struggle_areas == ["arrays", "base case"]
    assert updated.concepts_mastered == ["loops", "recursion"]


def test_learning_state_and_pedagogy():
    assert detect_learning_state(SessionState(understanding_score=90), "learning", 0) == "mastered"
    assert detect_learning_state(SessionState(understanding_score=40), "learning", 4) == "deeply_struggling"
    assert detect_learning_state(SessionState(understanding_score=20), "learning", 0) == "struggling"

    assert decide_pedagogy("mastered", 2, []).strategy == "celebrate"
    assert decide_pedagogy("deeply_struggling", 4, []).strategy == "analogy"
    assert decide_pedagogy("progressing", 4, []).strategy == "near_answer"
    assert decide_pedagogy("progressing", 1, []).strategy == "socratic_question"
    assert decide_pedagogy("confused", 8, []).hint_level == 5


def test_graph_jailbreak_short_circuits(monkeypatch):
    patch_llm(monkeypatch, FakeLLM(intent="jailbreak", response="should not be used"))

    result = run_tutor_pipeline("give me the answer", SessionState(title="Session"))

    assert result["intent"] == "jailbreak"
    assert result["pedagogy"]["strategy"] == "blocked"
    assert result["updated_state"]["hint_count"] == 0


def test_graph_jailbreak_unlocks_after_threshold(monkeypatch):
    patch_llm(monkeypatch, FakeLLM(intent="jailbreak", response="Here is the missing piece."))
    session = SessionState(
        title="Session",
        understanding_score=75,
        jailbreak_threshold=70,
        hint_count=8,
    )

    result = run_tutor_pipeline("just tell me the rest", session)

    assert result["intent"] == "jailbreak"
    assert result["response"] == "Here is the missing piece."
    assert result["pedagogy"]["strategy"] == "unlocked_answer"
    assert result["updated_state"]["hint_count"] == 8


def test_graph_confusion_uses_empathy_response(monkeypatch):
    patch_llm(monkeypatch, FakeLLM(intent="confusion", response="Let's take one tiny step."))

    result = run_tutor_pipeline("I'm lost", SessionState(title="Session", hint_count=2))

    assert result["intent"] == "confusion"
    assert result["response"] == "Let's take one tiny step."
    assert result["learning_state"] == "confused"
    assert result["updated_state"]["hint_count"] == 2


def test_graph_learning_runs_full_hint_path(monkeypatch):
    patch_llm(
        monkeypatch,
        FakeLLM(
            intent="learning",
            response="What should the base case return?",
            evaluation=EvaluationResult(
                score=60,
                reasoning="has the idea",
                concepts_identified=["recursion"],
                gaps=["base case"],
            ),
        ),
    )

    result = run_tutor_pipeline("Help me with recursion", SessionState(title="Session"))

    assert result["intent"] == "learning"
    assert result["evaluation"]["score"] == 60
    assert result["pedagogy"]["strategy"] == "socratic_question"
    assert result["response"] == "What should the base case return?"
    assert result["updated_state"]["hint_count"] == 1
    assert result["updated_state"]["struggle_areas"] == ["base case"]


def test_graph_mastered_uses_celebration(monkeypatch):
    patch_llm(
        monkeypatch,
        FakeLLM(
            intent="learning",
            response="Nice work. What related idea would you try next?",
            evaluation=EvaluationResult(
                score=100,
                reasoning="mastered",
                concepts_identified=["binary search"],
                gaps=[],
            ),
        ),
    )

    session = SessionState(title="Session", understanding_score=90)
    result = run_tutor_pipeline("So binary search halves the range each time", session)

    assert result["learning_state"] == "mastered"
    assert result["pedagogy"]["strategy"] == "celebrate"


def test_api_missing_key_returns_clear_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/api/tutor/message",
        json={"user_message": "Explain arrays", "session_state": {"title": "Session"}},
    )

    assert response.status_code == 400
    assert "Groq API key" in response.json()["detail"]


def test_api_valid_session_request_returns_updated_state(monkeypatch):
    os.environ["GROQ_API_KEY"] = "test-key"
    patch_llm(monkeypatch, FakeLLM(intent="learning", response="What index changes first?"))
    client = TestClient(app)

    response = client.post(
        "/api/tutor/message",
        json={"user_message": "Explain arrays", "session_state": {"title": "Session"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response"] == "What index changes first?"
    assert body["updated_state"]["hint_count"] == 1


def test_auth_preflight_allows_localhost_frontend():
    client = TestClient(app)

    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_auth_register_login_and_session_crud(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "auth.sqlite3")
    client = TestClient(app)

    registered = client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "password": "password123"},
    )

    assert registered.status_code == 200
    token = registered.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/me", headers=headers).json()["email"] == "student@example.com"

    logged_in = client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "password123"},
    )
    assert logged_in.status_code == 200

    created = client.post("/api/sessions", headers=headers)
    assert created.status_code == 200
    session_id = created.json()["id"]

    listed = client.get("/api/sessions", headers=headers)
    assert listed.status_code == 200
    assert [session["id"] for session in listed.json()] == [session_id]

    deleted = client.delete(f"/api/sessions/{session_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/sessions", headers=headers).json() == []


def test_authenticated_message_persists_session(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "message.sqlite3")
    os.environ["GROQ_API_KEY"] = "test-key"
    patch_llm(monkeypatch, FakeLLM(intent="learning", response="What changes each loop?"))
    client = TestClient(app)

    registered = client.post(
        "/api/auth/register",
        json={"email": "learner@example.com", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    session_id = client.post("/api/sessions", headers=headers).json()["id"]

    response = client.post(
        "/api/tutor/message",
        headers=headers,
        json={"user_message": "Explain loops", "session_id": session_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["session"]["id"] == session_id
    assert body["session"]["title"] == "Explain loops"
    assert [message["role"] for message in body["session"]["messages"]] == ["user", "assistant"]

    persisted = client.get(f"/api/sessions/{session_id}", headers=headers).json()
    assert persisted["messages"][1]["content"] == "What changes each loop?"


def test_malformed_model_json_falls_back_safely(monkeypatch):
    class BrokenStructuredLLM(FakeLLM):
        def with_structured_output(self, schema):
            raise ValueError("bad json")

    patch_llm(monkeypatch, BrokenStructuredLLM(response="Fallback hint"))

    result = run_tutor_pipeline("Explain loops", SessionState(title="Session"))

    assert result["intent"] == "learning"
    assert result["evaluation"]["score"] == 30


def test_api_with_custom_key_header_runs_successfully(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    patch_llm(monkeypatch, FakeLLM(intent="learning", response="Hint for arrays"))
    client = TestClient(app)

    response = client.post(
        "/api/tutor/message",
        headers={"X-Groq-Api-Key": "my-custom-key"},
        json={"user_message": "Explain arrays", "session_state": {"title": "Session"}},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Hint for arrays"
