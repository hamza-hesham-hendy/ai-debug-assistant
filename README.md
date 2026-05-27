# AI Debug Assistant

A FastAPI web application that uses Google Gemini AI to analyze programming bugs and provide specific fixes.

## Features
- User registration and login with secure password hashing (argon2)
- Submit programming issues in any language
- AI-powered analysis: error category, difficulty level, explanation, and fix
- Background task processing with auto-refresh
- Session-based authentication

## Tech Stack
- **Backend:** FastAPI + SQLModel + SQLite
- **AI:** Google Gemini 2.5 Flash
- **Auth:** Passlib + Argon2
- **Frontend:** Jinja2 Templates + vanilla CSS

## Local Setup

1. Clone the repo
   ```bash
   git clone https://github.com/YOUR_USERNAME/ai-debug-assistant.git
   cd ai-debug-assistant
   ```

2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3. Add your Gemini API key in a `.env` file
   ```
   GEMINI_API_KEY=your_key_here
   ```

4. Run the server
   ```bash
   uvicorn main:app --reload
   ```

5. Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

## Demo

Live Demo: https://web-production-a1ba2.up.railway.app/