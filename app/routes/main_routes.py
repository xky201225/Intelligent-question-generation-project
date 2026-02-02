from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from app import db
from app.models.models import *
from app.services.ai_service import DeepSeekService
from app.services.file_service import FileService
from app.services.export_service import ExportService
import json

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    return render_template('index.html')

# --- Textbook Management ---
@bp.route('/textbooks', methods=['GET', 'POST'])
def textbooks():
    if request.method == 'POST':
        name = request.form.get('name')
        subject_id = request.form.get('subject_id')
        author = request.form.get('author')
        
        # Check if file is uploaded for auto-chapter recognition
        chapters_data = []
        file = request.files.get('file')
        if file and file.filename:
            path = FileService.save_file(file, 'textbooks')
            text = FileService.extract_text(path)
            # Use heuristic recognition initially
            chapters_data = FileService.heuristic_recognize_chapters(text)
        
        tb = Textbook(textbook_name=name, subject_id=subject_id, author=author)
        db.session.add(tb)
        db.session.commit()
        
        # Add recognized chapters
        for idx, ch in enumerate(chapters_data, 1):
            chapter = TextbookChapter(
                textbook_id=tb.textbook_id,
                chapter_name=ch['title'],
                chapter_level=1,
                chapter_sort=idx,
                chapter_content=ch.get('content', '') # Store content now
            )
            db.session.add(chapter)
            
        db.session.commit()
        return redirect(url_for('main.textbooks'))
        
    textbooks = Textbook.query.all()
    subjects = SubjectDict.query.all()
    return render_template('textbooks.html', textbooks=textbooks, subjects=subjects)

@bp.route('/textbooks/<int:id>/chapters', methods=['GET', 'POST'])
def chapters(id):
    textbook = Textbook.query.get_or_404(id)
    if request.method == 'POST':
        name = request.form.get('name')
        level = request.form.get('level', 1)
        parent_id = request.form.get('parent_id', 0)
        file = request.files.get('file')
        chapter_content = ''
        if file and file.filename:
            path = FileService.save_file(file, 'chapters')
            extracted = FileService.extract_text(path)
            chapter_content = extracted or ''
        
        chapter = TextbookChapter(
            textbook_id=id,
            chapter_name=name,
            chapter_level=level,
            parent_chapter_id=parent_id,
            chapter_content=chapter_content
        )
        db.session.add(chapter)
        db.session.commit()
        return redirect(url_for('main.chapters', id=id))
        
    chapters = TextbookChapter.query.filter_by(textbook_id=id).all()
    return render_template('chapters.html', textbook=textbook, chapters=chapters)

@bp.route('/api/textbooks/<int:textbook_id>/chapters', methods=['GET'])
def api_textbook_chapters(textbook_id):
    chapters = TextbookChapter.query.filter_by(textbook_id=textbook_id).order_by(TextbookChapter.chapter_sort.asc(), TextbookChapter.chapter_id.asc()).all()
    return jsonify([
        {
            'chapter_id': c.chapter_id,
            'chapter_name': c.chapter_name,
            'chapter_level': c.chapter_level,
            'parent_chapter_id': c.parent_chapter_id
        } for c in chapters
    ])

# --- Question Bank ---
@bp.route('/questions')
def questions():
    # Advanced filtering
    subject_id = request.args.get('subject_id', type=int)
    textbook_id = request.args.get('textbook_id', type=int)
    chapter_id = request.args.get('chapter_id', type=int)
    type_id = request.args.get('type_id', type=int)
    difficulty_id = request.args.get('difficulty_id', type=int)
    keyword = (request.args.get('keyword') or '').strip()
    tags = (request.args.get('tags') or '').strip()
    knowledge_part = (request.args.get('knowledge_part') or '').strip()
    is_ai = request.args.get('is_ai')
    status = request.args.get('status', type=int)
    score_min = request.args.get('score_min', type=float)
    score_max = request.args.get('score_max', type=float)

    # default: published only
    if status is None:
        status = 1

    query = QuestionBank.query
    if status in (0, 1):
        query = query.filter(QuestionBank.status == status)
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        query = query.filter(QuestionBank.type_id == type_id)
    if difficulty_id:
        query = query.filter(QuestionBank.difficulty_id == difficulty_id)
    if chapter_id:
        query = query.filter(QuestionBank.chapter_id == chapter_id)
    if textbook_id:
        query = query.join(TextbookChapter, QuestionBank.chapter_id == TextbookChapter.chapter_id)\
                     .filter(TextbookChapter.textbook_id == textbook_id)
    if keyword:
        query = query.filter(QuestionBank.question_content.like(f"%{keyword}%"))
    if tags:
        query = query.filter(QuestionBank.question_tags.like(f"%{tags}%"))
    if knowledge_part:
        query = query.filter(QuestionBank.knowledge_part.like(f"%{knowledge_part}%"))
    if is_ai in ('0', '1'):
        query = query.filter(QuestionBank.is_ai_generated == int(is_ai))
    if score_min is not None:
        query = query.filter(QuestionBank.question_score >= score_min)
    if score_max is not None:
        query = query.filter(QuestionBank.question_score <= score_max)
        
    questions = query.order_by(QuestionBank.create_time.desc()).all()
    
    # Context data for filters
    subjects = SubjectDict.query.all()
    types = QuestionTypeDict.query.all()
    difficulties = QuestionDifficultyDict.query.all()
    textbooks = Textbook.query.all()
    
    return render_template('questions.html', questions=questions, 
                           subjects=subjects, types=types, difficulties=difficulties, textbooks=textbooks)

