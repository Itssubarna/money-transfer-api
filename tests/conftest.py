from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.db.session import create_db_engine
from app.db.models import Base
from app.main import app


@pytest.fixture
def engine(tmp_path) -> Iterator[Engine]:
    # A file-backed database (not :memory:) so concurrent tests get
    # genuinely separate connections, built with the app's own engine
    # factory (WAL, busy timeout, BEGIN IMMEDIATE for writes).
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    def override_get_session():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def create_account(client: TestClient) -> Callable[..., dict]:
    def _create(name: str = "Alice", initial_balance: int = 0) -> dict:
        response = client.post(
            "/accounts",
            json={"name": name, "initial_balance": initial_balance},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create


@pytest.fixture
def get_balance(client: TestClient) -> Callable[[int], int]:
    def _get(account_id: int) -> int:
        response = client.get(f"/accounts/{account_id}")
        assert response.status_code == 200, response.text
        return response.json()["balance"]

    return _get
