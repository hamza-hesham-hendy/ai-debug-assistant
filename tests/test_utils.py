"""
Tests for utility functions in utils.py:
  - clean_ai_fix: sanitizes AI-generated text
  - get_current_user: reads session cookie and returns User or None
  - run_ai_analysis: background task that calls AI and updates DB
"""

from unittest.mock import patch

from sqlmodel import Session

from models import ReviewSession
from utils import clean_ai_fix, run_ai_analysis

# ─── clean_ai_fix ─────────────────────────────────────────────────────────────


class TestCleanAiFix:
    """Tests for the clean_ai_fix() sanitizer."""

    def test_removes_python_code_fence(self):
        """```python fence is stripped."""
        text = "```python\ndef foo():\n    pass\n```"
        result = clean_ai_fix(text)
        assert "```" not in result
        assert "def foo():" in result

    def test_removes_plain_code_fence(self):
        """Plain ``` fence is stripped."""
        text = "```\nsome code\n```"
        result = clean_ai_fix(text)
        assert "```" not in result
        assert "some code" in result

    def test_removes_named_fences(self):
        """Named fences like ```javascript are stripped."""
        text = "```javascript\nconsole.log('hi');\n```"
        result = clean_ai_fix(text)
        assert "```" not in result

    def test_collapses_three_blank_lines_to_one(self):
        """3 consecutive newlines become exactly 2."""
        text = "line1\n\n\nline2"
        result = clean_ai_fix(text)
        assert "\n\n\n" not in result
        assert "line1" in result
        assert "line2" in result

    def test_collapses_many_blank_lines(self):
        """5 consecutive newlines are collapsed to 2."""
        text = "a\n\n\n\n\nb"
        result = clean_ai_fix(text)
        assert "\n\n\n" not in result

    def test_strips_leading_whitespace(self):
        """Leading whitespace/newlines are removed."""
        text = "\n\n   def foo():\n    pass"
        result = clean_ai_fix(text)
        assert not result.startswith("\n")
        assert not result.startswith(" ")

    def test_strips_trailing_whitespace(self):
        """Trailing whitespace is removed."""
        text = "def foo():\n    pass   \n\n"
        result = clean_ai_fix(text)
        assert not result.endswith(" ")
        assert not result.endswith("\n")

    def test_empty_string_returned_unchanged(self):
        """Empty string passes through."""
        assert clean_ai_fix("") == ""

    def test_none_returned_unchanged(self):
        """None passes through without error."""
        assert clean_ai_fix(None) is None

    def test_clean_text_unchanged(self):
        """Text that needs no cleaning is returned as-is (stripped)."""
        text = "def foo():\n    return 42\n\n# Fix: added return statement."
        result = clean_ai_fix(text)
        assert "def foo():" in result
        assert "# Fix:" in result

    def test_two_blank_lines_not_collapsed(self):
        """Exactly 2 newlines (1 blank line) are left alone."""
        text = "line1\n\nline2"
        result = clean_ai_fix(text)
        assert "\n\n" in result

    def test_only_whitespace_string(self):
        """String of only whitespace becomes empty after strip."""
        result = clean_ai_fix("   \n\n  ")
        assert result == ""

    def test_multiple_fences_all_removed(self):
        """Multiple code fences in the same string are all stripped."""
        text = "```python\nfoo\n```\n\n```\nbar\n```"
        result = clean_ai_fix(text)
        assert "```" not in result
        assert "foo" in result
        assert "bar" in result


# ─── get_current_user ─────────────────────────────────────────────────────────


