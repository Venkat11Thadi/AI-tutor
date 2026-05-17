from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


Intent = Literal["learning", "confusion", "jailbreak"]
LearningState = Literal[
    "mastered", "deeply_struggling", "struggling", "confused", "progressing"
]


class SessionMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    hint_level: int | None = None
    intent: str | None = None
    timestamp: str | None = None


class SessionState(BaseModel):
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
    intent: Intent
    reason: str


class EvaluationResult(BaseModel):
    score: int = Field(ge=0, le=100)
    reasoning: str
    concepts_identified: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class Pedagogy(BaseModel):
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
    user_message: str
    session_state: SessionState


class TutorMessageResponse(BaseModel):
    response: str
    intent: Intent
    updated_state: SessionState
    pedagogy: Pedagogy
    evaluation: EvaluationResult | None = None
    learning_state: LearningState | None = None
    topic: str


class TutorGraphState(BaseModel):
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

    def as_graph_input(self) -> dict[str, Any]:
        return self.model_dump()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
