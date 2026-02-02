from app import db
from datetime import datetime

class SubjectDict(db.Model):
    __tablename__ = 'subject_dict'
    
    subject_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='科目唯一标识')
    subject_name = db.Column(db.String(50), nullable=False, unique=True, comment='科目名称')
    subject_code = db.Column(db.String(20), nullable=False, unique=True, comment='科目编码')
    subject_credit = db.Column(db.Numeric(3, 1), default=0.0, comment='科目学分')
    class_hours = db.Column(db.Integer, default=0, comment='总课量')
    theory_hours = db.Column(db.Integer, default=0, comment='理论课学时')
    practice_hours = db.Column(db.Integer, default=0, comment='实践课学时')
    target_grade = db.Column(db.String(20), default='', comment='面向年级')
    start_semester = db.Column(db.Integer, default=1, comment='开课学期')
    teach_type = db.Column(db.String(20), default='', comment='授课类型')
    teacher = db.Column(db.String(50), default='', comment='授课老师')
    subject_desc = db.Column(db.Text, default='', comment='科目简介')
    is_enable = db.Column(db.Integer, default=1, comment='启用状态')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

class QuestionTypeDict(db.Model):
    __tablename__ = 'question_type_dict'
    
    type_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='题目类型唯一标识')
    type_name = db.Column(db.String(30), nullable=False, unique=True, comment='题目类型名称')
    type_code = db.Column(db.String(20), nullable=False, unique=True, comment='题目类型编码')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

class QuestionDifficultyDict(db.Model):
    __tablename__ = 'question_difficulty_dict'
    
    difficulty_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='难度唯一标识')
    difficulty_name = db.Column(db.String(20), nullable=False, unique=True, comment='难度名称')
    difficulty_level = db.Column(db.Integer, nullable=False, unique=True, comment='难度等级')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')

class Textbook(db.Model):
    __tablename__ = 'textbook'
    
    textbook_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='教材唯一标识')
    subject_id = db.Column(db.Integer, db.ForeignKey('subject_dict.subject_id'), nullable=False, comment='关联科目ID')
    textbook_name = db.Column(db.String(100), nullable=False, comment='教材名称')
    author = db.Column(db.String(100), nullable=False, comment='教材作者/主编')
    publisher = db.Column(db.String(50), default='', comment='出版社')
    edition = db.Column(db.String(20), default='', comment='教材版本')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    subject = db.relationship('SubjectDict', backref=db.backref('textbooks', lazy=True))

class TextbookChapter(db.Model):
    __tablename__ = 'textbook_chapter'
    
    chapter_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='章节唯一标识')
    textbook_id = db.Column(db.Integer, db.ForeignKey('textbook.textbook_id', ondelete='CASCADE'), nullable=False, comment='关联教材ID')
    chapter_name = db.Column(db.String(100), nullable=False, comment='章节名称')
    chapter_level = db.Column(db.Integer, nullable=False, comment='章节层级')
    parent_chapter_id = db.Column(db.Integer, default=0, comment='父章节ID')
    chapter_sort = db.Column(db.Integer, default=0, nullable=False, comment='章节排序号')
    chapter_content = db.Column(db.Text, default='', comment='章节内容')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    textbook = db.relationship('Textbook', backref=db.backref('chapters', lazy=True))

class QuestionBank(db.Model):
    __tablename__ = 'question_bank'
    
    question_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='题目唯一标识')
    subject_id = db.Column(db.Integer, db.ForeignKey('subject_dict.subject_id'), nullable=False, comment='关联科目ID')
    chapter_id = db.Column(db.Integer, db.ForeignKey('textbook_chapter.chapter_id'), nullable=False, comment='关联章节ID')
    type_id = db.Column(db.Integer, db.ForeignKey('question_type_dict.type_id'), nullable=False, comment='关联题目类型ID')
    difficulty_id = db.Column(db.Integer, db.ForeignKey('question_difficulty_dict.difficulty_id'), nullable=False, comment='关联难度ID')
    question_content = db.Column(db.Text, nullable=False, comment='题目内容')
    question_options = db.Column(db.Text, default='', comment='题目选项JSON（选择题等）')
    question_answer = db.Column(db.Text, nullable=False, comment='题目答案')
    question_analysis = db.Column(db.Text, default='', comment='题目解析')
    knowledge_part = db.Column(db.String(200), default='', comment='所属知识点/章节小点')
    question_tags = db.Column(db.String(500), default='', comment='题目标签（逗号分隔）')
    question_score = db.Column(db.Numeric(5, 1), nullable=False, comment='题目分数')
    is_ai_generated = db.Column(db.Integer, default=0, nullable=False, comment='是否AI生成')
    source_question_ids = db.Column(db.String(500), default='', comment='AI生成来源题目ID')
    status = db.Column(db.Integer, default=1, comment='状态: 0待校验, 1已发布')
    create_user = db.Column(db.String(50), default='', comment='创建人')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    subject = db.relationship('SubjectDict', backref=db.backref('questions', lazy=True))
    chapter = db.relationship('TextbookChapter', backref=db.backref('questions', lazy=True))
    type = db.relationship('QuestionTypeDict', backref=db.backref('questions', lazy=True))
    difficulty = db.relationship('QuestionDifficultyDict', backref=db.backref('questions', lazy=True))

