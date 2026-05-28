"""
Tests for Pydantic schemas in schemas.py:
  - RegisterFormData
  - LoginFormData

Validates required fields, correct types, and ValidationError on missing data.
"""

import pytest
from pydantic import ValidationError

from schemas import LoginFormData, RegisterFormData


class TestRegisterFormData:
    """Tests for RegisterFormData schema."""

    def test_valid_data_creates_instance(self):
        """All required fields present → instance created successfully."""
        data = RegisterFormData(
            username="alice",
            email="alice@example.com",
            password="securepass",
        )
        assert data.username == "alice"
        assert data.email == "alice@example.com"
        assert data.password == "securepass"

    def test_missing_username_raises(self):
        """Missing username → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterFormData(email="a@b.com", password="pass")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "username" in fields

    def test_missing_email_raises(self):
        """Missing email → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterFormData(username="bob", password="pass")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "email" in fields

    def test_missing_password_raises(self):
        """Missing password → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterFormData(username="bob", email="b@c.com")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "password" in fields

    def test_all_fields_missing_raises(self):
        """No fields → ValidationError with 3 errors."""
        with pytest.raises(ValidationError) as exc_info:
            RegisterFormData()
        assert len(exc_info.value.errors()) == 3

    def test_fields_are_strings(self):
        """Field values are stored as plain strings."""
        data = RegisterFormData(username="u", email="u@e.com", password="p")
        assert isinstance(data.username, str)
        assert isinstance(data.email, str)
        assert isinstance(data.password, str)

    def test_empty_string_is_accepted(self):
        """
        Pydantic v2 accepts empty strings for str fields by default
        (business-level validation lives in the route, not the schema).
        """
        data = RegisterFormData(username="", email="", password="")
        assert data.username == ""

    def test_long_values_accepted(self):
        """Very long strings are accepted at schema level."""
        long_str = "a" * 500
        data = RegisterFormData(username=long_str, email=long_str, password=long_str)
        assert len(data.username) == 500

    def test_whitespace_username_accepted(self):
        """Whitespace-only username is accepted at schema level."""
        data = RegisterFormData(username="   ", email="x@y.com", password="pass")
        assert data.username == "   "


class TestLoginFormData:
    """Tests for LoginFormData schema."""

    def test_valid_data_creates_instance(self):
        """Both fields present → instance created successfully."""
        data = LoginFormData(username="charlie", password="mypassword")
        assert data.username == "charlie"
        assert data.password == "mypassword"

    def test_missing_username_raises(self):
        """Missing username → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LoginFormData(password="pass")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "username" in fields

    def test_missing_password_raises(self):
        """Missing password → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            LoginFormData(username="charlie")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "password" in fields

    def test_all_fields_missing_raises(self):
        """No fields → ValidationError with 2 errors."""
        with pytest.raises(ValidationError) as exc_info:
            LoginFormData()
        assert len(exc_info.value.errors()) == 2

    def test_fields_are_strings(self):
        """Field values are stored as strings."""
        data = LoginFormData(username="u", password="p")
        assert isinstance(data.username, str)
        assert isinstance(data.password, str)

    def test_only_two_fields(self):
        """LoginFormData only has username and password, no email."""
        data = LoginFormData(username="u", password="p")
        assert not hasattr(data, "email")

    def test_empty_strings_accepted(self):
        """Empty string values pass schema-level validation."""
        data = LoginFormData(username="", password="")
        assert data.username == ""
        assert data.password == ""

    def test_special_characters_in_password(self):
        """Special characters in password are preserved."""
        pw = "P@$$w0rd!#&*()"
        data = LoginFormData(username="user", password=pw)
        assert data.password == pw
