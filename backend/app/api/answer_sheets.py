from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db import get_db, get_session

answer_styles_bp = Blueprint("answer_styles", __name__)
answer_sheets_bp = Blueprint("answer_sheets", __name__)


def _table(name: str):
    db = get_db(current_app)
    if name not in db.metadata.tables:
        db.metadata.reflect(bind=db.engine, only=[name])
    return db.metadata.tables[name]


@answer_styles_bp.get("")
def list_styles():
    type_id = request.args.get("type_id", type=int)
    t = _table("answer_area_style")
    stmt = select(t.c.style_id, t.c.type_id, t.c.style_name, t.c.style_config, t.c.is_default, t.c.create_time)
    if type_id is not None:
        stmt = stmt.where(t.c.type_id == type_id)
    stmt = stmt.order_by(t.c.type_id.asc(), t.c.is_default.desc(), t.c.style_id.desc())
    try:
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows]})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_styles_bp.post("")
def create_style():
    payload = request.get_json(silent=True) or {}
    t = _table("answer_area_style")
    if not payload.get("type_id") or not payload.get("style_name"):
        return jsonify({"error": {"message": "type_id 与 style_name 必填", "type": "BadRequest"}}), 400

    data = {
        "type_id": int(payload["type_id"]),
        "style_name": payload["style_name"],
        "style_config": payload.get("style_config") or "{}",
        "is_default": 1 if payload.get("is_default") else 0,
        "create_time": datetime.now(),
    }

    session = get_session(current_app)
    try:
        if data["is_default"] == 1:
            session.execute(update(t).where(t.c.type_id == data["type_id"]).values(is_default=0))
        res = session.execute(insert(t).values(**data))
        session.commit()
        style_id = res.inserted_primary_key[0] if res.inserted_primary_key else None
        return jsonify({"style_id": style_id})
    except IntegrityError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": "IntegrityError"}}), 400
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_styles_bp.put("/<int:style_id>")
def update_style(style_id: int):
    payload = request.get_json(silent=True) or {}
    t = _table("answer_area_style")
    data = {k: payload.get(k) for k in ["type_id", "style_name", "style_config"] if k in payload}
    if "is_default" in payload:
        data["is_default"] = 1 if payload.get("is_default") else 0
    if not data:
        return jsonify({"ok": True})

    session = get_session(current_app)
    try:
        if data.get("is_default") == 1:
            row = session.execute(select(t.c.type_id).where(t.c.style_id == style_id)).scalar_one_or_none()
            if row is not None:
                session.execute(update(t).where(t.c.type_id == row).values(is_default=0))
        session.execute(update(t).where(t.c.style_id == style_id).values(**data))
        session.commit()
        return jsonify({"ok": True})
    except IntegrityError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": "IntegrityError"}}), 400
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_styles_bp.delete("/<int:style_id>")
def delete_style(style_id: int):
    t = _table("answer_area_style")
    session = get_session(current_app)
    try:
        session.execute(delete(t).where(t.c.style_id == style_id))
        session.commit()
        return jsonify({"ok": True})
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.get("")
def list_sheets():
    paper_id = request.args.get("paper_id", type=int)
    t = _table("exam_answer_sheet")
    stmt = select(t.c.sheet_id, t.c.paper_id, t.c.sheet_name, t.c.template_config, t.c.create_user, t.c.create_time, t.c.update_time)
    if paper_id is not None:
        stmt = stmt.where(t.c.paper_id == paper_id)
    stmt = stmt.order_by(t.c.sheet_id.desc())
    try:
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows]})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.post("")
def create_sheet():
    payload = request.get_json(silent=True) or {}
    t = _table("exam_answer_sheet")
    if not payload.get("paper_id") or not payload.get("sheet_name"):
        return jsonify({"error": {"message": "paper_id 与 sheet_name 必填", "type": "BadRequest"}}), 400

    data = {
        "paper_id": int(payload["paper_id"]),
        "sheet_name": payload["sheet_name"],
        "template_config": payload.get("template_config") or "{}",
        "create_user": payload.get("create_user") or "creator",
        "create_time": datetime.now(),
        "update_time": datetime.now(),
    }
    session = get_session(current_app)
    try:
        res = session.execute(insert(t).values(**data))
        session.commit()
        sheet_id = res.inserted_primary_key[0] if res.inserted_primary_key else None
        return jsonify({"sheet_id": sheet_id})
    except IntegrityError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": "IntegrityError"}}), 400
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.put("/<int:sheet_id>")
def update_sheet(sheet_id: int):
    payload = request.get_json(silent=True) or {}
    t = _table("exam_answer_sheet")
    data = {k: payload.get(k) for k in ["sheet_name", "template_config", "create_user"] if k in payload}
    if not data:
        return jsonify({"ok": True})
    data["update_time"] = datetime.now()
    session = get_session(current_app)
    try:
        session.execute(update(t).where(t.c.sheet_id == sheet_id).values(**data))
        session.commit()
        return jsonify({"ok": True})
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.delete("/<int:sheet_id>")
def delete_sheet(sheet_id: int):
    t = _table("exam_answer_sheet")
    rel = _table("sheet_question_relation")
    session = get_session(current_app)
    try:
        session.execute(delete(rel).where(rel.c.sheet_id == sheet_id))
        session.execute(delete(t).where(t.c.sheet_id == sheet_id))
        session.commit()
        return jsonify({"ok": True})
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.get("/<int:sheet_id>/items")
def list_sheet_items(sheet_id: int):
    rel = _table("sheet_question_relation")
    stmt = select(
        rel.c.relation_id,
        rel.c.sheet_id,
        rel.c.question_id,
        rel.c.style_id,
        rel.c.area_sort,
        rel.c.area_score,
        rel.c.create_time,
    ).where(rel.c.sheet_id == sheet_id).order_by(rel.c.area_sort.asc())
    try:
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows]})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.put("/<int:sheet_id>/items")
def update_sheet_items(sheet_id: int):
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not isinstance(items, list):
        return jsonify({"error": {"message": "items 必须是数组", "type": "BadRequest"}}), 400

    rel = _table("sheet_question_relation")
    session = get_session(current_app)
    try:
        for it in items:
            if not it.get("question_id"):
                continue
            data = {}
            for k in ["style_id", "area_sort", "area_score"]:
                if k in it:
                    data[k] = it.get(k)
            if data:
                session.execute(
                    update(rel)
                    .where(and_(rel.c.sheet_id == sheet_id, rel.c.question_id == int(it["question_id"])))
                    .values(**data)
                )
        session.commit()
        return jsonify({"ok": True})
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@answer_sheets_bp.post("/from-paper/<int:paper_id>")
def create_sheet_from_paper(paper_id: int):
    payload = request.get_json(silent=True) or {}
    create_user = payload.get("create_user") or "creator"
    template_config = payload.get("template_config") or "{}"

    paper = _table("exam_paper")
    pqr = _table("paper_question_relation")
    qb = _table("question_bank")
    sheet = _table("exam_answer_sheet")
    rel = _table("sheet_question_relation")
    style = _table("answer_area_style")

    session = get_session(current_app)
    now = datetime.now()

    try:
        p = session.execute(select(paper).where(paper.c.paper_id == paper_id)).mappings().first()
        if p is None:
            return jsonify({"error": {"message": "试卷不存在", "type": "NotFound"}}), 404

        existing = session.execute(select(sheet).where(sheet.c.paper_id == paper_id)).mappings().first()
        if existing:
            sheet_id = existing["sheet_id"]
            session.execute(delete(rel).where(rel.c.sheet_id == sheet_id))
            session.execute(update(sheet).where(sheet.c.sheet_id == sheet_id).values(update_time=now))
        else:
            res = session.execute(
                insert(sheet).values(
                    paper_id=paper_id,
                    sheet_name=f"{p.get('paper_name')}-答题卡",
                    template_config=template_config,
                    create_user=create_user,
                    create_time=now,
                    update_time=now,
                )
            )
            sheet_id = res.inserted_primary_key[0] if res.inserted_primary_key else None
            if not sheet_id:
                raise RuntimeError("创建答题卡失败")

        q_stmt = (
            select(pqr.c.question_id, pqr.c.question_sort, pqr.c.question_score, qb.c.type_id)
            .join(qb, qb.c.question_id == pqr.c.question_id)
            .where(pqr.c.paper_id == paper_id)
            .order_by(pqr.c.question_sort.asc())
        )
        qs = session.execute(q_stmt).mappings().all()

        default_styles = {
            int(r["type_id"]): int(r["style_id"])
            for r in session.execute(select(style.c.type_id, style.c.style_id).where(style.c.is_default == 1)).mappings().all()
        }

        for q in qs:
            type_id = int(q["type_id"])
            session.execute(
                insert(rel).values(
                    sheet_id=sheet_id,
                    question_id=int(q["question_id"]),
                    style_id=default_styles.get(type_id),
                    area_sort=int(q["question_sort"]),
                    area_score=q["question_score"],
                    create_time=now,
                )
            )

        session.commit()
        return jsonify({"sheet_id": sheet_id, "item_count": len(qs)})
    except IntegrityError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": "IntegrityError"}}), 400
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
