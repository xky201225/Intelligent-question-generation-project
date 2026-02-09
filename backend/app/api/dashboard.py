from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, current_app, jsonify
from sqlalchemy import select, func, desc, text
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db, get_session

dashboard_bp = Blueprint("dashboard", __name__)


def _table(name: str):
    db = get_db(current_app)
    if name not in db.metadata.tables:
        db.metadata.reflect(bind=db.engine, only=[name])
    return db.metadata.tables[name]


@dashboard_bp.get("/stats")
def get_stats():
    session = get_session(current_app)
    try:
        u = _table("user")
        s = _table("subject_dict")
        t = _table("textbook")
        q = _table("question_bank")
        p = _table("exam_paper")
        
        # Count pending reviews (questions with review_status=0)
        pending_q = int(session.execute(select(func.count()).select_from(q).where(q.c.review_status == 0)).scalar_one() or 0)
        
        # Count pending reviews (papers with review_status=0)
        pending_p = int(session.execute(select(func.count()).select_from(p).where(p.c.review_status == 0)).scalar_one() or 0)

        return jsonify(
            {
                "users": int(session.execute(select(func.count()).select_from(u)).scalar_one() or 0),
                "subjects": int(session.execute(select(func.count()).select_from(s)).scalar_one() or 0),
                "textbooks": int(session.execute(select(func.count()).select_from(t)).scalar_one() or 0),
                "questions": int(session.execute(select(func.count()).select_from(q)).scalar_one() or 0),
                "papers": int(session.execute(select(func.count()).select_from(p)).scalar_one() or 0),
                "pending_questions": pending_q,
                "pending_papers": pending_p,
            }
        )
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@dashboard_bp.get("/trend")
def get_trend():
    """Get question creation trend for last 30 days"""
    session = get_session(current_app)
    try:
        q = _table("question_bank")
        p = _table("exam_paper")
        
        # Last 30 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=29) # 30 days including today
        
        # MySQL specific date formatting
        date_fmt = func.date_format(q.c.create_time, '%Y-%m-%d')
        
        # Question Trend
        stmt_q = (
            select(
                date_fmt.label("date"), 
                func.count().label("count")
            )
            .where(q.c.create_time >= start_date)
            .group_by("date")
            .order_by("date")
        )
        rows_q = session.execute(stmt_q).all()
        data_q = {r[0]: r[1] for r in rows_q}

        # Paper Trend
        date_fmt_p = func.date_format(p.c.create_time, '%Y-%m-%d')
        stmt_p = (
            select(
                date_fmt_p.label("date"), 
                func.count().label("count")
            )
            .where(p.c.create_time >= start_date)
            .group_by("date")
            .order_by("date")
        )
        rows_p = session.execute(stmt_p).all()
        data_p = {r[0]: r[1] for r in rows_p}
        
        # Fill missing dates
        result_dates = []
        result_q = []
        result_p = []
        
        curr = start_date
        while curr <= end_date:
            d_str = curr.strftime("%Y-%m-%d")
            result_dates.append(d_str)
            result_q.append(data_q.get(d_str, 0))
            result_p.append(data_p.get(d_str, 0))
            curr += timedelta(days=1)
            
        return jsonify({
            "dates": result_dates,
            "questions": result_q,
            "papers": result_p
        })
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@dashboard_bp.get("/distribution")
def get_distribution():
    """Get question distribution by subject"""
    session = get_session(current_app)
    try:
        q = _table("question_bank")
        s = _table("subject_dict")
        
        stmt = (
            select(
                s.c.subject_name,
                func.count(q.c.question_id).label("count")
            )
            .join(q, q.c.subject_id == s.c.subject_id)
            .group_by(s.c.subject_name)
            .order_by(desc("count"))
        )
        
        rows = session.execute(stmt).all()
        
        return jsonify({
            "items": [{"name": r[0], "value": r[1]} for r in rows]
        })
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