@bp.route('/questions/upload', methods=['GET', 'POST'])
def upload_questions():
    """
    Upload a doc/pdf/txt, parse questions heuristically, store as pending (status=0).
    """
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('请先选择要上传的文件', 'warning')
            return redirect(url_for('main.upload_questions'))

        path = FileService.save_file(file, 'question_uploads')
        text = FileService.extract_text(path)
        if not text:
            flash('文件解析失败，请尝试换一个文件或格式', 'danger')
            return redirect(url_for('main.upload_questions'))

        parsed = FileService.heuristic_parse_questions(text)
        if not parsed:
            flash('未识别到题目，请检查文件内容格式（建议使用编号题目）', 'warning')
            return redirect(url_for('main.upload_questions'))

        # Defaults: user will correct during pending review
        default_subject_id = int(request.form.get('subject_id') or 1)
        default_chapter_id = int(request.form.get('chapter_id') or 1)
        default_type_id = int(request.form.get('type_id') or 1)
        default_difficulty_id = int(request.form.get('difficulty_id') or 1)
        default_score = float(request.form.get('score') or 5)
        create_user = request.form.get('create_user') or ''

        for item in parsed:
            q = QuestionBank(
                subject_id=default_subject_id,
                chapter_id=default_chapter_id,
                type_id=default_type_id,
                difficulty_id=default_difficulty_id,
                question_content=item.get('content', ''),
                question_answer=item.get('answer', '') or '',
                question_analysis=item.get('analysis', '') or '',
                question_score=default_score,
                is_ai_generated=0,
                status=0,
                create_user=create_user
            )
            db.session.add(q)

        db.session.commit()
        flash(f'上传成功：识别到 {len(parsed)} 道题目，已进入“待校验”', 'success')
        return redirect(url_for('main.pending_questions'))

    subjects = SubjectDict.query.all()
    types = QuestionTypeDict.query.all()
    difficulties = QuestionDifficultyDict.query.all()
    textbooks = Textbook.query.all()
    return render_template(
        'upload_questions.html',
        subjects=subjects,
        types=types,
        difficulties=difficulties,
        textbooks=textbooks
    )

@bp.route('/questions/pending')
def pending_questions():
    questions = QuestionBank.query.filter_by(status=0).order_by(QuestionBank.create_time.desc()).all()
    return render_template('review_questions.html', questions=[
        {
            'question_id': q.question_id,
            'content': q.question_content,
            'options_json': q.question_options,
            'answer': q.question_answer,
            'analysis': q.question_analysis,
            'knowledge_part': q.knowledge_part,
            'tags': q.question_tags,
            'score': q.question_score,
            'subject_id': q.subject_id,
            'chapter_id': q.chapter_id,
            'type_id': q.type_id,
            'difficulty_id': q.difficulty_id
        } for q in questions
    ], is_db_review=True) # Special flag for template to handle DB objects vs JSON objects if needed

