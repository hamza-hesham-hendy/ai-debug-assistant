import re

from fastapi import Depends, Request
from passlib.context import CryptContext
from sqlmodel import Session, select

from ai_service import analyze_issue
from database import engine, get_session
from models import ReviewSession, User

# Password hashing using argon2
password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def clean_ai_fix(text: str) -> str:
    """
    Sanitize the AI-generated fix before saving to DB:
    1. Strip markdown code fences (```python, ```, etc.)
    2. Collapse 3+ consecutive blank lines down to 1
    3. Strip leading/trailing whitespace
    """
    if not text:
        return text

    # Remove markdown code fences like ```python or ``` 
    text = re.sub(r"```[\w]*\n?", "", text)

    # Collapse 3 or more consecutive newlines into exactly 2 (one blank line)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def get_current_user(request: Request, db: Session = Depends(get_session)):
    """Read session cookie → return User object or None."""
    user_id = request.cookies.get("session_id")
    if not user_id:
        return None
    statement = select(User).where(User.id == int(user_id))
    return db.exec(statement).first()


def run_ai_analysis(session_id: int, language: str, issue_description: str):
    """
    Background task: call Gemini AI and update the ReviewSession row.
    Wrapped in try/except so a failed AI call never crashes the server.
    """
    try:
        ai_result = analyze_issue(language, issue_description)

        with Session(engine) as db:
            review = db.get(ReviewSession, session_id)
            if review:
                review.ai_category    = ai_result["ai_category"]
                review.ai_difficulty  = ai_result["ai_difficulty"]
                review.ai_explanation = ai_result["ai_explanation"]
                review.ai_fix         = clean_ai_fix(ai_result["ai_fix"])
                review.ai_status      = "SUCCESS"
                db.add(review)
                db.commit()

    except Exception as e:
        with Session(engine) as db:
            review = db.get(ReviewSession, session_id)
            if review:
                review.ai_status     = "FAILED"
                review.error_message = str(e)
                db.add(review)
                db.commit()
