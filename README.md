# AI Debug Assistant

A FastAPI web application that uses Google Gemini AI to analyze programming bugs and provide specific fixes.

![CI](https://github.com/hamza-hesham-hendy/ai-debug-assistant/actions/workflows/ci.yml/badge.svg)

## Features

- User registration and login with secure password hashing (Argon2)
- Submit programming issues in any language
- AI-powered analysis: error category, difficulty level, explanation, and fix
- Background task processing with auto-refresh
- Session-based authentication

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + SQLModel + SQLite |
| AI | Google Gemini 2.5 Flash |
| Auth | Passlib + Argon2 |
| Frontend | Jinja2 Templates + Vanilla CSS |
| Testing | pytest + pytest-cov |
| Linting | Ruff (linter + formatter) |
| CI/CD | GitHub Actions |

## Local Setup

### 1. Clone the repo
```bash
git clone https://github.com/hamza-hesham-hendy/ai-debug-assistant.git
cd ai-debug-assistant
```

### 2. Create and activate a virtual environment
```bash
uv venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies
```bash
uv pip install -r requirements.txt
```

### 4. Add your Gemini API key
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_key_here
```

### 5. Run the server
```bash
uvicorn main:app --reload
```

### 6. Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Running Tests

Install test dependencies (if not already installed):
```bash
uv pip install pytest pytest-cov httpx
```

Run the full test suite with coverage:
```bash
pytest tests/ -v
```

Run with coverage report:
```bash
pytest tests/ --cov=. --cov-report=term-missing
```

> **Coverage threshold:** Tests will fail if total coverage drops below **85%**.
> Current coverage: **100%** across all 6 source files.

### Test Structure

| File | What it tests |
|---|---|
| `tests/test_auth.py` | Register, login, logout — happy paths & edge cases |
| `tests/test_routes.py` | Dashboard, submit form, background AI task |
| `tests/test_utils.py` | `clean_ai_fix`, `get_current_user`, `run_ai_analysis` |
| `tests/test_ai_service.py` | `analyze_issue` with mocked Gemini client |
| `tests/test_models.py` | SQLModel constraints, defaults, relationships |
| `tests/test_database.py` | Table creation, column structure, session lifecycle |
| `tests/test_schemas.py` | Pydantic schema validation |

> All AI (Gemini) calls are **mocked** in tests — no API key is needed to run the test suite.

---

## Pre-commit Hooks

Install and enable pre-commit hooks (runs ruff linter + formatter before every commit):
```bash
pip install pre-commit
pre-commit install
```

Run hooks manually on all files:
```bash
pre-commit run --all-files
```

---

## CI/CD

Every push and pull request automatically triggers the GitHub Actions pipeline (`.github/workflows/ci.yml`), which:

1. **Test job** — runs `pytest` and enforces ≥85% coverage
2. **Lint job** — runs `ruff check` and `ruff format --check`

Both jobs must pass for a PR to be considered green.

---

## Demo

Live Demo: https://web-production-a1ba2.up.railway.app/