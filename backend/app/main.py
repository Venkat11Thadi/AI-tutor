"""FastAPI application entry point for the Zephyr Assist tutor API."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .email_utils import generate_otp, send_otp_email
from .models import AuthRequest, AuthResponse, OtpSendRequest, RegisterRequest, SessionState, TutorMessageRequest, TutorMessageResponse
from .tutor_graph import run_tutor_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler that initializes the database on startup."""
    del app
    db.init_db()
    yield


app = FastAPI(title="Zephyr Assist Tutor API", lifespan=lifespan)
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
    allow_headers=["Authorization", "Content-Type", "X-Groq-Api-Key"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight health-check endpoint."""
    return {"status": "ok"}


def title_from_message(message: str) -> str:
    """Truncate a user message to create a short session title.

    Collapses whitespace, then caps at 34 characters with an ellipsis.

    Args:
        message: The raw user message.

    Returns:
        A title string, or ``"New Session"`` if the message is blank.
    """
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New Session"
    return f"{cleaned[:34]}..." if len(cleaned) > 34 else cleaned


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    """FastAPI dependency that extracts and validates the authenticated user.

    Decodes the JWT from the ``Authorization`` header and fetches the
    corresponding user record.

    Args:
        credentials: Bearer token extracted by FastAPI's ``HTTPBearer``.

    Returns:
        A dict representing the user row.

    Raises:
        HTTPException: 401 if credentials are missing or the user is
            not found.
    """
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
    """FastAPI dependency allowing anonymous access.

    Returns the authenticated user dict when a valid token is present,
    or ``None`` when no token is supplied.

    Args:
        credentials: Optional bearer token.

    Returns:
        A user dict, or ``None`` for anonymous requests.

    Raises:
        HTTPException: 401 if a token is provided but the user is not
            found.
    """
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


@app.post("/api/auth/otp/send")
def send_otp(request: OtpSendRequest) -> dict:
    """Dispatch an OTP verification code to the given email.

    Rejects the request if an account with the email already exists.

    Args:
        request: Contains the target email address.

    Returns:
        A success message confirming the code was sent.

    Raises:
        HTTPException: 409 if the email is already registered.
    """
    email = request.email
    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="account exists with this email")
    
    otp = generate_otp()
    db.save_otp(email, otp)
    send_otp_email(email, otp)
    return {"success": True, "detail": "Verification code sent to your email."}


@app.post("/api/auth/register", response_model=AuthResponse)
def register(request: RegisterRequest) -> dict:
    """Create a new user account with optional OTP verification.

    If an OTP is provided, it is verified before account creation.

    Args:
        request: Registration payload (email, password, optional OTP).

    Returns:
        A JWT access token and user profile.

    Raises:
        HTTPException: 400 if the OTP is invalid or expired.
    """
    if request.otp is not None and not db.verify_otp(request.email, request.otp):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")
    user = db.create_user(request.email, request.password)
    token = db.create_access_token(user["id"])
    return {"access_token": token, "token_type": "bearer", "user": user}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: AuthRequest) -> dict:
    """Authenticate a user with email and password, returning a JWT.

    Args:
        request: Login credentials.

    Returns:
        A JWT access token and public user profile.

    Raises:
        HTTPException: 401 on invalid credentials.
    """
    user = db.get_user_by_email(request.email)
    if user is None or not db.verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    public = db.public_user(user)
    token = db.create_access_token(public["id"])
    return {"access_token": token, "token_type": "bearer", "user": public}


@app.get("/api/auth/me")
def me(user: dict = Depends(current_user)) -> dict:
    """Return the current authenticated user's public profile."""
    return db.public_user(user)


@app.get("/api/sessions")
def list_sessions(user: dict = Depends(current_user)) -> list[dict]:
    """List all tutoring sessions for the authenticated user."""
    return db.list_sessions(user["id"])


@app.post("/api/sessions")
def create_session(user: dict = Depends(current_user)) -> dict:
    """Create a new empty tutoring session."""
    return db.create_session(user["id"])


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str, user: dict = Depends(current_user)) -> dict:
    """Retrieve a single tutoring session by ID."""
    return db.get_session(user["id"], session_id)


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, user: dict = Depends(current_user)) -> None:
    """Delete a tutoring session and all its messages."""
    db.delete_session(user["id"], session_id)


@app.post("/api/tutor/message", response_model=TutorMessageResponse)
def tutor_message(
    request: TutorMessageRequest,
    user: dict | None = Depends(optional_current_user),
    x_groq_api_key: str | None = Header(None, alias="X-Groq-Api-Key"),
) -> dict:
    """Main tutor pipeline endpoint.

    Accepts a student message, runs it through the LangGraph tutor
    pipeline, and returns the assistant response along with updated
    session state. Supports both persistent sessions (via
    ``session_id``) and stateless mode (via ``session_state``).

    Args:
        request: The tutor message request body.
        user: The authenticated user (optional for stateless mode).
        x_groq_api_key: Optional client-supplied Groq API key.

    Returns:
        The tutor response, evaluation, pedagogy, and updated state.

    Raises:
        HTTPException: 401 if session_id is used without auth; 400 if
            neither session_id nor session_state is provided.
    """
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
            groq_api_key=x_groq_api_key,
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
        groq_api_key=x_groq_api_key,
    )
