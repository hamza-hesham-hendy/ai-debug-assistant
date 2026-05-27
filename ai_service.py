import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def analyze_issue(language: str, issue_description: str) -> dict:
    prompt = f"""
    You are an expert programming debugger and senior software engineer.

    A developer is facing the following issue:
    Programming Language: {language}
    Problem Description: {issue_description}

    Provide a thorough, specific analysis with these four fields:

    1. ai_category: The specific error/issue category
       (e.g., "Syntax Error", "Logic Error", "Runtime Error", "Type Error",
        "Memory Error", "Import Error", "Concurrency Issue", "Performance Issue", etc.)

    2. ai_difficulty: Difficulty level — exactly one of: "Beginner", "Intermediate", or "Advanced"

    3. ai_explanation: A clear, direct explanation of what is wrong and WHY it is wrong.
       Be specific to the code or situation described — do NOT give generic advice.
       If the user shared actual code, pinpoint the exact line or character causing the problem.

    4. ai_fix: A concrete, working fix or solution.
       STRICT FORMATTING RULES for ai_fix:
       - Write the corrected code first, with each statement on its own line using \\n for newlines.
       - Do NOT use markdown code fences (no triple backticks).
       - Do NOT add blank lines between every single line of code — only use a blank line to separate logical sections.
       - After the code, add a blank line, then one sentence starting with "# Fix:" explaining what changed and why.
       - No excessive spacing or padding anywhere.

    Example of correct ai_fix format:
    def add(a, b):\\n    return a + b\\n\\n# Fix: Added the missing colon after the function signature.

    Be precise and specific. Treat the developer as capable — no hand-holding, just real help.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "ai_category":    types.Schema(type=types.Type.STRING),
                    "ai_difficulty":  types.Schema(type=types.Type.STRING),
                    "ai_explanation": types.Schema(type=types.Type.STRING),
                    "ai_fix":         types.Schema(type=types.Type.STRING),
                },
                required=["ai_category", "ai_difficulty", "ai_explanation", "ai_fix"],
            ),
        ),
    )

    return json.loads(response.text)
