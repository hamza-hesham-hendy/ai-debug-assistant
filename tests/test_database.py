"""
Tests for database.py: engine creation, table setup, and session management.
"""

import pytest
from sqlmodel import Session, SQLModel, create_engine, select, text
from sqlmodel.pool import StaticPool

import database
from database import create_db_and_tables, get_session
from models import User, ReviewSession


class TestCreateDbAndTables:
    """Tests for create_db_and_tables()."""

    def test_creates_tables_without_error(self):
        """create_db_and_tables() completes without raising."""
        # We call it against the real module engine (SQLite file)
        # This is safe because CI uses a temp DB and the function is idempotent.
        # We override the engine to use in-memory so we don't touch the real file.
        original_engine = database.engine
        try:
            test_engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            database.engine = test_engine
            create_db_and_tables()  # should not raise
            # Verify tables were actually created
            with Session(test_engine) as db:
                # If tables exist, this won't raise
                db.exec(select(User)).all()
                db.exec(select(ReviewSession)).all()
        finally:
            database.engine = original_engine

    def test_create_db_idempotent(self):
        """Calling create_db_and_tables() twice doesn't raise (IF NOT EXISTS)."""
        original_engine = database.engine
        try:
            test_engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            database.engine = test_engine
            create_db_and_tables()
            create_db_and_tables()  # second call should be a no-op
        finally:
            database.engine = original_engine

    def test_users_table_has_correct_columns(self):
        """After setup, the users table has expected columns."""
        original_engine = database.engine
        try:
            test_engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            database.engine = test_engine
            create_db_and_tables()

            with test_engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(users)"))
                columns = {row[1] for row in result}

            assert "id" in columns
            assert "username" in columns
            assert "email" in columns
            assert "hashed_password" in columns
        finally:
            database.engine = original_engine

    def test_review_sessions_table_has_correct_columns(self):
        """After setup, the review_sessions table has expected columns."""
        original_engine = database.engine
        try:
            test_engine = create_engine(
                "sqlite://",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
            database.engine = test_engine
            create_db_and_tables()

            with test_engine.connect() as conn:
                result = conn.execute(text("PRAGMA table_info(review_sessions)"))
                columns = {row[1] for row in result}

            assert "id" in columns
            assert "user_id" in columns
            assert "language" in columns
            assert "issue_description" in columns
            assert "ai_status" in columns
            assert "ai_category" in columns
            assert "ai_difficulty" in columns
            assert "ai_explanation" in columns
            assert "ai_fix" in columns
            assert "error_message" in columns
        finally:
            database.engine = original_engine


class TestGetSession:
    """Tests for get_session() dependency generator."""

    def test_get_session_yields_a_session(self, engine):
        """get_session yields a live SQLModel Session object."""
        original_engine = database.engine
        try:
            database.engine = engine
            gen = get_session()
            session = next(gen)
            assert isinstance(session, Session)
            try:
                next(gen)
            except StopIteration:
                pass  # expected — generator exhausted after yield
        finally:
            database.engine = original_engine

    def test_session_can_perform_queries(self, engine):
        """Session from get_session can execute queries."""
        original_engine = database.engine
        try:
            database.engine = engine
            gen = get_session()
            session = next(gen)
            results = session.exec(select(User)).all()
            assert isinstance(results, list)
            try:
                next(gen)
            except StopIteration:
                pass
        finally:
            database.engine = original_engine
