from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from daily_brief.config.settings import DatabaseConfig
from daily_brief.storage.models import Base


def _resolve_sqlite_path(url: str) -> Path | None:
    prefix = "sqlite:///"
    if url.startswith(prefix):
        return Path(url.removeprefix(prefix))
    return None


def build_engine(config: DatabaseConfig) -> Engine:
    sqlite_path = _resolve_sqlite_path(config.url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    config.raw_payload_dir.mkdir(parents=True, exist_ok=True)
    config.outbox_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(config.url, future=True)


def init_db(config: DatabaseConfig) -> None:
    engine = build_engine(config)
    Base.metadata.create_all(engine)
    _migrate_legacy_tables(engine)


def make_session_factory(config: DatabaseConfig) -> sessionmaker[Session]:
    engine = build_engine(config)
    return sessionmaker(
        bind=engine, autoflush=False, autocommit=False, future=True, expire_on_commit=False
    )


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _migrate_legacy_tables(engine: Engine) -> None:
    inspector = inspect(engine)
    if "runs" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("runs")}
    statements = {
        "target_date": "ALTER TABLE runs ADD COLUMN target_date DATE",
        "timezone_name": "ALTER TABLE runs ADD COLUMN timezone_name VARCHAR(64) NOT NULL DEFAULT 'UTC'",
        "mode": "ALTER TABLE runs ADD COLUMN mode VARCHAR(32) NOT NULL DEFAULT 'manual'",
        "dry_run": "ALTER TABLE runs ADD COLUMN dry_run BOOLEAN NOT NULL DEFAULT 0",
        "force_send": "ALTER TABLE runs ADD COLUMN force_send BOOLEAN NOT NULL DEFAULT 0",
    }
    with engine.begin() as connection:
        for column_name, statement in statements.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))
        if "target_date" not in existing_columns:
            connection.execute(
                text("UPDATE runs SET target_date = DATE(started_at) WHERE target_date IS NULL")
            )
