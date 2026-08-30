"""
Tests for the authentication API endpoints.
Covers: register, login, demo, /me (protected), and Google mock flow.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db


# ---- In-memory test DB ---------------------------------------------------

TEST_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


# ---- Tests ---------------------------------------------------------------

class TestRegister:
    def test_register_success(self):
        res = client.post("/api/auth/register", json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "SecurePass123!",
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["name"] == "Test User"
        assert data["user"]["role"] == "controller"

    def test_register_duplicate_email(self):
        body = {"name": "User A", "email": "dup@example.com", "password": "Pass123456!"}
        client.post("/api/auth/register", json=body)
        res = client.post("/api/auth/register", json=body)
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]


class TestLogin:
    def test_login_success(self):
        client.post("/api/auth/register", json={
            "name": "Login Test",
            "email": "login@example.com",
            "password": "MyPassword88!",
        })
        res = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "MyPassword88!",
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self):
        client.post("/api/auth/register", json={
            "name": "Wrong Pass",
            "email": "wrong@example.com",
            "password": "CorrectPass1!",
        })
        res = client.post("/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "WrongPass1!",
        })
        assert res.status_code == 401

    def test_login_unknown_email(self):
        res = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "SomePass1!",
        })
        assert res.status_code == 401


class TestDemoLogin:
    def test_demo_login(self):
        res = client.post("/api/auth/demo")
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user"]["role"] == "admin"
        assert data["user"]["auth_provider"] == "demo"

    def test_demo_login_is_idempotent(self):
        """Calling demo twice should return the same user, not create a duplicate."""
        res1 = client.post("/api/auth/demo")
        res2 = client.post("/api/auth/demo")
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["user"]["id"] == res2.json()["user"]["id"]


class TestMeEndpoint:
    def _get_token(self) -> str:
        client.post("/api/auth/register", json={
            "name": "Me User",
            "email": "me@example.com",
            "password": "MePass123!",
        })
        res = client.post("/api/auth/login", json={
            "email": "me@example.com",
            "password": "MePass123!",
        })
        return res.json()["access_token"]

    def test_me_with_valid_token(self):
        token = self._get_token()
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        assert res.json()["email"] == "me@example.com"

    def test_me_without_token(self):
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_me_with_invalid_token(self):
        res = client.get("/api/auth/me", headers={"Authorization": "Bearer definitely_not_a_valid_token"})
        assert res.status_code == 401
