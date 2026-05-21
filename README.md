# Zephyr Assist — AI-Powered CS Tutor

Zephyr Assist is a Socratic AI tutoring application for computer science and programming. Instead of giving direct answers, it guides students to discover solutions themselves through progressively detailed hints, analogies, and Socratic questioning.

## Live Deployment

- **Frontend (Vercel)**: [website link](https://ai-tutor-aj5l.vercel.app/)
- **Backend (Render)**: [https://ai-tutor-w6jf.onrender.com](https://ai-tutor-w6jf.onrender.com)


## Key Features

- **Socratic Tutoring Pipeline** — An 8-node LangGraph pipeline that classifies student intent, evaluates understanding, selects a teaching strategy, and generates guided responses.
- **Adaptive Hint System** — Hints escalate from gentle nudges to strong clues over multiple turns, with a configurable "jailbreak threshold" that unlocks direct answers once a student demonstrates sufficient understanding.
- **Session Persistence** — Conversations are stored in SQLite with per-user authentication, so students can resume from where they left off.
- **Progress Dashboard** — Visual overview of learning stats, understanding scores, topics studied, and concepts mastered.
- **User-Supplied API Key** — Users provide their own Groq API key via the Settings page, stored locally in the browser.
- **Email OTP Verification** — Optional email verification during registration (currently disabled; toggle `ENABLE_OTP_VERIFICATION` in `App.jsx` to enable).

## Tech Stack

| Layer     | Technology                                                  |
| --------- | ----------------------------------------------------------- |
| LLM       | [Groq](https://groq.com) — Llama 3.3 70B Versatile         |
| AI Graph  | [LangGraph](https://github.com/langchain-ai/langgraph)      |
| Backend   | [FastAPI](https://fastapi.tiangolo.com) + Python 3.11+       |
| Database  | SQLite (via stdlib `sqlite3`)                                |
| Auth      | Custom JWT (HS256) + PBKDF2 password hashing                 |
| Frontend  | [React 18](https://react.dev) + [Vite](https://vite.dev)    |
| Icons     | [Lucide React](https://lucide.dev)                           |
| Styling   | Vanilla CSS with CSS custom properties                       |

## Project Structure

```
├── backend/
│   └── app/
│       ├── __init__.py          # Package marker
│       ├── main.py              # FastAPI routes and middleware
│       ├── db.py                # SQLite persistence layer
│       ├── models.py            # Pydantic request/response schemas
│       ├── tutor_graph.py       # LangGraph tutor pipeline
│       ├── topics.py            # Keyword-based topic detection
│       └── email_utils.py       # OTP email dispatch utilities
├── frontend/
│   └── src/
│       ├── App.jsx              # React application (all components)
│       ├── main.jsx             # Vite entry point
│       ├── styles.css           # Complete CSS design system
│       └── lib/
│           └── tutorApi.js      # API client for backend communication
├── tests/
│   └── test_tutor_graph.py      # Backend integration tests
├── docs/
│   └── tutor-graph.md           # LangGraph pipeline documentation
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Pytest configuration
└── .env                         # Environment variables (not committed)
```

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- A **Groq API key** — get one free at [console.groq.com/keys](https://console.groq.com/keys)

### 1. Clone the Repository

```bash
git clone https://github.com/Venkat11Thadi/AI-tutor.git
cd AI-tutor
```

### 2. Backend Setup

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root (optional — users can also enter their key in the app):

```env
GROQ_API_KEY=gsk_your_key_here
JWT_SECRET=change-this-to-a-random-secret
```

### 4. Start the Backend

```bash
uvicorn backend.app.main:app --reload
```

The API will be available at `http://localhost:8000`. Verify with `http://localhost:8000/health`.

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

### 6. Using the App

1. Open `http://localhost:5173` in your browser.
2. Register an account (email + password).
3. Enter your Groq API key in the **API Settings** page.
4. Start a new session and ask a CS question!

## Running Tests

```bash
# From the project root
pytest
```

## License

This project is for educational purposes.
