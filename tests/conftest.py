"""
Pytest fixtures — SQLite in-memory for fast, dependency-free tests.
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db

TEST_DB_URL = "sqlite:///./test_foryou.db"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)

# SQLite: enable foreign keys
@event.listens_for(engine, "connect")
def set_sqlite_pragma(conn, _):
    conn.execute("PRAGMA foreign_keys=ON")

TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        if os.path.exists("test_foryou.db"):
            os.remove("test_foryou.db")
    except PermissionError:
        pass  # Windows file lock — file will be cleaned up on next run


@pytest.fixture()
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
