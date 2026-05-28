"""
Shared pytest fixtures for the ai-debug-assistant test suite.

Key design decisions:
- Uses an in-memory SQLite DB (StaticPool) shared across the session.
- The `registered_user` fixture inserts directly into the DB (not via HTTP)
  to avoid conflicts when the same username is registered across multiple tests
  running against the same in-memory DB.
- AI calls (analyze_issue) are patched at the utils module level so they
  never fire real Gemini API calls.
- The `client` fixture overrides get_session so all routes use the test DB.
"""

import itertools
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from unittest.mock import patch

import sys
import os

# Ensure project root is on the path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_session
from main import app
from models import User
from utils import password_context


# ─── Fake AI response ─────────────────────────────────────────────────────────

FAKE_AI_RESULT = {
    "ai_category": "Syntax Error",
    "ai_difficulty": "Beginner",
    "ai_explanation": "Missing colon after function definition.",
    "ai_fix": "def foo():\n    pass\n\n# Fix: Added the missing colon.",
}


# ─── Counter for unique usernames ─────────────────────────────────────────────
# Avoids IntegrityError when multiple fixtures try to register "testuser"
# against the same session-scoped in-memory DB.

_user_counter = itertools.count(1)


def _next_user():
    n = next(_user_counter)
    return {
        "username": f"testuser{n}",
        "email": f"testuser{n}@example.com",
        "password": "SecurePass123",
    }


# ─── In-memory DB engine ──────────────────────────────────────────────────────

@pytest.fixture(name="engine", scope="session")
def engine_fixture():
    """Create a fresh in-memory SQLite engine for the whole test session."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    yield test_engine
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture(name="db")
def db_fixture(engine):
    """Provide a DB session for the in-memory engine."""
    with Session(engine) as session:
        yield session


# ─── FastAPI TestClient ───────────────────────────────────────────────────────

@pytest.fixture(name="client")
def client_fixture(engine):
    """
    TestClient whose DB dependency is overridden to use the in-memory engine.
    Also patches analyze_issue so no real API calls fire.
    """
    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with patch("utils.analyze_issue", return_value=FAKE_AI_RESULT):
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

    app.dependency_overrides.clear()


# ─── Pre-created user fixtures ────────────────────────────────────────────────

@pytest.fixture(name="registered_user")
def registered_user_fixture(engine):
    """
    Insert a unique user directly into the DB and return their credentials.
    Using direct DB insertion avoids HTTP 409 conflicts when the same test DB
    already has a 'testuser' from a prior test in the same session.
    """
    creds = _next_user()
    with Session(engine) as db:
        hashed = password_context.hash(creds["password"])
        user = User(
            username=creds["username"],
            email=creds["email"],
            hashed_password=hashed,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    creds["user_id"] = user.id
    return creds


@pytest.fixture(name="logged_in_client")
def logged_in_client_fixture(client, registered_user):
    """Return a TestClient that already has a valid session_id cookie."""
    response = client.post(
        "/login",
        data={
            "username": registered_user["username"],
            "password": registered_user["password"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, (
        f"Login failed with {response.status_code}: {response.text[:200]}"
    )
    assert "session_id" in client.cookies
    return client


# ─── Mock AI fixture (explicit, for tests that need fine-grained control) ─────

@pytest.fixture(name="mock_ai")
def mock_ai_fixture():
    """Patch analyze_issue and return the mock so tests can configure it."""
    with patch("utils.analyze_issue", return_value=FAKE_AI_RESULT) as mock:
        yield mock