@bp.route('/questions/generate', methods=['GET', 'POST'])
def generate_questions():
    if request.method == 'POST':
        mode = request.form.get('mode')
        generated_data = []
        
        if mode == 'chapter':
            # Collect advanced parameters
            chapter_id = request.form.get('chapter_id')
            count = int(request.form.get('count', 5))
            total_score = int(request.form.get('total_score', 100))
            description = request.form.get('description', '')
            tags_keywords = (request.form.get('tags_keywords') or '').strip()
            
            # Knowledge Points (parsed from form, simplified for now)
            knowledge = [{"name": "综合知识", "percentage": 100}] 
            
            # Difficulty
            diff_level = request.form.get('difficulty') 
            difficulty = {diff_level: 100} if diff_level else {"中等": 100}
            
            # Types
            # Support custom type names + counts (JSON array) OR single select fallback
            question_types = []
            types_json = request.form.get('question_types_json', '').strip()
            if types_json:
                try:
                    parsed = json.loads(types_json)
                    # normalize: [{name,count}] -> [{name,percentage}]
                    total_count = sum(int(x.get('count', 0)) for x in parsed if x.get('name'))
                    if total_count > 0:
                        question_types = [
                            {"name": x.get('name'), "percentage": round(int(x.get('count', 0)) * 100 / total_count)}
                            for x in parsed if x.get('name')
                        ]
                        count = total_count
                except Exception:
                    question_types = []
            if not question_types:
                q_type = request.form.get('type')
                question_types = [{"name": q_type, "percentage": 100}] if q_type else [{"name": "选择题", "percentage": 100}]
            
            # Get Context
            chapter_text = ""
            chapter = None
            if chapter_id:
                chapter = TextbookChapter.query.get(chapter_id)
                if chapter and chapter.chapter_content:
                    chapter_text = chapter.chapter_content
                else:
                    chapter_text = "No content available for this chapter."
            
            generated_data = DeepSeekService.generate_questions_advanced(
                subject=chapter.textbook.subject.subject_name if chapter else "General",
                knowledge=knowledge,
                difficulty=difficulty,
                count=count,
                question_types=question_types,
                total_score=total_score,
                description=description,
                chapter_context=chapter_text,
                tags_keywords=tags_keywords
            )
            
        elif mode == 'similar':
            q_id = request.form.get('question_id')
            original = QuestionBank.query.get(q_id)
            if original:
                generated_data = DeepSeekService.generate_questions_advanced(
                    subject=original.subject.subject_name,
                    knowledge=[{"name": "相关知识点", "percentage": 100}],
                    difficulty={original.difficulty.difficulty_name: 100},
                    count=1,
                    question_types=[{"name": original.type.type_name, "percentage": 100}],
                    total_score=original.question_score,
                    description="生成相似题目",
                    chapter_context=original.question_content
                )

        return render_template('review_questions.html', questions=generated_data)
        
    subjects = SubjectDict.query.all()
    textbooks = Textbook.query.all()
    return render_template('generate.html', subjects=subjects, textbooks=textbooks)

@bp.route('/questions/save_generated', methods=['POST'])
def save_generated():
    data = request.json
    for item in data:
        q_id = item.get('question_id')
        # If this is a pending DB question, update it and publish.
        if q_id:
            q = QuestionBank.query.get(q_id)
            if not q:
                continue
            q.subject_id = item.get('subject_id', q.subject_id)
            q.chapter_id = item.get('chapter_id', q.chapter_id)
            q.type_id = item.get('type_id', q.type_id)
            q.difficulty_id = item.get('difficulty_id', q.difficulty_id)
            q.question_content = item.get('content', q.question_content)
            q.question_options = item.get('options_json', q.question_options)
            q.question_answer = item.get('answer', q.question_answer)
            q.question_analysis = item.get('analysis', q.question_analysis)
            q.knowledge_part = item.get('knowledge_part', q.knowledge_part)
            q.question_tags = item.get('tags', q.question_tags)
            q.question_score = item.get('score', q.question_score)
            q.status = 1
            continue

        # Otherwise treat as new AI output and store as pending first.
        content = item.get('stem') or item.get('content') or ''
        options_obj = item.get('options') or {}
        options_json = ''
        if isinstance(options_obj, dict) and options_obj:
            options_json = json.dumps(options_obj, ensure_ascii=False)

        q = QuestionBank(
            subject_id=item.get('subject_id', 1),
            chapter_id=item.get('chapter_id', 1),
            type_id=item.get('type_id', 1),
            difficulty_id=item.get('difficulty_id', 1),
            question_content=content,
            question_options=options_json,
            question_answer=item.get('answer', ''),
            question_analysis=item.get('answer_content') or item.get('analysis', ''),
            knowledge_part=item.get('knowledge_part', '') or '',
            question_tags=",".join(item.get('tags', [])) if isinstance(item.get('tags'), list) else (item.get('tags') or ''),
            question_score=item.get('score', 5),
            is_ai_generated=1,
            status=0  # pending validation; publish after explicit approval
        )
        db.session.add(q)
    db.session.commit()
    return jsonify({'status': 'success'})

