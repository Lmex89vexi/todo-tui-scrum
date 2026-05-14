from __future__ import annotations

import os

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base


DEFAULT_DB_URL = "sqlite:///./todo.db"


def get_database_url() -> str:
    return os.getenv("TODO_DB_URL", DEFAULT_DB_URL)


def get_engine():
    return create_engine(get_database_url(), future=True)


def init_db(engine) -> None:
    logger.debug("Initializing database schema")
    Base.metadata.create_all(engine)


def get_session_factory():
    engine = get_engine()
    init_db(engine)
    logger.debug("Session factory ready")
    return sessionmaker(bind=engine, future=True)
