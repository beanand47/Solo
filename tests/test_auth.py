from models import User
from routers.auth import hash_password


def test_signup_success(client, db):
    response = client.post(
        "/signup",
        data={
            "name": "Valid User",
            "email": "valid@example.com",
            "password": "validpass123",
            "confirm_password": "validpass123",
            "csrf_token": "test",
        },
    )

    assert response.status_code in {302, 303}
    assert response.headers["location"] == "/dashboard"
    assert db.query(User).filter(User.email == "valid@example.com").first() is not None


def test_signup_duplicate_email(client):
    payload = {
        "name": "Valid User",
        "email": "dupe@example.com",
        "password": "validpass123",
        "confirm_password": "validpass123",
        "csrf_token": "test",
    }
    client.post("/signup", data=payload)
    response = client.post("/signup", data=payload)

    assert response.status_code == 200
    assert "already exists" in response.text


def test_signup_password_mismatch(client):
    response = client.post(
        "/signup",
        data={
            "name": "Valid User",
            "email": "mismatch@example.com",
            "password": "validpass123",
            "confirm_password": "different123",
            "csrf_token": "test",
        },
    )

    assert response.status_code == 200
    assert "Passwords do not match" in response.text


def test_signup_short_password(client):
    response = client.post(
        "/signup",
        data={
            "name": "Valid User",
            "email": "short@example.com",
            "password": "abc",
            "confirm_password": "abc",
            "csrf_token": "test",
        },
    )

    assert response.status_code == 200
    assert "at least 8 characters" in response.text


def test_login_success(client, db):
    db.add(User(name="Login User", email="login@example.com", password_hash=hash_password("loginpass123")))
    db.commit()

    response = client.post(
        "/login",
        data={"email": "login@example.com", "password": "loginpass123", "csrf_token": "test"},
    )

    assert response.status_code in {302, 303}
    assert "session" in response.cookies


def test_login_wrong_password(client, db):
    db.add(User(name="Login User", email="wrong@example.com", password_hash=hash_password("loginpass123")))
    db.commit()

    response = client.post(
        "/login",
        data={"email": "wrong@example.com", "password": "badpass123", "csrf_token": "test"},
    )

    assert response.status_code == 200
    assert "Invalid email or password" in response.text
    assert "session" not in response.cookies


def test_login_nonexistent_email(client):
    response = client.post(
        "/login",
        data={"email": "missing@example.com", "password": "badpass123", "csrf_token": "test"},
    )

    assert response.status_code == 200
    assert "Invalid email or password" in response.text


def test_logout(authenticated_client):
    response = authenticated_client.get("/logout")

    assert response.status_code in {302, 303}
    assert response.headers["location"] == "/login"
    assert "session=" in response.headers.get("set-cookie", "").lower()


def test_protected_route_redirect(client):
    response = client.get("/dashboard")

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_csrf_missing(client):
    response = client.post(
        "/login",
        data={"email": "test@example.com", "password": "testpass123"},
    )

    assert response.status_code == 422
