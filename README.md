# SocraticCS LangGraph Tutor

This project contains a Python LangGraph backend for the 8-step Socratic CS tutor pipeline.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GROQ_API_KEY="your-groq-key"
uvicorn backend.app.main:app --reload
```

The tutor endpoint is:

```text
POST http://localhost:8000/api/tutor/message
```

The frontend adapter is in `frontend/src/lib/tutorApi.js` and calls the backend instead of Groq directly.

## Test

```powershell
pytest
```
