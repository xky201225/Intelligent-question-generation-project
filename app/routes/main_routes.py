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
        
        chapter = TextbookChapter(textbook_id=id, chapter_name=name, chapter_level=level, parent_chapter_id=parent_id)
        db.session.add(chapter)
        db.session.commit()
        return redirect(url_for('main.chapters', id=id))
        
    chapters = TextbookChapter.query.filter_by(textbook_id=id).all()
    return render_template('chapters.html', textbook=textbook, chapters=chapters)

# --- Question Bank ---
@bp.route('/questions')
def questions():
    # Basic filtering
    subject_id = request.args.get('subject_id')
    type_id = request.args.get('type_id')
    difficulty_id = request.args.get('difficulty_id')
    
    query = QuestionBank.query.filter_by(status=1) # Only show active/published questions
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if type_id:
        query = query.filter_by(type_id=type_id)
    if difficulty_id:
        query = query.filter_by(difficulty_id=difficulty_id)
        
    questions = query.order_by(QuestionBank.create_time.desc()).all()
    
    # Context data for filters
    subjects = SubjectDict.query.all()
    types = QuestionTypeDict.query.all()
    difficulties = QuestionDifficultyDict.query.all()
    
    return render_template('questions.html', questions=questions, 
                           subjects=subjects, types=types, difficulties=difficulties)

@bp.route('/questions/pending')
def pending_questions():
    questions = QuestionBank.query.filter_by(status=0).order_by(QuestionBank.create_time.desc()).all()
    return render_template('review_questions.html', questions=[
        {
            'question_id': q.question_id,
            'content': q.question_content,
            'answer': q.question_answer,
            'analysis': q.question_analysis,
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
            
            # Knowledge Points (parsed from form, simplified for now)
            knowledge = [{"name": "综合知识", "percentage": 100}] 
            
            # Difficulty
            diff_level = request.form.get('difficulty') 
            difficulty = {diff_level: 100} if diff_level else {"中等": 100}
            
            # Types
            q_type = request.form.get('type')
            question_types = [{"name": q_type, "percentage": 100}] if q_type else [{"name": "选择题", "percentage": 100}]
            
            # Get Context
            chapter_text = ""
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
                chapter_context=chapter_text
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
            q.question_answer = item.get('answer', q.question_answer)
            q.question_analysis = item.get('analysis', q.question_analysis)
            q.question_score = item.get('score', q.question_score)
            q.status = 1
            continue

        # Otherwise treat as new AI output and store as pending first.
        content = item.get('stem') or item.get('content') or ''
        if item.get('options'):
            content = f"{content}\n选项: {json.dumps(item['options'], ensure_ascii=False)}"

        q = QuestionBank(
            subject_id=item.get('subject_id', 1),
            chapter_id=item.get('chapter_id', 1),
            type_id=item.get('type_id', 1),
            difficulty_id=item.get('difficulty_id', 1),
            question_content=content,
            question_answer=item.get('answer', ''),
            question_analysis=item.get('answer_content') or item.get('analysis', ''),
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
                rel = PaperQuestionRelation(
                    paper_id=paper.paper_id,
                    question_id=q_id,
                    question_sort=idx,
                    question_score=q.question_score
                )
                total_score += float(q.question_score)
                db.session.add(rel)
        
        paper.total_score = total_score
        db.session.commit()
        return redirect(url_for('main.preview_paper', id=paper.paper_id))
        
    questions = QuestionBank.query.filter_by(status=1).all()
    subjects = SubjectDict.query.all()
    return render_template('create_paper.html', questions=questions, subjects=subjects)

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
