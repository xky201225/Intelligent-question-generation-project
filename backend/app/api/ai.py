from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from sqlalchemy import and_, insert, select, update, func
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db, get_session
from app.services.deepseek import get_deepseek_client

ai_bp = Blueprint("ai", __name__)

_executor = ThreadPoolExecutor(max_workers=2)
_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}

MAX_FILL_ATTEMPTS = 3


def _table(name: str):
    db = get_db(current_app)
    if name not in db.metadata.tables:
        db.metadata.reflect(bind=db.engine, only=[name])
    return db.metadata.tables[name]


def _extract_json_list(text: str) -> list[dict]:
    text = (text or "").strip()

    # 去掉常见 markdown code fence
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text).strip()
        text = re.sub(r"\s*```$", "", text).strip()

    start = text.find("[")
    if start < 0:
        raise ValueError("AI 返回内容不是 JSON 数组：未找到 [")

    def find_balanced_end(s: str, start_idx: int) -> int | None:
        in_string = False
        escape = False
        depth = 0
        for i in range(start_idx, len(s)):
            ch = s[i]
            if in_string:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return i
        return None

    end = find_balanced_end(text, start)
    candidate = text[start : end + 1] if end is not None else text[start:]

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    # 尝试“容错解析”：逐个 raw_decode，尽量取到前面完整的对象
    decoder = json.JSONDecoder()
    items: list[dict] = []
    idx = 1  # 跳过 '['
    while True:
        while idx < len(candidate) and candidate[idx] in " \t\r\n,":
            idx += 1
        if idx >= len(candidate):
            break
        if candidate[idx] == "]":
            break
        try:
            obj, next_idx = decoder.raw_decode(candidate, idx)
        except Exception:
            break
        if isinstance(obj, dict):
            items.append(obj)
        idx = next_idx
    if items:
        return items

    raise ValueError("AI 返回内容不是有效 JSON 数组")


def _job_update(job_id: str, patch: dict) -> None:
    with _jobs_lock:
        if job_id not in _jobs:
            return
        _jobs[job_id].update(patch)


def _job_snapshot(job_id: str) -> dict | None:
    with _jobs_lock:
        v = _jobs.get(job_id)
        return dict(v) if v else None


