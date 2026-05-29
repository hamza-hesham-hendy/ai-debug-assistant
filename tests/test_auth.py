"""
Tests for authentication routes: /register, /login, /logout.
Covers happy paths and edge cases (duplicate users, bad credentials, missing fields).
"""

from fastapi import status

# Use the non-deprecated constant for 422
HTTP_422 = 422


class TestRegister:
    """Tests for GET /register and POST /register."""

    def test_register_page_loads(self, client):
        """GET /register returns 200 HTML."""
        response = client.get("/register")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_register_success(self, client):
        """Valid registration redirects to /login."""
        response = client.post(
            "/register",
            data={
                "username": "brand_new_user_A",
                "email": "brand_new_A@example.com",
                "password": "Password123",
            },
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_303_SEE_OTHER
        assert response.headers["location"] == "/login"

    def test_register_duplicate_username(self, client):
        """Registering with an already-taken username returns 409."""
        payload = {
            "username": "dupuser_X",
            "email": "dup1_X@example.com",
            "password": "pass",
        }
        client.post("/register", data=payload)

        response = client.post(
            "/register",
            data={
                "username": "dupuser_X",  # same username
                "email": "dup2_X@example.com",  # different email
                "password": "pass",
            },
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already registered" in response.text.lower()

    def test_register_duplicate_email(self, client):
        """Registering with an already-taken email returns 409."""
        payload = {
            "username": "emailuser1_X",
            "email": "shared_X@example.com",
            "password": "pass",
        }
        client.post("/register", data=payload)

        response = client.post(
            "/register",
            data={
                "username": "emailuser2_X",  # different username
                "email": "shared_X@example.com",  # same email
                "password": "pass",
            },
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_register_missing_username(self, client):
        """Missing username field returns 422."""
        response = client.post(
            "/register",
            data={"email": "x@example.com", "password": "pass"},
            follow_redirects=False,
        )
        assert response.status_code == HTTP_422

    def test_register_missing_email(self, client):
        """Missing email field returns 422."""
        response = client.post(
            "/register",
            data={"username": "nomail", "password": "pass"},
            follow_redirects=False,
        )
        assert response.status_code == HTTP_422

    def test_register_missing_password(self, client):
        """Missing password field returns 422."""
        response = client.post(
            "/register",
            data={"username": "nopw", "email": "nopw@example.com"},
            follow_redirects=False,
        )
        assert response.status_code == HTTP_422

    def test_register_all_fields_missing(self, client):
        """Empty form body returns 422."""
        response = client.post("/register", data={}, follow_redirects=False)
        assert response.status_code == HTTP_422


class TestLogin:
    """Tests for GET /login and POST /login."""

    def test_login_page_loads(self, client):
        """GET /login returns 200 HTML."""
        response = client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_login_success(self, registered_user, client):
        """Valid credentials redirect to / and set session_id cookie."""
        response = client.post(
            "/login",
            data={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_303_SEE_OTHER
        assert response.headers["location"] == "/"
        assert "session_id" in client.cookies

    def test_login_wrong_password(self, registered_user, client):
        """Wrong password returns 401 with error message."""
        response = client.post(
            "/login",
            data={
                "username": registered_user["username"],
                "password": "WrongPassword!",
            },
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid" in response.text.lower()

    def test_login_nonexistent_user(self, client):
        """Username that doesn't exist returns 401."""
        response = client.post(
            "/login",
            data={"username": "ghostuser_xyz_99", "password": "whatever"},
            follow_redirects=False,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_missing_username(self, client):
        """Missing username returns 422."""
        response = client.post(
            "/login",
            data={"password": "somepass"},
            follow_redirects=False,
        )
        assert response.status_code == HTTP_422

    def test_login_missing_password(self, client):
        """Missing password returns 422."""
        response = client.post(
            "/login",
            data={"username": "someone"},
            follow_redirects=False,
        )
        assert response.status_code == HTTP_422

    def test_login_empty_form(self, client):
        """Completely empty form returns 422."""
        response = client.post("/login", data={}, follow_redirects=False)
        assert response.status_code == HTTP_422

    def test_login_sets_correct_cookie(self, registered_user, client, engine):
        """The session_id cookie value matches the actual user's DB id."""
        from sqlmodel import Session, select

        from models import User

        client.post(
            "/login",
            data={
                "username": registered_user["username"],
                "password": registered_user["password"],
            },
        )
        with Session(engine) as db:
            user = db.exec(select(User).where(User.username == registered_user["username"])).first()
        assert user is not None
        assert str(user.id) == client.cookies.get("session_id")


class TestLogout:
    """Tests for GET /logout."""

    def test_logout_redirects_to_login(self, logged_in_client):
        """Logout redirects to /login."""
        response = logged_in_client.get("/logout", follow_redirects=False)
        assert response.status_code == status.HTTP_303_SEE_OTHER
        assert "/login" in response.headers["location"]

    def test_logout_clears_cookie(self, logged_in_client):
        """After logout the session_id cookie is removed."""
        logged_in_client.get("/logout")
        assert "session_id" not in logged_in_client.cookies

    def test_logout_unauthenticated(self, client):
        """Logging out without a cookie still works (no crash)."""
        response = client.get("/logout", follow_redirects=False)
        assert response.status_code == status.HTTP_303_SEE_OTHER
