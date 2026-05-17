from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .models import AuthRequest, AuthResponse, SessionState, TutorMessageRequest, TutorMessageResponse
from .tutor_graph import run_tutor_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    db.init_db()
    yield


app = FastAPI(title="SocraticCS Tutor API", lifespan=lifespan)
bearer_scheme = HTTPBearer(auto_error=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def title_from_message(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New Session"
    return f"{cleaned[:34]}..." if len(cleaned) > 34 else cleaned


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = db.decode_access_token(credentials.credentials)
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dict(user)


def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    if credentials is None:
        return None
    user_id = db.decode_access_token(credentials.credentials)
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return dict(user)


@app.post("/api/auth/register", response_model=AuthResponse)
def register(request: AuthRequest) -> dict:
    user = db.create_user(request.email, request.password)
    token = db.create_access_token(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> dict:
    user = db.get_user_by_email(request.email)
    if user is None or not db.verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    public = db.public_user(user)
    token = db.create_access_token(public["id"])
    return {"access_token": token, "token_type": "bearer", "user": public}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    return db.public_user(user)


@app.get("/api/sessions")
def list_sessions(user: dict = Depends(current_user)) -> list[dict]:
    return db.list_sessions(user["id"])


@app.post("/api/sessions")
def create_session(user: dict = Depends(current_user)) -> dict:
    return db.create_session(user["id"])


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, user: dict = Depends(current_user)) -> dict:
    return db.get_session(user["id"], session_id)


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user: dict = Depends(current_user)) -> None:
    db.delete_session(user["id"], session_id)


@app.post("/api/tutor/message", response_model=TutorMessageResponse)
def tutor_message(
    request: TutorMessageRequest,
    user: dict | None = Depends(optional_current_user),
) -> dict:
    if request.session_id:
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        session_record = db.get_session(user["id"], request.session_id)
        session_state = SessionState.model_validate(session_record)
        if session_state.title == "New Session":
            session_state = session_state.model_copy(
                update={"title": title_from_message(request.user_message)}
            )
        result = run_tutor_pipeline(
            user_message=request.user_message,
            session_state=session_state,
        )
        updated_state = SessionState.model_validate(result["updated_state"])
        saved_session = db.save_session_state(user["id"], request.session_id, updated_state)
        result["session"] = saved_session
        return result

    if request.session_state is None:
        raise HTTPException(status_code=400, detail="session_state or session_id is required.")

    return run_tutor_pipeline(
        user_message=request.user_message,
        session_state=request.session_state,
    )
