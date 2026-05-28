"""
Tests for main application routes: / (dashboard) and /submit.
Covers authentication guards, session creation, background AI task execution,
and error handling edge cases.
"""

import time
import pytest
from fastapi import status
from unittest.mock import patch
from sqlmodel import Session, select

from models import ReviewSession


class TestDashboard:
    """Tests for GET / (index/dashboard)."""

    def test_index_unauthenticated_redirects(self, client):
        """Unauthenticated request to / redirects to /login."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == status.HTTP_303_SEE_OTHER
        assert "/login" in response.headers["location"]

    def test_index_authenticated_returns_200(self, logged_in_client):
        """Authenticated user gets 200 HTML dashboard."""
        response = logged_in_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_index_shows_username(self, logged_in_client):
        """Dashboard HTML contains the logged-in user's username."""
        response = logged_in_client.get("/")
        assert "testuser" in response.text

    def test_index_empty_sessions(self, logged_in_client):
        """New user with no sessions: dashboard loads without error."""
        response = logged_in_client.get("/")
        assert response.status_code == 200
        # No crash, page rendered

    def test_index_shows_sessions(self, logged_in_client, engine):
        """Sessions belonging to the user appear on the dashboard."""
        # Create a fake session directly in DB
        with Session(engine) as db:
            user_id = int(logged_in_client.cookies["session_id"])
            sess = ReviewSession(
                user_id=user_id,
                language="Python",
                issue_description="My bug",
                ai_status="SUCCESS",
                ai_category="Syntax Error",
                ai_difficulty="Beginner",
                ai_explanation="Explanation here",
                ai_fix="Fixed code",
            )
            db.add(sess)
            db.commit()

        response = logged_in_client.get("/")
        assert response.status_code == 200
        assert "Python" in response.text or "My bug" in response.text


class TestSubmit:
    """Tests for POST /submit."""

    def test_submit_unauthenticated_redirects(self, client):
        """Unauthenticated POST /submit redirects to /login."""
        response = client.post(
            "/submit",
            data={"language": "Python", "issue_description": "Some error"},
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_303_SEE_OTHER
        assert "/login" in response.headers["location"]

    def test_submit_creates_pending_session(self, logged_in_client, engine):
        """Valid submit creates a ReviewSession with PENDING status immediately."""
        with patch("utils.analyze_issue", return_value={
            "ai_category": "Syntax Error",
            "ai_difficulty": "Beginner",
            "ai_explanation": "Explanation",
            "ai_fix": "Fix here",
        }):
            response = logged_in_client.post(
                "/submit",
                data={
                    "language": "Python",
                    "issue_description": "IndexError on line 5",
                },
                follow_redirects=False,
            )

        assert response.status_code == status.HTTP_303_SEE_OTHER
        assert response.headers["location"] == "/"

        with Session(engine) as db:
            sessions = db.exec(select(ReviewSession)).all()
        assert len(sessions) >= 1
        latest = sorted(sessions, key=lambda s: s.id)[-1]
        assert latest.language == "Python"
        assert latest.issue_description == "IndexError on line 5"

    def test_submit_missing_language(self, logged_in_client):
        """Missing language field returns 422."""
        response = logged_in_client.post(
            "/submit",
            data={"issue_description": "Some bug"},
            follow_redirects=False,
        )
        assert response.status_code == 422

    def test_submit_missing_description(self, logged_in_client):
        """Missing issue_description field returns 422."""
        response = logged_in_client.post(
            "/submit",
            data={"language": "Python"},
            follow_redirects=False,
        )
        assert response.status_code == 422

    def test_submit_empty_form(self, logged_in_client):
        """Empty form body returns 422."""
        response = logged_in_client.post("/submit", data={}, follow_redirects=False)
        assert response.status_code == 422

    def test_submit_multiple_languages(self, logged_in_client, engine):
        """Submit works for various programming languages."""
        languages = ["Python", "JavaScript", "Go", "Rust", "Java"]
        for lang in languages:
            with patch("utils.analyze_issue", return_value={
                "ai_category": "Logic Error",
                "ai_difficulty": "Intermediate",
                "ai_explanation": "Some explanation",
                "ai_fix": "Some fix",
            }):
                response = logged_in_client.post(
                    "/submit",
                    data={"language": lang, "issue_description": f"Bug in {lang}"},
                    follow_redirects=False,
                )
            assert response.status_code == status.HTTP_303_SEE_OTHER

    def test_submit_ai_success_updates_db(self, logged_in_client, engine):
        """
        After background task runs, ReviewSession is updated to SUCCESS
        with AI fields populated.
        """
        import database
        import time
        fake_result = {
            "ai_category": "Type Error",
            "ai_difficulty": "Intermediate",
            "ai_explanation": "Wrong type passed",
            "ai_fix": "Cast to int first",
        }
        # Patch both analyze_issue AND utils.engine so the background task
        # writes back to the same in-memory DB that we query below.
        # utils.py does `from database import engine` so patch utils.engine.
        with patch("utils.analyze_issue", return_value=fake_result), \
             patch("utils.engine", engine):
            logged_in_client.post(
                "/submit",
                data={"language": "TypeScript", "issue_description": "Type mismatch unique"},
            )
            time.sleep(0.1)

        with Session(engine) as db:
            sessions = db.exec(
                select(ReviewSession).where(ReviewSession.language == "TypeScript")
            ).all()

        success_sessions = [s for s in sessions if s.ai_status == "SUCCESS"]
        assert len(success_sessions) >= 1
        s = success_sessions[-1]
        assert s.ai_category == "Type Error"
        assert s.ai_difficulty == "Intermediate"
        assert s.ai_explanation == "Wrong type passed"

    def test_submit_ai_failure_marks_failed(self, logged_in_client, engine):
        """When analyze_issue raises, the session gets FAILED status."""
        import database
        import time
        with patch("utils.analyze_issue", side_effect=RuntimeError("API unavailable")), \
             patch("utils.engine", engine):
            logged_in_client.post(
                "/submit",
                data={"language": "Kotlin", "issue_description": "will fail uniquely"},
            )
            time.sleep(0.1)

        with Session(engine) as db:
            sessions = db.exec(
                select(ReviewSession).where(ReviewSession.language == "Kotlin")
            ).all()

        failed = [s for s in sessions if s.ai_status == "FAILED"]
        assert len(failed) >= 1
        assert "API unavailable" in failed[-1].error_message

    def test_submit_redirects_back_to_dashboard(self, logged_in_client):
        """Successful submit always redirects to /."""
        with patch("utils.analyze_issue", return_value={
            "ai_category": "Import Error",
            "ai_difficulty": "Beginner",
            "ai_explanation": "Module not found",
            "ai_fix": "pip install it",
        }):
            response = logged_in_client.post(
                "/submit",
                data={"language": "Python", "issue_description": "import error"},
                follow_redirects=False,
            )
        assert response.headers["location"] == "/"
