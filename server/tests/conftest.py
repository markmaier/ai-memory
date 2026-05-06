import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("AUTH_DISABLED", "false")
os.environ.setdefault("MEM0_TELEMETRY", "false")

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import auth as auth_module
import db as db_module
from mem0 import Memory
from models import APIKey, Base, User


Memory.from_config = classmethod(lambda cls, config: SimpleNamespace(llm=SimpleNamespace(), vector_store=SimpleNamespace()))

import main as main_module


TEST_PASSWORD = "password123"


def _build_test_session_factory(db_path: Path):
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def test_engine(tmp_path):
    engine, _ = _build_test_session_factory(tmp_path / "test.db")
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    session_factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def override_database(test_engine, monkeypatch):
    session_factory = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(db_module, "SessionLocal", session_factory)
    monkeypatch.setattr(main_module, "SessionLocal", session_factory)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[db_module.get_db] = override_get_db

    if not any(getattr(route, "path", None) == "/api/health" for route in main_module.app.routes):

        @main_module.app.get("/api/health", include_in_schema=False)
        def health_check():
            return {"status": "ok"}

    yield

    main_module.app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def cleanup_database(test_engine):
    yield
    with test_engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


@pytest.fixture()
def client():
    with TestClient(main_module.app) as test_client:
        yield test_client


def create_test_user(db, email, password, role="admin"):
    user = User(
        name=email.split("@")[0],
        email=email,
        password_hash=auth_module.hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_test_api_key(db, user_id):
    full_key, prefix, key_hash = auth_module.generate_api_key()
    api_key = APIKey(
        key_prefix=prefix,
        key_hash=key_hash,
        label="test-key",
        created_by=user_id,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, full_key


def get_auth_headers(client, email, password):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin_user(db_session):
    return create_test_user(db_session, "admin@example.com", TEST_PASSWORD, role="admin")


@pytest.fixture()
def auth_headers(client, admin_user):
    return get_auth_headers(client, admin_user.email, TEST_PASSWORD)
