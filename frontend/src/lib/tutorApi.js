const API_BASE_URL = import.meta.env.VITE_TUTOR_API_URL || "http://localhost:8000";

export async function runTutorPipeline({ userMessage, sessionState }) {
  const res = await fetch(`${API_BASE_URL}/api/tutor/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_message: userMessage,
      session_state: sessionState,
    }),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Tutor API error");
  }

  return {
    response: data.response,
    intent: data.intent,
    updatedState: data.updated_state,
    pedagogy: data.pedagogy,
    evaluation: data.evaluation,
    learningState: data.learning_state,
    topic: data.topic,
  };
}