@bp.route('/questions/pending/reject', methods=['POST'])
def reject_pending_questions():
    """
    Reject (delete) pending questions by IDs.
    """
    payload = request.json or {}
    ids = payload.get('question_ids') or []
    if not isinstance(ids, list) or not ids:
        return jsonify({'status': 'error', 'message': 'question_ids required'}), 400

    QuestionBank.query.filter(QuestionBank.question_id.in_(ids), QuestionBank.status == 0).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'status': 'success'})

# --- Paper Assembly ---
@bp.route('/paper/create', methods=['GET', 'POST'])
def create_paper():
    if request.method == 'POST':
        name = request.form.get('paper_name')
        subject_id = request.form.get('subject_id')
        creator = request.form.get('creator')
        question_ids = request.form.getlist('questions')
        
        total_score = 0
        paper = ExamPaper(paper_name=name, subject_id=subject_id, creator=creator, total_score=0)
        db.session.add(paper)
        db.session.commit()
        
        for idx, q_id in enumerate(question_ids, 1):
            q = QuestionBank.query.get(q_id)
            if q:
                # allow per-question score override
                custom_score = request.form.get(f"score_{q_id}")
                try:
                    score_value = float(custom_score) if custom_score is not None and custom_score != '' else float(q.question_score)
                except Exception:
                    score_value = float(q.question_score)
                rel = PaperQuestionRelation(
                    paper_id=paper.paper_id,
                    question_id=q_id,
                    question_sort=idx,
                    question_score=score_value
                )
                total_score += float(score_value)
                db.session.add(rel)
        
        paper.total_score = total_score
        db.session.commit()
        return redirect(url_for('main.preview_paper', id=paper.paper_id))
        
    # GET: filter questions for paper basket
    subject_id = request.args.get('subject_id', type=int)
    textbook_id = request.args.get('textbook_id', type=int)
    chapter_id = request.args.get('chapter_id', type=int)
    type_id = request.args.get('type_id', type=int)
    difficulty_id = request.args.get('difficulty_id', type=int)
    keyword = (request.args.get('keyword') or '').strip()
    tags = (request.args.get('tags') or '').strip()
    knowledge_part = (request.args.get('knowledge_part') or '').strip()
    score_min = request.args.get('score_min', type=float)
    score_max = request.args.get('score_max', type=float)

    query = QuestionBank.query.filter(QuestionBank.status == 1)
    if subject_id:
        query = query.filter(QuestionBank.subject_id == subject_id)
    if type_id:
        query = query.filter(QuestionBank.type_id == type_id)
    if difficulty_id:
        query = query.filter(QuestionBank.difficulty_id == difficulty_id)
    if chapter_id:
        query = query.filter(QuestionBank.chapter_id == chapter_id)
    if textbook_id:
        query = query.join(TextbookChapter, QuestionBank.chapter_id == TextbookChapter.chapter_id)\
                     .filter(TextbookChapter.textbook_id == textbook_id)
    if keyword:
        query = query.filter(QuestionBank.question_content.like(f"%{keyword}%"))
    if tags:
        query = query.filter(QuestionBank.question_tags.like(f"%{tags}%"))
    if knowledge_part:
        query = query.filter(QuestionBank.knowledge_part.like(f"%{knowledge_part}%"))
    if score_min is not None:
        query = query.filter(QuestionBank.question_score >= score_min)
    if score_max is not None:
        query = query.filter(QuestionBank.question_score <= score_max)

    questions = query.order_by(QuestionBank.create_time.desc()).all()
    subjects = SubjectDict.query.all()
    types = QuestionTypeDict.query.all()
    difficulties = QuestionDifficultyDict.query.all()
    textbooks = Textbook.query.all()
    return render_template(
        'create_paper.html',
        questions=questions,
        subjects=subjects,
        types=types,
        difficulties=difficulties,
        textbooks=textbooks
    )

