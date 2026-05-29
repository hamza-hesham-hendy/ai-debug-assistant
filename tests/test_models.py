"""
Tests for SQLModel ORM models: User and ReviewSession.
Uses an isolated in-memory SQLite DB via the shared engine fixture.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from models import ReviewSession, User
from utils import password_context


class TestUserModel:
    """Tests for the User model."""

    def test_user_creation(self, engine):
        """A User can be created and persisted with correct field values."""
        with Session(engine) as db:
            user = User(
                username="alice",
                email="alice@example.com",
                hashed_password=password_context.hash("secret"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            assert user.id is not None
            assert user.username == "alice"
            assert user.email == "alice@example.com"
            assert user.hashed_password != "secret"  # must be hashed

    def test_user_id_is_auto_incremented(self, engine):
        """Multiple users get distinct auto-incremented IDs."""
        with Session(engine) as db:
            u1 = User(username="bob1", email="bob1@example.com", hashed_password="h1")
            u2 = User(username="bob2", email="bob2@example.com", hashed_password="h2")
            db.add(u1)
            db.add(u2)
            db.commit()
            db.refresh(u1)
            db.refresh(u2)
            assert u1.id != u2.id

    def test_user_unique_username_constraint(self, engine):
        """Inserting two users with the same username raises IntegrityError."""
        with Session(engine) as db:
            db.add(User(username="dupname", email="a@x.com", hashed_password="h"))
            db.commit()

        with pytest.raises(IntegrityError):
            with Session(engine) as db:
                db.add(User(username="dupname", email="b@x.com", hashed_password="h"))
                db.commit()

    def test_user_unique_email_constraint(self, engine):
        """Inserting two users with the same email raises IntegrityError."""
        with Session(engine) as db:
            db.add(User(username="u_em1", email="same@x.com", hashed_password="h"))
            db.commit()

        with pytest.raises(IntegrityError):
            with Session(engine) as db:
                db.add(User(username="u_em2", email="same@x.com", hashed_password="h"))
                db.commit()

    def test_user_sessions_relationship_default_empty(self, engine):
        """A freshly created user has an empty sessions list."""
        with Session(engine) as db:
            user = User(username="lonely", email="lonely@x.com", hashed_password="h")
            db.add(user)
            db.commit()
            db.refresh(user)
            assert user.sessions == []

    def test_user_query_by_username(self, engine):
        """Can query a user by username using select()."""
        with Session(engine) as db:
            db.add(User(username="findme", email="findme@x.com", hashed_password="h"))
            db.commit()

        with Session(engine) as db:
            found = db.exec(select(User).where(User.username == "findme")).first()
        assert found is not None
        assert found.email == "findme@x.com"


class TestReviewSessionModel:
    """Tests for the ReviewSession model."""

    def _make_user(self, engine, username: str) -> int:
        """Helper: insert a User and return their id."""
        with Session(engine) as db:
            user = User(username=username, email=f"{username}@x.com", hashed_password="h")
            db.add(user)
            db.commit()
            db.refresh(user)
            return user.id

    def test_default_ai_status_is_pending(self, engine):
        """New ReviewSession defaults to ai_status='PENDING'."""
        user_id = self._make_user(engine, "default_status_user")
        with Session(engine) as db:
            sess = ReviewSession(
                user_id=user_id,
                language="Python",
                issue_description="Something",
            )
            db.add(sess)
            db.commit()
            db.refresh(sess)
            assert sess.ai_status == "PENDING"

    def test_optional_fields_default_to_none(self, engine):
        """AI fields default to None until populated."""
        user_id = self._make_user(engine, "none_fields_user")
        with Session(engine) as db:
            sess = ReviewSession(
                user_id=user_id,
                language="Go",
                issue_description="Nil pointer",
            )
            db.add(sess)
            db.commit()
            db.refresh(sess)

        assert sess.ai_category is None
        assert sess.ai_difficulty is None
        assert sess.ai_explanation is None
        assert sess.ai_fix is None
        assert sess.error_message is None

    def test_all_fields_persist(self, engine):
        """All AI fields can be written and read back correctly."""
        user_id = self._make_user(engine, "allfields_user")
        with Session(engine) as db:
            sess = ReviewSession(
                user_id=user_id,
                language="JavaScript",
                issue_description="Async bug",
                ai_category="Concurrency Issue",
                ai_difficulty="Advanced",
                ai_explanation="Race condition in promise chain",
                ai_fix="Use async/await properly",
                ai_status="SUCCESS",
            )
            db.add(sess)
            db.commit()
            sess_id = sess.id

        with Session(engine) as db:
            loaded = db.get(ReviewSession, sess_id)
        assert loaded.ai_category == "Concurrency Issue"
        assert loaded.ai_difficulty == "Advanced"
        assert loaded.ai_status == "SUCCESS"

    def test_failed_status_with_error_message(self, engine):
        """FAILED status and error_message persist correctly."""
        user_id = self._make_user(engine, "failed_user")
        with Session(engine) as db:
            sess = ReviewSession(
                user_id=user_id,
                language="Rust",
                issue_description="Borrow error",
                ai_status="FAILED",
                error_message="API timeout after 30s",
            )
            db.add(sess)
            db.commit()
            sess_id = sess.id

        with Session(engine) as db:
            loaded = db.get(ReviewSession, sess_id)
        assert loaded.ai_status == "FAILED"
        assert loaded.error_message == "API timeout after 30s"

    def test_relationship_back_populates(self, engine):
        """ReviewSession.user back-populates to the correct User."""
        user_id = self._make_user(engine, "rel_user")
        with Session(engine) as db:
            sess = ReviewSession(
                user_id=user_id,
                language="Python",
                issue_description="rel test",
                ai_status="PENDING",
            )
            db.add(sess)
            db.commit()
            sess_id = sess.id

        with Session(engine) as db:
            loaded = db.get(ReviewSession, sess_id)
            assert loaded.user is not None
            assert loaded.user.id == user_id

    def test_multiple_sessions_per_user(self, engine):
        """A single user can have multiple ReviewSessions."""
        user_id = self._make_user(engine, "multi_session_user")
        with Session(engine) as db:
            for i in range(3):
                db.add(
                    ReviewSession(
                        user_id=user_id,
                        language="Python",
                        issue_description=f"Issue {i}",
                    )
                )
            db.commit()

        with Session(engine) as db:
            sessions = db.exec(select(ReviewSession).where(ReviewSession.user_id == user_id)).all()
        assert len(sessions) == 3

    def test_session_id_is_auto_incremented(self, engine):
        """Each ReviewSession gets a unique auto-incremented ID."""
        user_id = self._make_user(engine, "autoinc_user")
        with Session(engine) as db:
            s1 = ReviewSession(user_id=user_id, language="Python", issue_description="A")
            s2 = ReviewSession(user_id=user_id, language="Go", issue_description="B")
            db.add(s1)
            db.add(s2)
            db.commit()
            db.refresh(s1)
            db.refresh(s2)
        assert s1.id != s2.id
