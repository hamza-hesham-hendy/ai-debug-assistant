from sqlmodel import Field, Relationship, SQLModel

# ORM => SQLModel
# Class  => Table
# Properties => Columns
# Object => Record / Row


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True, index=True)
    username: str = Field(unique=True, nullable=False, index=True, max_length=20)
    email: str = Field(unique=True, nullable=False, index=True, max_length=50)
    hashed_password: str = Field(max_length=255, nullable=False)

    # Relationship: User(1) => ReviewSession(M)
    sessions: list["ReviewSession"] = Relationship(back_populates="user")


class ReviewSession(SQLModel, table=True):
    __tablename__ = "review_sessions"
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    language: str = Field(nullable=False)
    issue_description: str = Field(nullable=False)
    ai_category: str | None = Field(default=None)
    ai_difficulty: str | None = Field(default=None)
    ai_explanation: str | None = Field(default=None)  # what is wrong and why
    ai_fix: str | None = Field(default=None)  # the actual fix / corrected code
    ai_status: str = Field(default="PENDING")  # SUCCESS / FAILED / PENDING
    error_message: str | None = Field(default=None)

    user: User | None = Relationship(back_populates="sessions")
