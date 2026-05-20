# Zephyr Assist — Feature & Architecture Reference

This document provides a centralized overview of every feature, component, and technical decision in the Zephyr Assist application.

---

## 1. AI / Tutor Pipeline

### 1.1 LangGraph Tutor Pipeline (`tutor_graph.py`)

The core intelligence of Zephyr Assist is an **8-node LangGraph `StateGraph`** that processes one student message at a time and returns a guided response.

| Node | Purpose |
| --- | --- |
| `classify_intent` | Guardian agent — classifies the student's message as `learning`, `confusion`, or `jailbreak` using structured LLM output |
| `route_intent` | Conditional router — directs the turn to the appropriate response path |
| `evaluate_understanding` | Evaluator agent — scores student understanding (0–100) and identifies mastered concepts and gaps |
| `update_student_state` | Merges evaluation results into the persistent session model using exponential moving average |
| `detect_learning_state` | Converts score, intent, and hint count into a coarse state: `mastered`, `deeply_struggling`, `struggling`, `confused`, or `progressing` |
| `decide_pedagogy` | Selects a teaching strategy: `socratic_question`, `reframe`, `analogy`, `near_answer`, or `celebrate` |
| `generate_hint` | Creates the Socratic tutor response using strategy-specific system prompts |
| `finalize` | Appends messages, increments hint count, and assembles the final response payload |

### 1.2 Intent Classification

Three possible intents:

- **`learning`** — Genuine CS question or follow-up → full evaluation + hint pipeline
- **`confusion`** — Frustration or "I don't understand" → empathetic reframe with a simpler first step
- **`jailbreak`** — Request for direct answers, off-topic asks, or rule-breaking → blocked or unlocked depending on understanding score

### 1.3 Jailbreak Unlock Mechanism

Each session has a `jailbreak_threshold` (default: 70%). If a student's `understanding_score` meets or exceeds this threshold when they request a direct answer, the system unlocks and provides a complete explanation. Below the threshold, the student is encouraged to keep working through the problem.

### 1.4 Adaptive Hint Escalation

The `hint_level` (0–5) controls instructional intensity:

| Level | Behavior |
| --- | --- |
| 0–1 | Pure Socratic questions — no information revealed |
| 2–3 | Guided hints with examples and analogies |
| 4 | Strong hints that almost reveal the answer |
| 5 | Very direct guidance (near-answer strategy) |

The `hint_count` (total hints in a session) is unbounded and displayed in the UI.

### 1.5 Topic Detection (`topics.py`)

A lightweight keyword-matching system that detects 26 CS topics (e.g., "Recursion", "OOP Concepts", "Dynamic Programming") from the student's first message. Falls back to "CS/Programming" if no match is found.

### 1.6 LLM Configuration

- **Provider**: Groq (ultra-fast inference)
- **Model**: `llama-3.3-70b-versatile`
- **Temperature**: 0.2 for classification, 0.3 for evaluation, 0.6–0.7 for responses
- **Structured Output**: Used for `IntentResult` and `EvaluationResult` via LangChain's `with_structured_output()`

---

## 2. Backend (FastAPI)

### 2.1 Authentication System (`db.py`, `main.py`)

| Feature | Implementation |
| --- | --- |
| Password hashing | PBKDF2-SHA256 with 210,000 iterations and random salt |
| JWT tokens | Custom minimal HS256 implementation (no external JWT library) |
| Token lifetime | 7 days |
| Email normalization | Lowercase + trim for case-insensitive lookups |

### 2.2 Email OTP Verification (`email_utils.py`, `db.py`)

- **OTP Generation**: 6-digit cryptographically random codes via `random.SystemRandom()`
- **Storage**: SQLite `otps` table with email, code, and ISO-8601 expiration timestamp
- **Expiry**: 10 minutes; single-use (deleted after successful verification)
- **Email Template**: Branded HTML email with Zephyr Assist green color palette
- **Development Fallback**: If SMTP credentials are not configured, OTP is printed to the server console
- **Current Status**: Disabled by default (`ENABLE_OTP_VERIFICATION = false` in frontend). The backend accepts registrations with or without an OTP.

### 2.3 API Endpoints

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | No | Health check |
| `POST` | `/api/auth/otp/send` | No | Send OTP to email (for registration) |
| `POST` | `/api/auth/register` | No | Create account (OTP optional) |
| `POST` | `/api/auth/login` | No | Authenticate and receive JWT |
| `GET` | `/api/auth/me` | Yes | Get current user profile |
| `GET` | `/api/sessions` | Yes | List all user sessions |
| `POST` | `/api/sessions` | Yes | Create a new session |
| `GET` | `/api/sessions/{id}` | Yes | Get session details |
| `DELETE` | `/api/sessions/{id}` | Yes | Delete a session |
| `POST` | `/api/tutor/message` | Yes | Send message through tutor pipeline |