@bp.route('/paper/<int:id>/preview')
def preview_paper(id):
    paper = ExamPaper.query.get_or_404(id)
    relations = PaperQuestionRelation.query.filter_by(paper_id=id).order_by(PaperQuestionRelation.question_sort).all()
    questions = []
    for rel in relations:
        q = QuestionBank.query.get(rel.question_id)
        questions.append({
            'content': q.question_content,
            'score': rel.question_score,
            'answer': q.question_answer,
            'analysis': q.question_analysis
        })
    return render_template('preview_paper.html', paper=paper, questions=questions)

@bp.route('/paper/<int:id>/export/<format>')
def export_paper(id, format):
    paper = ExamPaper.query.get_or_404(id)
    relations = PaperQuestionRelation.query.filter_by(paper_id=id).order_by(PaperQuestionRelation.question_sort).all()
    
    questions = []
    for rel in relations:
        q = QuestionBank.query.get(rel.question_id)
        questions.append({
            'content': q.question_content,
            'score': rel.question_score,
            'answer': q.question_answer,
            'analysis': q.question_analysis
        })
    
    paper_data = {
        'paper_name': paper.paper_name,
        'subject_name': paper.subject.subject_name,
        'total_score': paper.total_score,
        'creator': paper.creator
    }
    
    with_answers = request.args.get('with_answers') == '1'
    
    if format == 'word':
        path = ExportService.export_to_word(paper_data, questions, with_answers)
    else:
        path = ExportService.export_to_pdf(paper_data, questions, with_answers)
        
    return send_file(path, as_attachment=True)

# --- Paper Upload -> AI Generate -> Save ---
@bp.route('/paper/upload', methods=['GET', 'POST'])
def upload_paper_generate():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('请先选择要上传的试卷文件', 'warning')
            return redirect(url_for('main.upload_paper_generate'))

        paper_name = request.form.get('paper_name') or 'AI生成试卷'
        subject_id = int(request.form.get('subject_id') or 1)
        creator = request.form.get('creator') or 'AI'
        total_score = int(request.form.get('total_score') or 100)
        diff_level = request.form.get('difficulty') or '中等'
        difficulty = {diff_level: 100}

        types_json = (request.form.get('question_types_json') or '').strip()
        question_types = []
        question_count = int(request.form.get('count') or 5)
        if types_json:
            try:
                parsed = json.loads(types_json)
                total_count = sum(int(x.get('count', 0)) for x in parsed if x.get('name'))
                if total_count > 0:
                    question_types = [
                        {"name": x.get('name'), "percentage": round(int(x.get('count', 0)) * 100 / total_count)}
                        for x in parsed if x.get('name')
                    ]
                    question_count = total_count
            except Exception:
                question_types = []
        if not question_types:
            question_types = [{"name": "选择题", "percentage": 100}]

        path = FileService.save_file(file, 'paper_uploads')
        text = FileService.extract_text(path)
        if not text:
            flash('文件解析失败，请尝试换一个文件或格式', 'danger')
            return redirect(url_for('main.upload_paper_generate'))

        subject = SubjectDict.query.get(subject_id).subject_name if SubjectDict.query.get(subject_id) else "General"
        knowledge = [{"name": "覆盖原试卷知识点", "percentage": 100}]

        generated = DeepSeekService.generate_questions_from_text_content(
            document_text=text,
            question_count=question_count,
            total_score=total_score,
            subject=subject,
            knowledge=knowledge,
            difficulty=difficulty,
            question_types=question_types
        )

        paper_meta = {
            'paper_name': paper_name,
            'subject_id': subject_id,
            'creator': creator,
            'total_score': total_score
        }
        return render_template('review_questions.html', questions=generated, paper_mode=True, paper_meta=paper_meta)

    subjects = SubjectDict.query.all()
    return render_template('upload_paper.html', subjects=subjects)

