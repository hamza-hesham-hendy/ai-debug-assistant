"""
Tests for ai_service.analyze_issue().

The Gemini client is always mocked so:
  - No real API calls are made in CI.
  - Tests are deterministic and fast.
  - We test that the function correctly forwards inputs and parses outputs.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from ai_service import analyze_issue

SAMPLE_RESULT = {
    "ai_category": "Syntax Error",
    "ai_difficulty": "Beginner",
    "ai_explanation": "Missing colon after function definition.",
    "ai_fix": "def foo():\n    pass\n\n# Fix: Added colon.",
}


def make_mock_client(result_dict: dict) -> MagicMock:
    """Build a mock genai.Client that returns result_dict as JSON."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(result_dict)

    mock_models = MagicMock()
    mock_models.generate_content.return_value = mock_response

    mock_client = MagicMock()
    mock_client.models = mock_models
    return mock_client


class TestAnalyzeIssue:
    """Tests for analyze_issue(language, issue_description)."""

    def test_returns_dict(self):
        """analyze_issue returns a dict."""
        with patch("ai_service.client", make_mock_client(SAMPLE_RESULT)):
            result = analyze_issue("Python", "Missing colon")
        assert isinstance(result, dict)

    def test_returns_all_required_keys(self):
        """Result contains all four expected keys."""
        with patch("ai_service.client", make_mock_client(SAMPLE_RESULT)):
            result = analyze_issue("Python", "Some error")
        assert "ai_category" in result
        assert "ai_difficulty" in result
        assert "ai_explanation" in result
        assert "ai_fix" in result

    def test_values_are_strings(self):
        """All returned values are strings."""
        with patch("ai_service.client", make_mock_client(SAMPLE_RESULT)):
            result = analyze_issue("Python", "Some error")
        for key in ("ai_category", "ai_difficulty", "ai_explanation", "ai_fix"):
            assert isinstance(result[key], str), f"{key} should be a string"

    def test_python_language_input(self):
        """Works correctly with Python as the language."""
        with patch("ai_service.client", make_mock_client(SAMPLE_RESULT)):
            result = analyze_issue("Python", "IndexError: list index out of range")
        assert result["ai_category"] == "Syntax Error"

    def test_javascript_language_input(self):
        """Works correctly with JavaScript as the language."""
        js_result = {**SAMPLE_RESULT, "ai_category": "Type Error"}
        with patch("ai_service.client", make_mock_client(js_result)):
            result = analyze_issue("JavaScript", "undefined is not a function")
        assert result["ai_category"] == "Type Error"

    def test_go_language_input(self):
        """Works correctly with Go as the language."""
        go_result = {**SAMPLE_RESULT, "ai_difficulty": "Advanced"}
        with patch("ai_service.client", make_mock_client(go_result)):
            result = analyze_issue("Go", "nil pointer dereference")
        assert result["ai_difficulty"] == "Advanced"

    def test_difficulty_is_valid_value(self):
        """ai_difficulty is one of the three allowed values."""
        for difficulty in ("Beginner", "Intermediate", "Advanced"):
            mocked = {**SAMPLE_RESULT, "ai_difficulty": difficulty}
            with patch("ai_service.client", make_mock_client(mocked)):
                result = analyze_issue("Python", "Some error")
            assert result["ai_difficulty"] == difficulty

    def test_prompt_contains_language(self):
        """The prompt sent to Gemini contains the provided language."""
        mock_client = make_mock_client(SAMPLE_RESULT)
        with patch("ai_service.client", mock_client):
            analyze_issue("Rust", "borrow checker error")
        call_args = mock_client.models.generate_content.call_args
        # The prompt (contents kwarg or positional arg) should include "Rust"
        prompt_text = str(call_args)
        assert "Rust" in prompt_text

    def test_prompt_contains_description(self):
        """The prompt sent to Gemini contains the issue description."""
        mock_client = make_mock_client(SAMPLE_RESULT)
        with patch("ai_service.client", mock_client):
            analyze_issue("Python", "unique_error_string_xyz")
        call_args = mock_client.models.generate_content.call_args
        prompt_text = str(call_args)
        assert "unique_error_string_xyz" in prompt_text

    def test_api_error_propagates(self):
        """If the Gemini client raises, analyze_issue lets the exception propagate."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = ConnectionError("API down")
        with patch("ai_service.client", mock_client):
            with pytest.raises(ConnectionError, match="API down"):
                analyze_issue("Python", "some error")

    def test_malformed_json_raises(self):
        """If API returns non-JSON, json.loads raises ValueError."""
        mock_response = MagicMock()
        mock_response.text = "not valid json {{{"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        with patch("ai_service.client", mock_client):
            with pytest.raises((ValueError, Exception)):
                analyze_issue("Python", "some issue")

    def test_empty_issue_description(self):
        """Empty issue description is passed through (no crash)."""
        with patch("ai_service.client", make_mock_client(SAMPLE_RESULT)):
            result = analyze_issue("Python", "")
        assert "ai_category" in result

    def test_very_long_description(self):
        """Very long issue description is handled gracefully."""
        long_desc = "error " * 1000
        with patch("ai_service.client", make_mock_client(SAMPLE_RESULT)):
            result = analyze_issue("Python", long_desc)
        assert "ai_fix" in result