def _job_event(job_id: str, event_type: str, message: str | None = None, data: dict | None = None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        seq = int(job.get("seq") or 0) + 1
        job["seq"] = seq
        ev = {"id": seq, "ts": now, "type": event_type, "message": message, "data": data or {}}
        job.setdefault("events", []).append(ev)
        if len(job["events"]) > 4000:
            job["events"] = job["events"][-2000:]


def _pick_first(d: dict, keys: list[str]) -> str | None:
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s != "":
            return s
    return None


def _run_generation(app, job_id: str, subject_id: int, chapter_ids: list[int], rules: list[dict], create_user: str):
    with app.app_context():
        _job_update(job_id, {"status": "running", "started_at": datetime.now().isoformat(timespec="seconds")})
        _job_event(job_id, "job_start", "开始生成")
        qb = _table("question_bank")
        ch = _table("textbook_chapter")
        session = get_session(current_app)
        inserted = 0
        created_ids: list[int] = []

        try:
            stmt = select(ch.c.chapter_id, ch.c.chapter_name, ch.c.content).where(ch.c.chapter_id.in_(chapter_ids))
            chapters = session.execute(stmt).mappings().all()
            if not chapters:
                _job_update(job_id, {"status": "error", "error": "所选章节不存在"})
                _job_event(job_id, "job_error", "所选章节不存在")
                return

            for chapter in chapters:
                chapter_id = int(chapter["chapter_id"])
                summary = chapter.get("content") or ""
                _job_event(job_id, "chapter_start", f"章节：{chapter.get('chapter_name')}", {"chapter_id": chapter_id})

                for rule in rules:
                    type_id = rule["type_id"]
                    difficulty_id = rule["difficulty_id"]
                    count = rule["count"]
                    _job_event(
                        job_id,
                        "rule_start",
                        f"题型={type_id} 难度={difficulty_id} 数量={count}",
                        {"chapter_id": chapter_id, "type_id": type_id, "difficulty_id": difficulty_id, "count": count},
                    )

                    sample_stmt = (
                        select(qb.c.question_id, qb.c.question_content, qb.c.question_answer, qb.c.question_analysis)
                        .where(and_(qb.c.chapter_id == chapter_id, qb.c.review_status == 1, qb.c.type_id == type_id))
                        .order_by(qb.c.question_id.desc())
                        .limit(3)
                    )
                    sample = session.execute(sample_stmt).mappings().all()
                    source_ids = [str(s["question_id"]) for s in sample]

                    system_prompt = "你是一位大学出题助理。你必须严格输出 JSON 数组，不要输出任何多余文本。"
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
                        user_prompt += (
                            f"\n{i}. 题干：{s.get('question_content')}\n"
                            f"   答案：{s.get('question_answer')}\n"
                            f"   解析：{s.get('question_analysis')}\n"
                        )

                    client = get_deepseek_client()
                    target_count = int(count)
                    collected: list[dict] = []
                    seen_contents: set[str] = set()
                    attempt = 0

                    def call_model(prompt: str, attempt_no: int, missing: int) -> str:
                        _job_event(
                            job_id,
                            "ai_start",
                            f"请求模型中…（第{attempt_no}次，缺{missing}题）",
                            {"chapter_id": chapter_id, "type_id": type_id, "difficulty_id": difficulty_id, "attempt": attempt_no, "missing": missing},
                        )
                        try:
                            raw_chunks: list[str] = []
                            buf = ""
                            last_flush = time.time()
                            for chunk in client.chat_stream(system_prompt=system_prompt, user_prompt=prompt, temperature=0.7):
                                raw_chunks.append(chunk)
                                buf += chunk
                                now_ts = time.time()
                                if len(buf) >= 200 or "\n" in buf or (now_ts - last_flush) >= 0.8:
                                    _job_event(job_id, "ai_delta", data={"text": buf})
                                    buf = ""
                                    last_flush = now_ts
                            if buf:
                                _job_event(job_id, "ai_delta", data={"text": buf})
                            raw_text = "".join(raw_chunks)
                        except Exception as err:
                            _job_event(job_id, "ai_error", f"流式输出不可用，改用普通请求：{err}")
                            raw_text = client.chat(system_prompt=system_prompt, user_prompt=prompt, temperature=0.7)
                            _job_event(job_id, "ai_delta", data={"text": raw_text})
                        _job_event(job_id, "ai_end", "模型返回完成")
                        return raw_text

                    while len(collected) < target_count and attempt < MAX_FILL_ATTEMPTS:
                        attempt += 1
                        missing = target_count - len(collected)

                        prompt = user_prompt.replace(f"目标数量：{count}\n", f"目标数量：{missing}\n")
                        if attempt > 1:
                            existed = "\n".join([f"- {x['question_content']}" for x in collected[:50]])
                            prompt += (
                                "\n补齐要求：\n"
                                f"1) 你只需要补齐缺口：再生成 {missing} 道新题\n"
                                "2) 只输出 JSON 数组，不要输出 ```json 或任何解释文本\n"
                                "3) 绝对不要重复已有题干\n"
                                f"\n已生成题干（不要重复）：\n{existed}\n"
                            )

                        _job_event(job_id, "rule_retry", f"补齐生成：第{attempt}次（还差{missing}题）")
                        raw = call_model(prompt, attempt, missing)
                        try:
                            items = _extract_json_list(raw)
                        except Exception as err:
                            _job_event(job_id, "rule_warn", f"解析失败（第{attempt}次）：{err}")
                            continue

                        _job_event(job_id, "parse_ok", f"解析成功：{len(items)}条（第{attempt}次）", {"count": len(items), "attempt": attempt})

                        for it in items:
                            if len(collected) >= target_count:
                                break
                            if not isinstance(it, dict):
                                continue
                            content = _pick_first(it, ["question_content", "content", "stem", "question", "题干"])
                            if not content:
                                continue
                            content_key = re.sub(r"\s+", " ", content).strip()
                            if content_key in seen_contents:
                                continue
                            seen_contents.add(content_key)

                            answer = _pick_first(it, ["question_answer", "answer", "答案"])
                            analysis = _pick_first(it, ["question_analysis", "analysis", "解析"])
                            score_raw = _pick_first(it, ["question_score", "score", "分值"])
                            score_val = None
                            if score_raw is not None:
                                try:
                                    score_val = float(score_raw)
                                except Exception:
                                    score_val = None

                            collected.append(
                                {
                                    "question_content": content,
                                    "question_answer": answer,
                                    "question_analysis": analysis,
                                    "question_score": score_val,
                                }
                            )

                        _job_event(job_id, "rule_progress", f"已收集：{len(collected)}/{target_count}", {"collected": len(collected), "target": target_count})

                    if len(collected) < target_count:
                        _job_event(job_id, "rule_error", f"补齐失败：需要{target_count}，实际{len(collected)}（已重试{attempt}次）")
                        raise ValueError(f"生成题目不足：需要{target_count}，实际{len(collected)}")

                    now = datetime.now()
                    for it in collected:
                        data = {
                            "subject_id": subject_id,
                            "chapter_id": chapter_id,
                            "type_id": type_id,
                            "difficulty_id": difficulty_id,
                            "question_content": it.get("question_content"),
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

                    _job_update(job_id, {"inserted": inserted, "question_ids": created_ids})
                    _job_event(job_id, "progress", f"已入库：{inserted}题", {"inserted": inserted})
                    _job_event(job_id, "rule_end", "本规则完成")

            session.commit()
            _job_update(
                job_id,
                {
                    "status": "done",
                    "inserted": inserted,
                    "question_ids": created_ids,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            _job_event(job_id, "job_done", f"任务完成：新增{inserted}题", {"inserted": inserted})
        except Exception as err:
            session.rollback()
            _job_update(
                job_id,
                {
                    "status": "error",
                    "error": str(err),
                    "inserted": inserted,
                    "question_ids": created_ids,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            _job_event(job_id, "job_error", str(err))


@ai_bp.post("/generate-questions")
def generate_questions():
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id")
    # chapter_id = payload.get("chapter_id") # 旧逻辑
    chapter_ids = payload.get("chapter_ids") or []
    if payload.get("chapter_id"): # 兼容旧参数
        chapter_ids.append(payload.get("chapter_id"))
    
    create_user = payload.get("create_user") or "ai"
    
    # 支持 rules 列表模式
    rules = payload.get("rules")
    
    # 支持 chapter_weights 字典 {str(chapter_id): float(weight)}
    # weight 为百分比（如 30 表示 30%）或小数（0.3），这里统一按比例分配
    chapter_weights = payload.get("chapter_weights") or {}
    
    if not rules:
        # 兼容旧的单条模式
        type_id = payload.get("type_id")
        difficulty_id = payload.get("difficulty_id")
        count = payload.get("count")
        if type_id and difficulty_id and count:
            rules = [{"type_id": type_id, "difficulty_id": difficulty_id, "count": count}]
        else:
            return jsonify({"error": {"message": "缺少生成规则 (rules 或 type_id/difficulty_id/count)", "type": "BadRequest"}}), 400

    if not subject_id or not chapter_ids:
        return jsonify({"error": {"message": "subject_id 和 chapter_ids 必填", "type": "BadRequest"}}), 400

    # 验证 rules 并计算总数
    validated_rules = []
    total_count_needed = 0
    
    for r in rules:
        tid = r.get("type_id")
        did = r.get("difficulty_id")
        cnt = r.get("count")
        if not tid or not did or not cnt:
            continue # 忽略无效规则
        try:
            cnt = int(cnt)
            if cnt < 1 or cnt > 50:
                return jsonify({"error": {"message": f"数量范围 1-50 (type_id={tid})", "type": "BadRequest"}}), 400
            validated_rules.append({"type_id": tid, "difficulty_id": did, "count": cnt})
            total_count_needed += cnt
        except:
             return jsonify({"error": {"message": "count 格式错误", "type": "BadRequest"}}), 400
    
    if not validated_rules:
        return jsonify({"error": {"message": "有效生成规则为空", "type": "BadRequest"}}), 400

    # 计算每个章节的分配比例
    # 如果前端传了 chapter_weights，则优先使用；否则平均分配
    # chapter_weights 格式: {"1": 30, "2": 70}
    
    # 过滤出有效的 chapter_ids（必须在库里存在）
    # 但为了简单，先假设前端传的都是有效的
    
    final_chapter_dist = {} # {chapter_id: ratio}
    
    # 1. 整理权重输入
    weight_map = {}
    for cid in chapter_ids:
        w = chapter_weights.get(str(cid))
        if w is not None:
            try:
                weight_map[int(cid)] = float(w)
            except:
                pass
    
    # 2. 如果有权重输入，归一化；如果没有，平均分配
    if weight_map:
        total_weight = sum(weight_map.values())
        if total_weight > 0:
            for cid, w in weight_map.items():
                final_chapter_dist[cid] = w / total_weight
        else:
            # 权重全为0，回退到平均分配
            avg = 1.0 / len(chapter_ids)
            for cid in chapter_ids:
                final_chapter_dist[int(cid)] = avg
    else:
        avg = 1.0 / len(chapter_ids)
        for cid in chapter_ids:
            final_chapter_dist[int(cid)] = avg
            
    # 3. 补齐未设置权重的章节（如果部分设置了，未设置的默认为0？或者平均剩余？这里简化策略：
    # 如果 chapter_weights 不为空，则只生成权重 > 0 的章节；
    # 如果 chapter_weights 为空，则所有 chapter_ids 平均分配。
    # 上面的逻辑已经涵盖了。
    # 但要注意 chapter_ids 中可能包含 weight_map 中没有的 key
    if weight_map:
        # 确保 final_chapter_dist 包含了所有需要生成的章节
        # 这里策略是：如果有权重配置，则严格按照权重配置来，不在权重里的章节就不生成（或者权重为0）
        # 但前端传了 chapter_ids，我们应该以 chapter_ids 为准？
        # 混合策略：chapter_ids 是范围，chapter_weights 是分配。
        # 如果某个 id 在 chapter_ids 但不在 weights 里，且 weights 不为空，则视为 0？
        # 用户需求：“选择章节之后还需要输入每个章节的占比”，暗示是全覆盖的。
        pass

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "inserted": 0,
            "question_ids": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "seq": 0,
            "events": [],
        }

    app = current_app._get_current_object()
    _executor.submit(_run_generation_v2, app, job_id, int(subject_id), final_chapter_dist, validated_rules, create_user)
    return jsonify({"ok": True, "job_id": job_id, "queued": True})


def _run_generation_v2(app, job_id: str, subject_id: int, chapter_dist: dict[int, float], rules: list[dict], create_user: str):
    """
    新版生成逻辑：支持章节权重分配
    chapter_dist: {chapter_id: ratio}，ratio Sum 应该约为 1.0
    rules: [{"type_id": 1, "difficulty_id": 1, "count": 10}, ...]
    """
    with app.app_context():
        _job_update(job_id, {"status": "running", "started_at": datetime.now().isoformat(timespec="seconds")})
        _job_event(job_id, "job_start", "开始生成（按权重分配）")
        qb = _table("question_bank")
        ch = _table("textbook_chapter")
        session = get_session(current_app)
        inserted = 0
        created_ids: list[int] = []

        try:
            chapter_ids = list(chapter_dist.keys())
            stmt = select(ch.c.chapter_id, ch.c.chapter_name, ch.c.content, ch.c.parent_chapter_id, ch.c.textbook_id).where(ch.c.chapter_id.in_(chapter_ids))
            chapters_data = {r["chapter_id"]: dict(r) for r in session.execute(stmt).mappings().all()}
            
            if not chapters_data:
                _job_update(job_id, {"status": "error", "error": "所选章节不存在"})
                _job_event(job_id, "job_error", "所选章节不存在")
                return

            # --- 递归获取子章节内容 ---
            # 1. 找出涉及的教材ID
            textbook_ids = set(c["textbook_id"] for c in chapters_data.values() if c.get("textbook_id"))
            
            # 2. 获取这些教材的所有章节以构建层级关系
            all_chapters_map = {} # {chapter_id: row}
            children_map = {} # {parent_id: [child_id, ...]}
            
            if textbook_ids:
                all_ch_stmt = select(ch.c.chapter_id, ch.c.chapter_name, ch.c.parent_chapter_id, ch.c.content).where(ch.c.textbook_id.in_(textbook_ids))
                all_rows = session.execute(all_ch_stmt).mappings().all()
                for row in all_rows:
                    cid = row["chapter_id"]
                    pid = row["parent_chapter_id"]
                    all_chapters_map[cid] = row
                    if pid:
                        children_map.setdefault(pid, []).append(cid)
            
            def get_aggregated_content(root_id):
                contents = []
                # 根节点内容
                root_c = all_chapters_map.get(root_id, {}).get("content")
                if root_c:
                    contents.append(root_c)
                
                # 递归子节点
                stack = [root_id]
                seen = {root_id}
                while stack:
                    curr = stack.pop()
                    children = children_map.get(curr, [])
                    for child in children:
                        if child not in seen:
                            seen.add(child)
                            stack.append(child)
                            c = all_chapters_map.get(child, {}).get("content")
                            if c:
                                contents.append(c)
                return "\n".join(contents)
            # -----------------------

            # 对每条规则进行分配
            for rule_idx, rule in enumerate(rules):
                type_id = rule["type_id"]
                difficulty_id = rule["difficulty_id"]
                total_count = rule["count"]
                
                # 分配数量
                # 使用最大余额法或简单的四舍五入，保证总数一致
                # 这里简单处理：按比例计算，向下取整，剩余的加给占比最大的章节
                
                dist_counts = {} # {chapter_id: count}
                current_sum = 0
                sorted_chapters = sorted(chapter_dist.items(), key=lambda x: x[1], reverse=True)
                
                for cid, ratio in sorted_chapters:
                    c = int(total_count * ratio)
                    dist_counts[cid] = c
                    current_sum += c
                
                # 补齐余数
                remainder = total_count - current_sum
                if remainder > 0:
                    # 加给权重最高的
                    dist_counts[sorted_chapters[0][0]] += remainder
                
                # --- 新增逻辑：将分配给父章节的 count 分摊给所有叶子子章节 ---
                final_tasks = {} # {cid: count}
                
                def get_leaves(node_id):
                    children = children_map.get(node_id, [])
                    if not children:
                        return [node_id]
                    leaves = []
                    for child in children:
                        leaves.extend(get_leaves(child))
                    return leaves

                for cid, count in dist_counts.items():
                    if count <= 0:
                        continue
                    
                    leaves = get_leaves(cid)
                    # 过滤掉不在 all_chapters_map 里的（比如可能没查到）
                    leaves = [l for l in leaves if l in all_chapters_map]
                    
                    if not leaves:
                        # 只有自己
                        final_tasks[cid] = final_tasks.get(cid, 0) + count
                    else:
                        # 平均分配给叶子
                        avg = count // len(leaves)
                        rem = count % len(leaves)
                        for i, leaf in enumerate(leaves):
                            c = avg + (1 if i < rem else 0)
                            if c > 0:
                                final_tasks[leaf] = final_tasks.get(leaf, 0) + c
                
                dist_counts = final_tasks
                # --------------------------------------------------------

                _job_event(
                    job_id,
                    "rule_start",
                    f"规则{rule_idx+1}: 题型={type_id} 难度={difficulty_id} 总数={total_count}",
                    {"type_id": type_id, "difficulty_id": difficulty_id, "total_count": total_count}
                )

                # 逐个章节生成
                for cid, count in dist_counts.items():
                    if count <= 0:
                        continue
                        
                    chapter_info = all_chapters_map.get(cid)
                    if not chapter_info:
                        continue
                        
                    _job_event(job_id, "chapter_start", f"章节：{chapter_info.get('chapter_name')} (分配{count}题)", {"chapter_id": cid})
                    
                    # 复用核心生成逻辑 (call_model 等)
                    # 这里为了避免代码冗余，最好提取一个 _generate_for_single_chapter 函数
                    # 但考虑到 _run_generation 内部有很多闭包变量，暂时内联或者简单提取
                    
                    # --- 开始单章节生成逻辑 ---
                    sample_stmt = (
                        select(qb.c.question_id, qb.c.question_content, qb.c.question_answer, qb.c.question_analysis)
                        .where(and_(qb.c.chapter_id == cid, qb.c.review_status == 1, qb.c.type_id == type_id))
                        .order_by(qb.c.question_id.desc())
                        .limit(3)
                    )
                    sample = session.execute(sample_stmt).mappings().all()
                    source_ids = [str(s["question_id"]) for s in sample]

                    # summary = chapter_info.get("content") or ""
                    # summary = get_aggregated_content(cid)
                    # 修改为只使用当前章节（叶子节点）的内容，避免重复或混淆
                    summary = chapter_info.get("content") or ""
                    
                    system_prompt = "你是出题助理。你必须严格输出 JSON 数组，不要输出任何多余文本。"
                    user_prompt = (
                        "请为指定教材章节生成题目，要求：\n"
                        "1) 只生成与章节相关的题\n"
                        "2) 难度与题型遵循要求\n"
                        "3) 输出严格 JSON 数组，每个元素包含字段：question_content, question_answer, question_analysis, question_score\n"
                        "4) question_content 内可包含选项（如A/B/C/D），但仍是纯文本\n\n"
                        f"章节名称：{chapter_info['chapter_name']}\n"
                        f"章节概要：{summary if summary else '(暂无概要)'}\n"
                        f"目标数量：{count}\n"
                        f"题型ID：{type_id}\n"
                        f"难度ID：{difficulty_id}\n\n"
                        "参考题目（用于风格与覆盖点，不要重复）：\n"
                    )
                    for i, s in enumerate(sample, start=1):
                        user_prompt += (
                            f"\n{i}. 题干：{s.get('question_content')}\n"
                            f"   答案：{s.get('question_answer')}\n"
                            f"   解析：{s.get('question_analysis')}\n"
                        )

                    client = get_deepseek_client()
                    target_count = int(count)
                    collected: list[dict] = []
                    seen_contents: set[str] = set()
                    attempt = 0

                    def call_model(prompt: str, attempt_no: int, missing: int) -> str:
                        _job_event(
                            job_id,
                            "ai_start",
                            f"请求模型中…（第{attempt_no}次，缺{missing}题）",
                            {"chapter_id": cid, "type_id": type_id, "difficulty_id": difficulty_id, "attempt": attempt_no, "missing": missing},
                        )
                        try:
                            raw_chunks: list[str] = []
                            buf = ""
                            last_flush = time.time()
                            for chunk in client.chat_stream(system_prompt=system_prompt, user_prompt=prompt, temperature=0.7):
                                raw_chunks.append(chunk)
                                buf += chunk
                                now_ts = time.time()
                                if len(buf) >= 200 or "\n" in buf or (now_ts - last_flush) >= 0.8:
                                    _job_event(job_id, "ai_delta", data={"text": buf})
                                    buf = ""
                                    last_flush = now_ts
                            if buf:
                                _job_event(job_id, "ai_delta", data={"text": buf})
                            raw_text = "".join(raw_chunks)
                        except Exception as err:
                            _job_event(job_id, "ai_error", f"流式输出不可用，改用普通请求：{err}")
                            raw_text = client.chat(system_prompt=system_prompt, user_prompt=prompt, temperature=0.7)
                            _job_event(job_id, "ai_delta", data={"text": raw_text})
                        _job_event(job_id, "ai_end", "模型返回完成")
                        return raw_text

                    while len(collected) < target_count and attempt < MAX_FILL_ATTEMPTS:
                        attempt += 1
                        missing = target_count - len(collected)

                        prompt = user_prompt.replace(f"目标数量：{count}\n", f"目标数量：{missing}\n")
                        if attempt > 1:
                            existed = "\n".join([f"- {x['question_content']}" for x in collected[:50]])
                            prompt += (
                                "\n补齐要求：\n"
                                f"1) 你只需要补齐缺口：再生成 {missing} 道新题\n"
                                "2) 只输出 JSON 数组，不要输出 ```json 或任何解释文本\n"
                                "3) 绝对不要重复已有题干\n"
                                f"\n已生成题干（不要重复）：\n{existed}\n"
                            )

                        _job_event(job_id, "rule_retry", f"补齐生成：第{attempt}次（还差{missing}题）")
                        raw = call_model(prompt, attempt, missing)
                        try:
                            items = _extract_json_list(raw)
                        except Exception as err:
                            _job_event(job_id, "rule_warn", f"解析失败（第{attempt}次）：{err}")
                            continue

                        _job_event(job_id, "parse_ok", f"解析成功：{len(items)}条（第{attempt}次）", {"count": len(items), "attempt": attempt})

                        for it in items:
                            if len(collected) >= target_count:
                                break
                            if not isinstance(it, dict):
                                continue
                            content = _pick_first(it, ["question_content", "content", "stem", "question", "题干"])
                            if not content:
                                continue
                            content_key = re.sub(r"\s+", " ", content).strip()
                            if content_key in seen_contents:
                                continue
                            seen_contents.add(content_key)
                            
                            answer = _pick_first(it, ["question_answer", "answer", "答案"])
                            analysis = _pick_first(it, ["question_analysis", "analysis", "解析"])
                            score_raw = _pick_first(it, ["question_score", "score", "分值"])
                            score_val = None
                            if score_raw is not None:
                                try:
                                    score_val = float(score_raw)
                                except Exception:
                                    score_val = None

                            collected.append(
                                {
                                    "question_content": content,
                                    "question_answer": answer,
                                    "question_analysis": analysis,
                                    "question_score": score_val,
                                }
                            )

                        _job_event(job_id, "rule_progress", f"已收集：{len(collected)}/{target_count}", {"collected": len(collected), "target": target_count})

                    if len(collected) < target_count:
                        _job_event(job_id, "rule_error", f"补齐失败：需要{target_count}，实际{len(collected)}（已重试{attempt}次）")
                        # 不抛出异常，继续下一个章节
                    
                    now = datetime.now()
                    for it in collected:
                        data = {
                            "subject_id": subject_id,
                            "chapter_id": cid,
                            "type_id": type_id,
                            "difficulty_id": difficulty_id,
                            "question_content": it.get("question_content"),
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
                    
                    _job_update(job_id, {"inserted": inserted, "question_ids": created_ids})
                    _job_event(job_id, "progress", f"已入库：{inserted}题", {"inserted": inserted})
                    # --- 结束单章节生成逻辑 ---

            session.commit()
            _job_update(
                job_id,
                {
                    "status": "done",
                    "inserted": inserted,
                    "question_ids": created_ids,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            _job_event(job_id, "job_done", f"任务完成：新增{inserted}题", {"inserted": inserted})
        except Exception as err:
            session.rollback()
            _job_update(
                job_id,
                {
                    "status": "error",
                    "error": str(err),
                    "inserted": inserted,
                    "question_ids": created_ids,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            _job_event(job_id, "job_error", str(err))


@ai_bp.get("/jobs/<string:job_id>")
def get_job(job_id: str):
    snap = _job_snapshot(job_id)
    if not snap:
        return jsonify({"error": {"message": "任务不存在", "type": "NotFound"}}), 404
    return jsonify({"job": snap})


@ai_bp.get("/jobs/<string:job_id>/events")
def job_events(job_id: str):
    last_id = request.args.get("last_id", default=0, type=int)

    def gen():
        nonlocal last_id
        yield ": ok\n\n"
        while True:
            snap = _job_snapshot(job_id)
            if not snap:
                yield f"event: error\ndata: {json.dumps({'message': '任务不存在'}, ensure_ascii=False)}\n\n"
                break

            events: list[dict] = []
            with _jobs_lock:
                job = _jobs.get(job_id) or {}
                for e in job.get("events", []):
                    if int(e.get("id") or 0) > last_id:
                        events.append(e)

            for e in events:
                last_id = int(e.get("id") or last_id)
                payload = json.dumps(e, ensure_ascii=False)
                yield f"id: {last_id}\ndata: {payload}\n\n"

            if snap.get("status") in ["done", "error"] and not events:
                break

            time.sleep(0.5)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(gen()), headers=headers, mimetype="text/event-stream")


@ai_bp.get("/pending")
def list_pending():
    qb = _table("question_bank")
    ch = _table("textbook_chapter")
    sd = _table("subject_dict")
    qtd = _table("question_type_dict")
    qdd = _table("question_difficulty_dict")
    subject_id = request.args.get("subject_id", type=int)
    chapter_ids_str = request.args.get("chapter_id", type=str)
    page = max(1, request.args.get("page", default=1, type=int))
    page_size = min(100, max(1, request.args.get("page_size", default=20, type=int)))

    where = [qb.c.review_status == 0]
    if subject_id is not None:
        where.append(qb.c.subject_id == subject_id)
    if chapter_ids_str:
        try:
            c_ids = [int(x) for x in chapter_ids_str.split(",") if x.strip()]
            if c_ids:
                if len(c_ids) == 1:
                    where.append(qb.c.chapter_id == c_ids[0])
                else:
                    where.append(qb.c.chapter_id.in_(c_ids))
        except Exception:
            pass

    stmt_base = (
        select(
            qb.c.question_id,
            qb.c.subject_id,
            qb.c.chapter_id,
            qb.c.type_id,
            qb.c.difficulty_id,
            sd.c.subject_name.label("subject_name"),
            ch.c.chapter_name.label("chapter_name"),
            qtd.c.type_name.label("type_name"),
            qdd.c.difficulty_name.label("difficulty_name"),
            qb.c.question_content,
            qb.c.question_answer,
            qb.c.question_analysis,
            qb.c.question_score,
            qb.c.is_ai_generated,
            qb.c.source_question_ids,
            qb.c.create_user,
            qb.c.create_time,
        )
        .select_from(
            qb.outerjoin(ch, ch.c.chapter_id == qb.c.chapter_id)
            .outerjoin(sd, sd.c.subject_id == qb.c.subject_id)
            .outerjoin(qtd, qtd.c.type_id == qb.c.type_id)
            .outerjoin(qdd, qdd.c.difficulty_id == qb.c.difficulty_id)
        )
        .where(and_(*where))
    )
    
    stmt = (
        stmt_base
        .order_by(qb.c.question_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    try:
        # 使用不带分页的查询来计算总数
        count_query = select(func.count()).select_from(stmt_base.subquery())
        total = get_session(current_app).execute(count_query).scalar_one()
        
        rows = get_session(current_app).execute(stmt).mappings().all()
        return jsonify({"items": [dict(r) for r in rows], "page": page, "page_size": page_size, "total": total})
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


@ai_bp.post("/verify/batch")
def verify_batch():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    reviewer = payload.get("reviewer") or "reviewer"
    
    if action != "approve_all_pending":
        return jsonify({"error": {"message": "不支持的操作", "type": "BadRequest"}}), 400

    qb = _table("question_bank")
    now = datetime.now()
    
    # 批量更新所有 review_status=0 的题目为 1
    stmt = (
        update(qb)
        .where(qb.c.review_status == 0)
        .values(review_status=1, reviewer=reviewer, review_time=now)
    )
    
    try:
        session = get_session(current_app)
        res = session.execute(stmt)
        session.commit()
        return jsonify({"ok": True, "count": res.rowcount})
    except SQLAlchemyError as err:
        get_session(current_app).rollback()
        return jsonify({"error": {"message": str(err), "type": err.__class__.__name__}}), 500
