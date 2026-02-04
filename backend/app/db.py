from __future__ import annotations

from dataclasses import dataclass

from flask import Flask, g
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True)
class DbState:
    engine: Engine
    session_factory: sessionmaker[Session]
    metadata: MetaData


def build_mysql_url(app: Flask) -> str:
    host = app.config["MYSQL_HOST"]
    port = app.config["MYSQL_PORT"]
    db = app.config["MYSQL_DB"]
    user = app.config["MYSQL_USER"]
    pwd = app.config["MYSQL_PASSWORD"]
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"


def init_db(app: Flask) -> None:
    url = build_mysql_url(app)
    engine = create_engine(url, echo=app.config.get("SQLALCHEMY_ECHO", False), pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    metadata = MetaData()

    try:
        metadata.reflect(bind=engine, views=False)
    except SQLAlchemyError:
        pass

    app.extensions["db_state"] = DbState(engine=engine, session_factory=session_factory, metadata=metadata)


def get_db(app: Flask) -> DbState:
    return app.extensions["db_state"]


def get_session(app: Flask) -> Session:
    if "db_session" not in g:
        g.db_session = get_db(app).session_factory()
    return g.db_session


def close_session(err=None) -> None:
    session = g.pop("db_session", None)
    if session is not None:
        session.close()
