from app import create_app, db
from app.models.models import SubjectDict, QuestionTypeDict, QuestionDifficultyDict, AnswerAreaStyle
import json

app = create_app()

import pymysql
from config import Config

def create_database():
    # Parse the database URI to get connection details
    # SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:201225@localhost/test_paper_system?charset=utf8mb4'
    uri = Config.SQLALCHEMY_DATABASE_URI
    db_name = uri.split('/')[-1].split('?')[0]
    
    # Connect to MySQL server (no specific DB)
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='201225',
        charset='utf8mb4'
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
        print(f"Database '{db_name}' created or already exists.")
    except Exception as e:
        print(f"Error creating database: {e}")
    finally:
        cursor.close()
        conn.close()

def init_db():
    create_database()
    
    with app.app_context():
        # Drop all tables to ensure schema update (For Development/Finalizing)
        db.drop_all()
        db.create_all()
        
        # Seed Subjects
        if not SubjectDict.query.first():
            subjects = [
                {'name': '语文', 'code': 'CHN'},
                {'name': '数学', 'code': 'MATH'},
                {'name': '英语', 'code': 'ENG'},
                {'name': '物理', 'code': 'PHY'},
                {'name': '化学', 'code': 'CHEM'}
            ]
            for s in subjects:
                db.session.add(SubjectDict(subject_name=s['name'], subject_code=s['code']))
        
        # Seed Types
        if not QuestionTypeDict.query.first():
            types = [
                {'name': '选择题', 'code': 'CHOICE'},
                {'name': '填空题', 'code': 'FILL'},
                {'name': '简答题', 'code': 'SA'},
                {'name': '判断题', 'code': 'JUDGE'},
                {'name': '计算题', 'code': 'CALC'},
                {'name': '写作题', 'code': 'WRITE'}
            ]
            for t in types:
                db.session.add(QuestionTypeDict(type_name=t['name'], type_code=t['code']))
        
        # Seed Difficulty
        if not QuestionDifficultyDict.query.first():
            diffs = [
                {'name': '简单', 'level': 1},
                {'name': '中等', 'level': 2},
                {'name': '困难', 'level': 3}
            ]
            for d in diffs:
                db.session.add(QuestionDifficultyDict(difficulty_name=d['name'], difficulty_level=d['level']))
                
        db.session.commit()
        
        # Seed Answer Area Styles
        if not AnswerAreaStyle.query.first():
            # Get Type IDs
            choice_id = QuestionTypeDict.query.filter_by(type_code='CHOICE').first().type_id
            fill_id = QuestionTypeDict.query.filter_by(type_code='FILL').first().type_id
            sa_id = QuestionTypeDict.query.filter_by(type_code='SA').first().type_id
            judge_id = QuestionTypeDict.query.filter_by(type_code='JUDGE').first().type_id
            
            styles = [
                {
                    'type_id': choice_id, 
                    'name': '标准选择题涂卡', 
                    'config': {'type': 'optical_mark', 'options': ['A', 'B', 'C', 'D'], 'layout': 'horizontal'},
                    'default': 1
                },
                {
                    'type_id': fill_id, 
                    'name': '标准填空下划线', 
                    'config': {'type': 'text_line', 'lines': 1},
                    'default': 1
                },
                {
                    'type_id': sa_id, 
                    'name': '标准简答题横线', 
                    'config': {'type': 'text_box', 'lines': 5},
                    'default': 1
                },
                {
                    'type_id': judge_id, 
                    'name': '标准判断题涂卡', 
                    'config': {'type': 'optical_mark', 'options': ['T', 'F'], 'layout': 'horizontal'},
                    'default': 1
                }
            ]
            
            for s in styles:
                db.session.add(AnswerAreaStyle(
                    type_id=s['type_id'],
                    style_name=s['name'],
                    style_config=json.dumps(s['config']),
                    is_default=s['default']
                ))
        
        db.session.commit()
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