class TestGetCurrentUser:
    """Tests for get_current_user() via simulated requests."""

    def test_unauthenticated_returns_none(self, client):
        """No session_id cookie → / redirects (user is None)."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303  # redirected because user is None

    def test_valid_cookie_returns_user(self, logged_in_client):
        """Valid session_id cookie → dashboard loads (user found)."""
        response = logged_in_client.get("/")
        assert response.status_code == 200

    def test_invalid_cookie_value_redirects(self, client):
        """Non-existent user ID in cookie → treated as unauthenticated."""
        client.cookies.set("session_id", "99999")
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303


# ─── run_ai_analysis ──────────────────────────────────────────────────────────


class TestRunAiAnalysis:
    """
    Tests for run_ai_analysis() background task.

    IMPORTANT: run_ai_analysis uses `Session(engine)` from database.engine
    directly (not via dependency injection), so we must patch `database.engine`
    to point at the test engine so DB writes land in the same in-memory DB
    that assertions read from.
    """

    def _create_pending_session(self, engine, user_id: int) -> int:
        """Helper: insert a PENDING ReviewSession and return its id."""
        with Session(engine) as db:
            sess = ReviewSession(
                user_id=user_id,
                language="Python",
                issue_description="Test issue",
                ai_status="PENDING",
            )
            db.add(sess)
            db.commit()
            db.refresh(sess)
            return sess.id

    def test_success_updates_all_fields(self, logged_in_client, engine):
        """Successful AI call populates all AI fields and sets SUCCESS."""
        user_id = int(logged_in_client.cookies["session_id"])
        session_id = self._create_pending_session(engine, user_id)

        fake_result = {
            "ai_category": "Logic Error",
            "ai_difficulty": "Advanced",
            "ai_explanation": "Off-by-one error",
            "ai_fix": "Fix the index",
        }
        # Patch both analyze_issue AND utils.engine so run_ai_analysis
        # reads/writes to the same in-memory DB as our test assertions.
        # utils.py does `from database import engine` so we must patch utils.engine,
        # not database.engine.
        with patch("utils.analyze_issue", return_value=fake_result), patch("utils.engine", engine):
            run_ai_analysis(session_id, "Python", "Off-by-one")

        with Session(engine) as db:
            sess = db.get(ReviewSession, session_id)

        assert sess.ai_status == "SUCCESS"
        assert sess.ai_category == "Logic Error"
        assert sess.ai_difficulty == "Advanced"
        assert sess.ai_explanation == "Off-by-one error"
        assert "Fix the index" in sess.ai_fix

    def test_ai_exception_marks_failed(self, logged_in_client, engine):
        """When analyze_issue raises, session gets FAILED + error_message."""
        user_id = int(logged_in_client.cookies["session_id"])
        session_id = self._create_pending_session(engine, user_id)

        # utils.py does `from database import engine` so patch utils.engine directly
        with (
            patch("utils.analyze_issue", side_effect=ValueError("Bad API response")),
            patch("utils.engine", engine),
        ):
            run_ai_analysis(session_id, "Python", "Bad input")

        with Session(engine) as db:
            sess = db.get(ReviewSession, session_id)

        assert sess.ai_status == "FAILED"
        assert "Bad API response" in sess.error_message

    def test_nonexistent_session_id_does_not_crash(self, engine):
        """Passing a non-existent session_id doesn't raise (graceful no-op)."""
        with (
            patch(
                "utils.analyze_issue",
                return_value={
                    "ai_category": "X",
                    "ai_difficulty": "Beginner",
                    "ai_explanation": "Y",
                    "ai_fix": "Z",
                },
            ),
            patch("utils.engine", engine),
        ):
            # Should not raise any exception
            run_ai_analysis(999999, "Python", "Doesn't matter")

    def test_ai_fix_is_cleaned_before_save(self, logged_in_client, engine):
        """clean_ai_fix is applied to ai_fix before saving."""
        user_id = int(logged_in_client.cookies["session_id"])
        session_id = self._create_pending_session(engine, user_id)

        raw_fix = "```python\ndef foo():\n    pass\n```"
        with (
            patch(
                "utils.analyze_issue",
                return_value={
                    "ai_category": "Syntax Error",
                    "ai_difficulty": "Beginner",
                    "ai_explanation": "Missing colon",
                    "ai_fix": raw_fix,
                },
            ),
            patch("utils.engine", engine),
        ):
            run_ai_analysis(session_id, "Python", "Missing colon")

        with Session(engine) as db:
            sess = db.get(ReviewSession, session_id)

        assert sess.ai_fix is not None
        assert "```" not in sess.ai_fix
