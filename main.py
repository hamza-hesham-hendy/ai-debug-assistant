from contextlib import asynccontextmanager

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    Form,
    Request,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from database import create_db_and_tables, get_session
from models import ReviewSession, User
from schemas import LoginFormData, RegisterFormData
from utils import get_current_user, password_context, run_ai_analysis


# Modern lifespan replaces the deprecated @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()  # runs on startup
    yield
    # shutdown cleanup can go here if needed


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ─── Dashboard ────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    # Guard: unauthenticated users get redirected to login
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Fetch only this user's sessions, newest first
    statement = select(ReviewSession).where(ReviewSession.user_id == user.id)
    sessions = db.exec(statement).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user, "sessions": sessions},
    )


# ─── Submit Issue ─────────────────────────────────────────────────────────────


@app.post("/submit")
def handle_submit(
    background_tasks: BackgroundTasks,
    language: str = Form(),
    issue_description: str = Form(),
    db: Session = Depends(get_session),
    user: User | None = Depends(get_current_user),
):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Save the new session row immediately with PENDING status
    new_session = ReviewSession(
        user_id=user.id,
        language=language,
        issue_description=issue_description,
        ai_status="PENDING",
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    # Run AI analysis in the background (non-blocking)
    background_tasks.add_task(
        run_ai_analysis,
        session_id=new_session.id,
        language=new_session.language,
        issue_description=new_session.issue_description,
    )

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)


# ─── Register ─────────────────────────────────────────────────────────────────


@app.get("/register", response_class=HTMLResponse)
def register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")


@app.post("/register")
def handle_register(
    request: Request,
    data: RegisterFormData = Form(),
    db: Session = Depends(get_session),
):
    hashed = password_context.hash(data.password)
    new_user = User(username=data.username, email=data.email, hashed_password=hashed)
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Username or email is already registered."},
            status_code=status.HTTP_409_CONFLICT,
        )
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# ─── Login ────────────────────────────────────────────────────────────────────


@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/login")
def handle_login(
    request: Request,
    data: LoginFormData = Form(),
    db: Session = Depends(get_session),
):
    statement = select(User).where(User.username == data.username)
    user = db.exec(statement).first()

    if not user or not password_context.verify(data.password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_id", value=str(user.id))
    return response


# ─── Logout ───────────────────────────────────────────────────────────────────


@app.get("/logout")
def handle_logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="session_id")
    return response
