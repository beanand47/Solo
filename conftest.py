import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models import User
import routers.auth as auth_module


TEST_DATABASE_URL = "sqlite:///./test_solo.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db, monkeypatch):
    monkeypatch.setattr(auth_module, "validate_csrf_token", lambda token: token == "test")
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db):
    user = User(
        name="Test User",
        email="test@example.com",
        password_hash=auth_module.hash_password("testpass123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": "test@example.com", "password": "testpass123", "name": "Test User"}


@pytest.fixture
def authenticated_client(client, test_user):
    token = auth_module.create_session_token(test_user["id"])
    client.cookies.set("session", token)
    return client
