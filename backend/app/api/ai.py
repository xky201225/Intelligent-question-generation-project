from __future__ import annotations

import json
import os
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import and_, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db, get_session
from app.services.deepseek import get_deepseek_client

ai_bp = Blueprint("ai", __name__)


def _table(name: str):
    db = get_db(current_app)
    if name not in db.metadata.tables:
        db.metadata.reflect(bind=db.engine, only=[name])
    return db.metadata.tables[name]


def _chapter_summary_path(chapter_id: int) -> str:
    return os.path.join(current_app.config["UPLOAD_DIR"], "chapter_summaries", f"{chapter_id}.txt")


def _extract_json_list(text: str) -> list[dict]:
    text = text.strip()
    if text.startswith("["):
        return json.loads(text)
    m = re.search(r"\\[[\\s\\S]*\\]", text)
    if not m:
        raise ValueError("AI 返回内容不是 JSON 数组")
    return json.loads(m.group(0))


@ai_bp.post("/generate-questions")
def generate_questions():
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    chapter_id = payload.get("chapter_id")
    type_id = payload.get("type_id")
    difficulty_id = payload.get("difficulty_id")
    count = payload.get("count")
    create_user = payload.get("create_user") or "ai"

    if not subject_id or not chapter_id or not type_id or not difficulty_id or not count:
        return jsonify({"error": {"message": "subject_id/chapter_id/type_id/difficulty_id/count 必填", "type": "BadRequest"}}), 400

    try:
        count = int(count)
        if count < 1 or count > 50:
            raise ValueError()
    except Exception:
        return jsonify({"error": {"message": "count 范围 1-50", "type": "BadRequest"}}), 400

    qb = _table("question_bank")
    ch = _table("textbook_chapter")

    try:
        session = get_session(current_app)
        chapter = session.execute(select(ch).where(ch.c.chapter_id == chapter_id)).mappings().first()
        if chapter is None:
            return jsonify({"error": {"message": "章节不存在", "type": "NotFound"}}), 404

        summary = ""
        sp = _chapter_summary_path(int(chapter_id))
        if os.path.exists(sp):
            with open(sp, "r", encoding="utf-8") as f:
                summary = f.read().strip()

        sample_stmt = (
            select(qb.c.question_id, qb.c.question_content, qb.c.question_answer, qb.c.question_analysis)
            .where(and_(qb.c.chapter_id == chapter_id, qb.c.review_status == 1))
            .order_by(qb.c.question_id.desc())
            .limit(10)
        )
        sample = session.execute(sample_stmt).mappings().all()
        source_ids = [str(s["question_id"]) for s in sample]

        system_prompt = "你是出题助理。你必须严格输出 JSON 数组，不要输出任何多余文本。"
        user_prompt = (
            "请为指定教材章节生成题目，要求：\n"
            "1) 只生成与章节相关的题\n"
            "2) 难度与题型遵循要求\n"
            "3) 输出严格 JSON 数组，每个元素包含字段：question_content, question_answer, question_analysis, question_score\n"
            "4) question_content 内可包含选项（如A/B/C/D），但仍是纯文本\n\n"
            f"章节名称：{chapter['chapter_name']}\n"
            f"章节概要：{summary if summary else '(暂无概要)'}\n"
            f"目标数量：{count}\n"
            f"题型ID：{type_id}\n"
            f"难度ID：{difficulty_id}\n\n"
            "参考题目（用于风格与覆盖点，不要重复）：\n"
        )
        for i, s in enumerate(sample, start=1):
            user_prompt += f"\n{i}. 题干：{s.get('question_content')}\n   答案：{s.get('question_answer')}\n   解析：{s.get('question_analysis')}\n"

        client = get_deepseek_client()
        raw = client.chat(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.7)
        items = _extract_json_list(raw)

        now = datetime.now()
        inserted = 0
        created_ids: list[int] = []
        for it in items[:count]:
            content = (it.get("question_content") or "").strip()
            if not content:
                continue
            data = {
                "subject_id": subject_id,
                "chapter_id": chapter_id,
                "type_id": type_id,
                "difficulty_id": difficulty_id,
                "question_content": content,
                "question_answer": it.get("question_answer"),
                "question_analysis": it.get("question_analysis"),
                "question_score": it.get("question_score"),
                "is_ai_generated": 1,
                "source_question_ids": ",".join(source_ids) if source_ids else None,
                "review_status": 0,
                "reviewer": None,
                "review_time": None,
                "create_user": create_user,
                "create_time": now,
                "update_time": now,
            }
            res = session.execute(insert(qb).values(**data))
            if res.inserted_primary_key:
                created_ids.append(res.inserted_primary_key[0])
            inserted += 1

        session.commit()
        return jsonify({"ok": True, "inserted": inserted, "question_ids": created_ids})
    except (ValueError, json.JSONDecodeError) as err:
        get_session(current_app).rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
    except SQLAlchemyError as err:
        get_session(current_app).rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
    except Exception as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@ai_bp.get("/pending")
def list_pending():
    qb = _table("question_bank")
    subject_id = request.args.get("subject_id", type=int)
    chapter_id = request.args.get("chapter_id", type=int)
    page = max(1, request.args.get("page", default=1, type=int))
    page_size = min(100, max(1, request.args.get("page_size", default=20, type=int)))

    where = [qb.c.review_status == 0]
    if subject_id is not None:
        where.append(qb.c.subject_id == subject_id)
    if chapter_id is not None:
        where.append(qb.c.chapter_id == chapter_id)

    stmt = (
        select(
            qb.c.question_id,
            qb.c.subject_id,
            qb.c.chapter_id,
            qb.c.type_id,
            qb.c.difficulty_id,
            qb.c.question_content,
            qb.c.question_answer,
            qb.c.question_analysis,
            qb.c.question_score,
            qb.c.is_ai_generated,
            qb.c.source_question_ids,
            qb.c.create_user,
            qb.c.create_time,
        )
        .where(and_(*where))
        .order_by(qb.c.question_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    try:
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows], "page": page, "page_size": page_size})
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@ai_bp.post("/verify")
def verify_question():
    payload = request.get_json(silent=True) or {}
    question_id = payload.get("question_id")
    action = payload.get("action")
    reviewer = payload.get("reviewer") or "reviewer"
    fields = payload.get("fields") or {}

    if not question_id or action not in ["approve", "reject", "update_and_approve"]:
        return jsonify({"error": {"message": "question_id 与 action 必填", "type": "BadRequest"}}), 400

    qb = _table("question_bank")
    now = datetime.now()

    data = {"reviewer": reviewer, "review_time": now}
    if action == "reject":
        data["review_status"] = 2
    else:
        data["review_status"] = 1
        if action == "update_and_approve":
            for k in ["question_content", "question_answer", "question_analysis", "question_score", "type_id", "difficulty_id", "chapter_id", "subject_id"]:
                if k in fields:
                    data[k] = fields.get(k)

    try:
        session = get_session(current_app)
        session.execute(update(qb).where(qb.c.question_id == int(question_id)).values(**data))
        session.commit()
        return jsonify({"ok": True})
    except SQLAlchemyError as err:
        get_session(current_app).rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
