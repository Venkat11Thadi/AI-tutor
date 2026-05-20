const API_BASE_URL = import.meta.env.VITE_TUTOR_API_URL || "http://localhost:8000";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, { token, ...options } = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token),
      ...(options.headers || {}),
    },
  });

  const data = res.status === 204 ? null : await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail || "API error");
  }
  return data;
}

export async function register({ email, password }) {
  return request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login({ email, password }) {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getCurrentUser(token) {
  return request("/api/auth/me", { token });
}

export async function fetchSessions(token) {
  return request("/api/sessions", { token });
}

export async function createSession(token) {
  return request("/api/sessions", { method: "POST", token });
}

export async function deleteSession(token, sessionId) {
  return request(`/api/sessions/${sessionId}`, { method: "DELETE", token });
}

export async function runTutorPipeline({ userMessage, sessionState, sessionId, token }) {
  const body = sessionId
    ? { user_message: userMessage, session_id: sessionId }
    : { user_message: userMessage, session_state: sessionState };

  const headers = {
    "Content-Type": "application/json",
    ...authHeaders(token),
  };

  const customKey = localStorage.getItem("socraticcs_groq_api_key");
  if (customKey) {
    headers["X-Groq-Api-Key"] = customKey;
  }

  const res = await fetch(`${API_BASE_URL}/api/tutor/message`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Tutor API error");
  }

  return {
    response: data.response,
    intent: data.intent,
    updatedState: data.updated_state,
    session: data.session,
    pedagogy: data.pedagogy,
    evaluation: data.evaluation,
    learningState: data.learning_state,
    topic: data.topic,
  };
}
