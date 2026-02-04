from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db, get_session

dicts_bp = Blueprint("dicts", __name__)


def _table(name: str):
    db = get_db(current_app)
    if name not in db.metadata.tables:
        db.metadata.reflect(bind=db.engine, only=[name])
    return db.metadata.tables[name]


@dicts_bp.get("/subjects")
def list_subjects():
    try:
        t = _table("subject_dict")
        stmt = select(
            t.c.subject_id,
            t.c.subject_name,
            t.c.subject_code,
            t.c.target_grade,
            t.c.start_semester,
            t.c.teach_type,
            t.c.is_enable,
        )
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows]})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@dicts_bp.get("/question-types")
def list_question_types():
    try:
        t = _table("question_type_dict")
        stmt = select(t.c.type_id, t.c.type_name, t.c.type_code)
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows]})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@dicts_bp.get("/difficulties")
def list_difficulties():
    try:
        t = _table("question_difficulty_dict")
        stmt = select(t.c.difficulty_id, t.c.difficulty_name, t.c.difficulty_level)
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows]})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
