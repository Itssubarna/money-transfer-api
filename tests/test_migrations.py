"""Checks that the Alembic migrations build the schema the models expect."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.models import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def alembic_config(url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def test_migrations_match_models_and_downgrade_cleanly(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    config = alembic_config(url)
    engine = create_engine(url)

    command.upgrade(config, "head")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == [], f"models and migrations have drifted: {diff}"

    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
