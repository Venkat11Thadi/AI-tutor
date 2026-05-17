from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .models import TutorMessageRequest, TutorMessageResponse
from .tutor_graph import run_tutor_pipeline

app = FastAPI(title="SocraticCS Tutor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/tutor/message", response_model=TutorMessageResponse)
def tutor_message(request: TutorMessageRequest) -> dict:
    return run_tutor_pipeline(
        user_message=request.user_message,
        session_state=request.session_state,
    )