@bp.route('/paper/save_generated', methods=['POST'])
def save_generated_paper():
    payload = request.json or {}
    paper_meta = payload.get('paper_meta') or {}
    questions = payload.get('questions') or []

    paper_name = paper_meta.get('paper_name') or 'AI生成试卷'
    subject_id = int(paper_meta.get('subject_id') or 1)
    creator = paper_meta.get('creator') or 'AI'

    # Save questions (published) and create paper relations
    paper = ExamPaper(paper_name=paper_name, subject_id=subject_id, creator=creator, total_score=0)
    db.session.add(paper)
    db.session.commit()

    total_score = 0.0
    default_chapter_id = int(paper_meta.get('chapter_id') or 1)
    default_type_id = int(paper_meta.get('type_id') or 1)
    default_difficulty_id = int(paper_meta.get('difficulty_id') or 1)

    for idx, item in enumerate(questions, 1):
        content = item.get('content') or item.get('stem') or ''
        options_obj = item.get('options') or {}
        options_json = ''
        if isinstance(options_obj, dict) and options_obj:
            options_json = json.dumps(options_obj, ensure_ascii=False)
        score = float(item.get('score') or 5)

        q = QuestionBank(
            subject_id=subject_id,
            chapter_id=int(item.get('chapter_id') or default_chapter_id),
            type_id=int(item.get('type_id') or default_type_id),
            difficulty_id=int(item.get('difficulty_id') or default_difficulty_id),
            question_content=content,
            question_options=options_json,
            question_answer=item.get('answer', '') or '',
            question_analysis=item.get('analysis') or item.get('answer_content') or '',
            knowledge_part=item.get('knowledge_part') or '',
            question_tags=",".join(item.get('tags', [])) if isinstance(item.get('tags'), list) else (item.get('tags') or ''),
            question_score=score,
            is_ai_generated=1,
            status=1,
            create_user=creator
        )
        db.session.add(q)
        db.session.flush()  # get q.question_id

        rel = PaperQuestionRelation(
            paper_id=paper.paper_id,
            question_id=q.question_id,
            question_sort=idx,
            question_score=score
        )
        db.session.add(rel)
        total_score += score

    paper.total_score = total_score
    db.session.commit()
    return jsonify({'status': 'success', 'paper_id': paper.paper_id})

# --- Answer Sheet ---
@bp.route('/paper/<int:paper_id>/answer_sheet/create', methods=['GET', 'POST'])
def create_answer_sheet(paper_id):
    paper = ExamPaper.query.get_or_404(paper_id)
    
    if request.method == 'POST':
        sheet_name = request.form.get('sheet_name', f"{paper.paper_name}-答题卡")
        
        # Create Sheet
        sheet = ExamAnswerSheet(
            paper_id=paper.paper_id,
            sheet_name=sheet_name,
            template_config=json.dumps({'layout': 'A4', 'columns': 2}), # Default config
            create_user=paper.creator
        )
        db.session.add(sheet)
        db.session.commit()
        
        # Create Relations (Auto-map default styles)
        relations = PaperQuestionRelation.query.filter_by(paper_id=paper_id).order_by(PaperQuestionRelation.question_sort).all()
        for idx, rel in enumerate(relations, 1):
            q = QuestionBank.query.get(rel.question_id)
            # Find default style for this question type
            default_style = AnswerAreaStyle.query.filter_by(type_id=q.type_id, is_default=1).first()
            if not default_style:
                # Fallback if no default style
                default_style = AnswerAreaStyle.query.filter_by(type_id=q.type_id).first()
            
            if default_style:
                sheet_rel = SheetQuestionRelation(
                    sheet_id=sheet.sheet_id,
                    question_id=q.question_id,
                    style_id=default_style.style_id,
                    area_sort=idx
                )
                db.session.add(sheet_rel)
                
        db.session.commit()
        return redirect(url_for('main.preview_answer_sheet', sheet_id=sheet.sheet_id))
        
    # Check if exists
    existing_sheet = ExamAnswerSheet.query.filter_by(paper_id=paper_id).first()
    if existing_sheet:
        return redirect(url_for('main.preview_answer_sheet', sheet_id=existing_sheet.sheet_id))
        
    return render_template('create_answer_sheet.html', paper=paper)

@bp.route('/answer_sheet/<int:sheet_id>/preview')
def preview_answer_sheet(sheet_id):
    sheet = ExamAnswerSheet.query.get_or_404(sheet_id)
    relations = SheetQuestionRelation.query.filter_by(sheet_id=sheet_id).order_by(SheetQuestionRelation.area_sort).all()
    
    areas = []
    for rel in relations:
        q = QuestionBank.query.get(rel.question_id)
        style = AnswerAreaStyle.query.get(rel.style_id)
        areas.append({
            'sort': rel.area_sort,
            'question_score': q.question_score, # Ideally get from paper relation, but simplified here
            'style_name': style.style_name,
            'config': json.loads(style.style_config)
        })
        
    return render_template('preview_answer_sheet.html', sheet=sheet, areas=areas)
