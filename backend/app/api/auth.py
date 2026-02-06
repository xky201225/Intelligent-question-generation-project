from __future__ import annotations

from datetime import datetime
import base64
import random
import string
import time
import uuid

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import insert, select, update, func
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db, get_session

auth_bp = Blueprint("auth", __name__)


def _table(name: str):
    db = get_db(current_app)
    if name not in db.metadata.tables:
        db.metadata.reflect(bind=db.engine, only=[name])
    return db.metadata.tables[name]


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=current_app.config.get("AUTH_TOKEN_SALT", "auth-token"))


def issue_token(user_id: int) -> str:
    return _serializer().dumps({"uid": int(user_id)})


def verify_token(token: str) -> dict:
    expires = int(current_app.config.get("AUTH_TOKEN_EXPIRES_SECONDS", 7 * 24 * 3600))
    return _serializer().loads(token, max_age=expires)


_captchas: dict[str, dict] = {}


def _rand_text(n: int = 4) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(n))


def _captcha_svg(text: str, width: int = 120, height: int = 40) -> str:
    # 验证码配置参数 - 可在此处调整识别度
    line_count = 5       # 干扰线条数（原为6，减少条数可提高清晰度）
    point_count = 50     # 干扰点数
    font_size = 20       # 字体大小（原为22，增大可提高清晰度）
    rotate_range = 10    # 旋转角度范围 +/-（原为20，减小可减少歪斜）
    jitter_range = 1     # 位置抖动范围 +/-（原为5-6，减小可减少重叠）
    
    lines = []
    for _ in range(line_count):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        color = random.choice(["#69c", "#c96", "#9c6", "#c69"])
        lines.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1" />')
    
    points = []
    for _ in range(point_count):
        x, y = random.randint(0, width), random.randint(0, height)
        color = random.choice(["#69c", "#c96", "#9c6", "#c69"])
        points.append(f'<circle cx="{x}" cy="{y}" r="1" fill="{color}" />')

    chars = []
    # 增加左右内边距，防止字符靠边被裁
    padding = 10
    available_width = width - (padding * 2)
    step = available_width // len(text)
    
    for i, ch in enumerate(text):
        # 坐标 = 左边距 + 当前格起点 + 半格宽 + 随机抖动
        x = padding + int(step * i) + (step // 2) + random.randint(-jitter_range, jitter_range)
        y = height // 2 + random.randint(-jitter_range, jitter_range)
        rotate = random.randint(-rotate_range, rotate_range)
        # 改为彩色，使用稍深的颜色以保证可读性
        color = random.choice([
            "#e44", "#4e4", "#44e", "#c60", "#808", 
            "#088", "#d22", "#292", "#229", "#a50"
        ])
        chars.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{font_size}" font-family="monospace" text-anchor="middle" dominant-baseline="central" transform="rotate({rotate},{x},{y})">{ch}</text>')
    
    # 增加 viewBox 属性以确保正确缩放
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="#f7f7f7"/><g>{"".join(lines)}{"".join(points)}{"".join(chars)}</g></svg>'
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def _create_captcha() -> dict:
    text = _rand_text(4)
    cid = uuid.uuid4().hex
    img = _captcha_svg(text)
    _captchas[cid] = {"text": text.lower(), "exp": time.time() + 300}
    return {"id": cid, "image": img}


def _verify_captcha(cid: str, user_text: str) -> bool:
    if not cid or not user_text:
        return False
    data = _captchas.pop(cid, None)
    if not data:
        return False
    if time.time() > float(data.get("exp") or 0):
        return False
    return str(user_text).lower().strip() == str(data.get("text") or "")


@auth_bp.get("/captcha")
def captcha():
    c = _create_captcha()
    return jsonify(c)


def _generate_invite_code(session, u_table) -> str:
    for _ in range(20):
        code = _rand_text(6)
        exists = session.execute(select(func.count()).select_from(u_table).where(u_table.c.invitationCode == code)).scalar_one()
        if int(exists or 0) == 0:
            return code
    return uuid.uuid4().hex[:6]


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    captcha_id = (payload.get("captchaId") or "").strip()
    captcha_text = (payload.get("captchaText") or "").strip()
    password = payload.get("password") or ""

    if not name or not password:
        return jsonify({"error": {"message": "name 与 password 必填", "type": "BadRequest"}}), 400
    
    if not _verify_captcha(captcha_id, captcha_text):
        return jsonify({"error": {"message": "验证码错误", "type": "BadRequest"}}), 400

    u = _table("user")
    stmt = select(u.c.id, u.c.name, u.c.password, u.c.status).where(u.c.name == name).limit(1)
    session = get_session(current_app)
    try:
        row = session.execute(stmt).mappings().first()
        if not row:
            return jsonify({"error": {"message": "用户名或密码错误", "type": "Unauthorized"}}), 401
        if int(row.get("status") or 0) != 1:
            return jsonify({"error": {"message": "账号已被禁用", "type": "Forbidden"}}), 403

        stored = row.get("password") or ""
        ok = False
        try:
            ok = check_password_hash(stored, password)
        except Exception:
            ok = False
        if not ok:
            if stored and ":" not in str(stored) and str(stored) == password:
                ok = True
                session.execute(update(u).where(u.c.id == row["id"]).values(password=generate_password_hash(password)))
                session.commit()

        if not ok:
            return jsonify({"error": {"message": "用户名或密码错误", "type": "Unauthorized"}}), 401

        token = issue_token(int(row["id"]))
        return jsonify({"token": token, "user": {"id": int(row["id"]), "name": row.get("name"), "status": int(row.get("status") or 0)}})
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    password = payload.get("password") or ""
    captcha_id = (payload.get("captchaId") or "").strip()
    captcha_text = (payload.get("captchaText") or "").strip()
    invitation_code = (payload.get("invitationCode") or "").strip()

    if not name or not password:
        return jsonify({"error": {"message": "name 与 password 必填", "type": "BadRequest"}}), 400

    if not _verify_captcha(captcha_id, captcha_text):
        return jsonify({"error": {"message": "验证码错误", "type": "BadRequest"}}), 400

    u = _table("user")
    session = get_session(current_app)
    
    try:
        total = session.execute(select(func.count()).select_from(u)).scalar_one() or 0
        if int(total) > 0:
            if not invitation_code:
                return jsonify({"error": {"message": "需要有效邀请码", "type": "Forbidden"}}), 403
            inviter = session.execute(select(u.c.id).where(u.c.invitationCode == invitation_code).limit(1)).scalar_one_or_none()
            if inviter is None:
                return jsonify({"error": {"message": "邀请码错误", "type": "Forbidden"}}), 403

        exists = session.execute(select(u.c.id).where(u.c.name == name).limit(1)).scalar_one_or_none()
        if exists:
            return jsonify({"error": {"message": "用户名已存在", "type": "Conflict"}}), 409
            
        new_invite = _generate_invite_code(session, u)
        now = datetime.now()
        
        res = session.execute(
            insert(u).values(
                name=name,
                password=generate_password_hash(password),
                invitationCode=new_invite,
                time=now,
                status=1,
            )
        )
        session.commit()
        user_id = res.inserted_primary_key[0] if res.inserted_primary_key else None
        if not user_id:
            return jsonify({"error": {"message": "注册失败", "type": "InternalError"}}), 500
            
        token = issue_token(int(user_id))
        return jsonify({"token": token, "user": {"id": int(user_id), "name": name, "status": 1, "invitationCode": new_invite}})
    except SQLAlchemyError as err:
        session.rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500


@auth_bp.get("/me")
def me():
    token = None
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    token = token or request.args.get("token", type=str)
    if not token:
        return jsonify({"error": {"message": "未登录", "type": "Unauthorized"}}), 401

    try:
        data = verify_token(token)
    except SignatureExpired:
        return jsonify({"error": {"message": "登录已过期", "type": "Unauthorized"}}), 401
    except BadSignature:
        return jsonify({"error": {"message": "无效登录", "type": "Unauthorized"}}), 401

    uid = int(data.get("uid") or 0)
    if uid <= 0:
        return jsonify({"error": {"message": "无效登录", "type": "Unauthorized"}}), 401

    u = _table("user")
    stmt = select(u.c.id, u.c.name, u.c.status, u.c.invitationCode).where(u.c.id == uid).limit(1)
    row = get_session(current_app).execute(stmt).mappings().first()
    if not row:
        return jsonify({"error": {"message": "用户不存在", "type": "Unauthorized"}}), 401
    if int(row.get("status") or 0) != 1:
        return jsonify({"error": {"message": "账号已被禁用", "type": "Forbidden"}}), 403
    
    return jsonify({"user": {"id": int(row["id"]), "name": row.get("name"), "status": int(row.get("status") or 0), "invitationCode": row.get("invitationCode")}})


@auth_bp.get("/stats")
def stats():
    session = get_session(current_app)
    try:
        s = _table("subject_dict")
        t = _table("textbook")
        q = _table("question_bank")
        p = _table("exam_paper")
        u = _table("user")
        return jsonify(
            {
                "subjects": int(session.execute(select(func.count()).select_from(s)).scalar_one() or 0),
                "textbooks": int(session.execute(select(func.count()).select_from(t)).scalar_one() or 0),
                "questions": int(session.execute(select(func.count()).select_from(q)).scalar_one() or 0),
                "papers": int(session.execute(select(func.count()).select_from(p)).scalar_one() or 0),
                "users": int(session.execute(select(func.count()).select_from(u)).scalar_one() or 0),
            }
        )
    except SQLAlchemyError as err:
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