### 2.4 Database Schema (SQLite)

Four tables:

- **`users`** — `id`, `email`, `password_hash`, `created_at`
- **`sessions`** — Full session state including `understanding_score`, `hint_count`, `struggle_areas`, `concepts_mastered`
- **`messages`** — Individual messages with `role`, `content`, `hint_level`, `intent`, `learning_state`, `strategy`
- **`otps`** — Temporary OTP codes with expiration timestamps

### 2.5 CORS Configuration

Allowed origins include `localhost:5173` with a regex pattern for any localhost port. Custom headers `Authorization`, `Content-Type`, and `X-Groq-Api-Key` are explicitly permitted.

---

## 3. Frontend (React + Vite)

### 3.1 Application Views

| View | Component | Description |
| --- | --- | --- |
| Auth | `AuthView` | Login/Register form with optional OTP verification step |
| Chat | `ChatView` | Main tutoring interface with message bubbles, typing indicator, and composer |
| Dashboard | `Dashboard` | Learning analytics with stat cards, bar charts, topic breakdown, and concept lists |
| Settings | `SettingsView` | Groq API key configuration with save/clear functionality |

### 3.2 State Management

Pure React `useState` + `useEffect` — no external state library. Key state:

- `token` / `user` — Authentication state (JWT persisted in `localStorage`)
- `sessions` / `activeId` — Session list and currently selected session
- `view` — Current view (`chat`, `dashboard`, `settings`)
- `authMode` / `authForm` / `showOtpInput` / `otp` — Registration flow state

### 3.3 API Client (`tutorApi.js`)

A thin wrapper around `fetch()` with:

- Automatic `Authorization` header injection from stored JWT
- `X-Groq-Api-Key` header injection from `localStorage` for the tutor endpoint
- Centralized error handling that extracts `detail` from FastAPI error responses

### 3.4 Design System (`styles.css`)

- **Color Palette**: Light green theme — `#00a97b` (accent), `#5ec2a2` (accent-light), `#eefdf7` (background), `#d9eddf` (secondary)
- **Typography**: Inter font family with systematic weight hierarchy
- **CSS Custom Properties**: All colors, backgrounds, and borders use CSS variables for easy theme changes
- **Responsive Design**: Two breakpoints — 1100px (collapses sidebar to icons) and 680px (stacks layout vertically)

### 3.5 User Experience Details

- **Groq API Key Guard**: If no API key is saved, the user is automatically redirected to the Settings page after login
- **Message Badges**: Each assistant message shows the detected intent and hint level
- **Typing Indicator**: Animated dots during LLM response generation
- **Auto-scroll**: Messages scroll to bottom on new content
- **Session Management**: Create, switch, and delete sessions from the sidebar
- **Error Recovery**: On tutor API failure, the user's message is restored to the draft field

---

## 4. Testing

### Backend Tests (`tests/test_tutor_graph.py`)

- **15 test cases** covering:
  - Tutor graph pipeline with mocked LLM responses
  - Intent classification routing (learning, jailbreak, confusion)
  - Jailbreak threshold unlock behavior
  - Understanding score evaluation and state updates
  - Pedagogy strategy selection
  - Session CRUD via API endpoints
  - Authentication flow including OTP verification
  - Message persistence across sessions

---

## 5. Tech Stack Rationale

| Choice | Reason |
| --- | --- |
| **Groq + Llama 3.3 70B** | Fastest inference for LLMs; structured output support; free tier available |
| **LangGraph** | Clean node-based pipeline with conditional routing; easy to extend with new teaching strategies |
| **FastAPI** | Modern async Python API framework with automatic OpenAPI docs and Pydantic validation |
| **SQLite** | Zero-configuration database perfect for single-server deployments; no external service needed |
| **Custom JWT** | Avoids `PyJWT` dependency; minimal HS256 implementation is sufficient for this use case |
| **PBKDF2-SHA256** | Standard library password hashing (no `bcrypt` dependency); 210K iterations per OWASP recommendation |
| **React 18 + Vite** | Fast dev server with HMR; simple component model without heavy framework overhead |
| **Vanilla CSS** | Full control over the design system; no build-time CSS processing needed |
| **Lucide React** | Lightweight, tree-shakable icon library with consistent design |