class ExamPaper(db.Model):
    __tablename__ = 'exam_paper'
    
    paper_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='试卷唯一标识')
    paper_name = db.Column(db.String(200), nullable=False, comment='试卷名称')
    subject_id = db.Column(db.Integer, db.ForeignKey('subject_dict.subject_id'), nullable=False, comment='关联科目ID')
    total_score = db.Column(db.Numeric(6, 1), nullable=False, comment='试卷总分')
    creator = db.Column(db.String(50), nullable=False, comment='组卷人')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='组卷时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    paper_desc = db.Column(db.Text, default='', comment='试卷描述')
    
    subject = db.relationship('SubjectDict', backref=db.backref('papers', lazy=True))

class PaperQuestionRelation(db.Model):
    __tablename__ = 'paper_question_relation'
    
    relation_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='关联记录唯一标识')
    paper_id = db.Column(db.BigInteger, db.ForeignKey('exam_paper.paper_id', ondelete='CASCADE'), nullable=False, comment='关联试卷ID')
    question_id = db.Column(db.BigInteger, db.ForeignKey('question_bank.question_id', ondelete='CASCADE'), nullable=False, comment='关联题目ID')
    question_sort = db.Column(db.Integer, nullable=False, comment='题目在试卷中的排序号')
    question_score = db.Column(db.Numeric(5, 1), nullable=False, comment='题目在试卷中的分数')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    paper = db.relationship('ExamPaper', backref=db.backref('relations', lazy=True, cascade="all, delete-orphan"))
    question = db.relationship('QuestionBank', backref=db.backref('paper_relations', lazy=True))

class AnswerAreaStyle(db.Model):
    __tablename__ = 'answer_area_style'
    
    style_id = db.Column(db.Integer, primary_key=True, autoincrement=True, comment='答题样式唯一标识')
    type_id = db.Column(db.Integer, db.ForeignKey('question_type_dict.type_id'), nullable=False, comment='关联题目类型ID')
    style_name = db.Column(db.String(50), nullable=False, unique=True, comment='样式名称')
    style_config = db.Column(db.Text, nullable=False, comment='样式配置JSON')
    is_default = db.Column(db.Integer, default=0, comment='是否默认')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    type = db.relationship('QuestionTypeDict', backref=db.backref('styles', lazy=True))

class ExamAnswerSheet(db.Model):
    __tablename__ = 'exam_answer_sheet'
    
    sheet_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='答题卡唯一标识')
    paper_id = db.Column(db.BigInteger, db.ForeignKey('exam_paper.paper_id'), nullable=False, unique=True, comment='关联试卷ID')
    sheet_name = db.Column(db.String(200), nullable=False, comment='答题卡名称')
    template_config = db.Column(db.Text, comment='全局模板配置JSON')
    create_user = db.Column(db.String(50), default='', comment='创建人')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    update_time = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    paper = db.relationship('ExamPaper', backref=db.backref('answer_sheet', uselist=False, lazy=True))

class SheetQuestionRelation(db.Model):
    __tablename__ = 'sheet_question_relation'
    
    relation_id = db.Column(db.BigInteger, primary_key=True, autoincrement=True, comment='关联记录唯一标识')
    sheet_id = db.Column(db.BigInteger, db.ForeignKey('exam_answer_sheet.sheet_id', ondelete='CASCADE'), nullable=False, comment='关联答题卡ID')
    question_id = db.Column(db.BigInteger, db.ForeignKey('question_bank.question_id'), nullable=False, comment='关联题目ID')
    style_id = db.Column(db.Integer, db.ForeignKey('answer_area_style.style_id'), nullable=False, comment='关联答题样式ID')
    area_sort = db.Column(db.Integer, nullable=False, comment='答题区域排序号')
    create_time = db.Column(db.DateTime, default=datetime.now, comment='创建时间')
    
    sheet = db.relationship('ExamAnswerSheet', backref=db.backref('question_relations', lazy=True, cascade="all, delete-orphan"))
    question = db.relationship('QuestionBank', backref=db.backref('sheet_relations', lazy=True))
    style = db.relationship('AnswerAreaStyle', backref=db.backref('sheet_relations', lazy=True))
