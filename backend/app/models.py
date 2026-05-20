"""Pydantic schemas for the Zephyr Assist tutor API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


Intent = Literal["learning", "confusion", "jailbreak"]
LearningState = Literal[
    "mastered", "deeply_struggling", "struggling", "confused", "progressing"
]


class SessionMessage(BaseModel):
    """A single message exchanged between the student and tutor."""

    role: Literal["user", "assistant"]
    content: str
    hint_level: int | None = None
    intent: str | None = None
    learning_state: str | None = None
    strategy: str | None = None
    timestamp: str | None = None


class SessionState(BaseModel):
    """Persistent session state tracking the student's progress and tutor context."""

    title: str = "Session"
    topic: str = "CS/Programming"
    messages: list[SessionMessage] = Field(default_factory=list)
    hint_count: int = 0
    understanding_score: int = 0
    jailbreak_threshold: int = Field(default=70, ge=70, le=90)
    status: Literal["active", "completed", "abandoned"] = "active"
    struggle_areas: list[str] = Field(default_factory=list)
    concepts_mastered: list[str] = Field(default_factory=list)


class IntentResult(BaseModel):
    """Structured output from the guardian intent classifier."""

    intent: Intent
    reason: str


class EvaluationResult(BaseModel):
    """Structured output from the understanding evaluator."""

    score: int = Field(ge=0, le=100)
    reasoning: str
    concepts_identified: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class Pedagogy(BaseModel):
    """Chosen teaching strategy and hint intensity for the next response."""

    strategy: Literal[
        "blocked",
        "celebrate",
        "analogy",
        "reframe",
        "near_answer",
        "socratic_question",
        "unlocked_answer",
    ]
    hint_level: int = Field(ge=0, le=5)


class TutorMessageRequest(BaseModel):
    """Incoming request body for a single tutor turn."""

    user_message: str
    session_state: SessionState | None = None
    session_id: str | None = None


class TutorMessageResponse(BaseModel):
    """Response payload returned after processing a tutor turn."""

    response: str
    intent: Intent
    updated_state: SessionState
    session: dict[str, Any] | None = None
    pedagogy: Pedagogy
    evaluation: EvaluationResult | None = None
    learning_state: LearningState | None = None
    topic: str


class OtpSendRequest(BaseModel):
    """Request body for sending an OTP verification email."""

    email: str


class AuthRequest(BaseModel):
    """Credentials payload for login."""

    email: str
    password: str = Field(min_length=8)


class RegisterRequest(AuthRequest):
    """Extended auth payload for registration, with optional OTP."""

    otp: str | None = Field(default=None, min_length=6, max_length=6)


class UserResponse(BaseModel):
    """Public-facing user representation (no password hash)."""

    id: str
    email: str
    created_at: str


class AuthResponse(BaseModel):
    """JWT token plus user info returned on successful auth."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TutorGraphState(BaseModel):
    """Full input state passed into the LangGraph tutor pipeline."""

    user_message: str
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    session_state: SessionState
    topic: str = "CS/Programming"
    intent: Intent | None = None
    intent_reason: str | None = None
    evaluation: EvaluationResult | None = None
    learning_state: LearningState | None = None
    pedagogy: Pedagogy | None = None
    response: str | None = None
    updated_state: SessionState | None = None
    groq_api_key: str | None = None

    def as_graph_input(self) -> dict[str, Any]:
        """Serialize to a plain dict suitable for ``StateGraph.invoke``."""
        return self.model_dump()


def utc_timestamp() -> str:
    """Return the current UTC time as an ISO-8601 string.

    Note:
        Equivalent to ``db.utc_now()``; kept here because it is imported
        directly by the tutor graph for message timestamping.
    """
    return datetime.now(timezone.utc).isoformat()
