# Intelligent Test Paper Generation System Construction Plan

I will build the project using **Flask** + **SQLAlchemy** + **MySQL** with a modular structure.

## 1. Project Initialization & Infrastructure
- **Directory Structure**:
  - `app/`: Core application package.
    - `models/`: Database models (ORM).
    - `routes/`: Blueprint routes (Web & API).
    - `services/`: Business logic (AI, Files, Export).
    - `templates/`: HTML templates (Jinja2 + Bootstrap).
    - `static/`: CSS/JS.
  - `config.py`: Configuration (DB connection, API Keys).
  - `requirements.txt`: Dependencies.
  - `run.py`: Entry point.
- **Dependencies**: `Flask`, `Flask-SQLAlchemy`, `PyMySQL`, `requests` (for AI), `python-docx` (Word handling), `pdfkit`/`reportlab` (PDF handling).

## 2. Database Implementation
I will create SQLAlchemy models mapping exactly to your MySQL schema:
- **Dictionaries**: `SubjectDict`, `QuestionTypeDict`, `QuestionDifficultyDict`.
- **Textbooks**: `Textbook`, `TextbookChapter` (with recursive parent support).
- **Questions**: `QuestionBank` (includes `is_ai_generated`, `source_question_ids`).
- **Papers**: `ExamPaper`, `PaperQuestionRelation`.
- **Initialization**: A script to create tables and seed basic dictionary data.

## 3. Core Business Services
- **AI Service (`services/ai_service.py`)**:
  - Integration with DeepSeek API.
  - Functions: `generate_questions(content, type, count)`, `expand_question(question_id)`.
  - **Note**: API Key will be placed as a global variable in this file as requested.
- **File Service**:
  - Upload handling for Textbooks (PDF/Word).
  - Text extraction logic to feed into AI.
- **Export Service**:
  - Convert `ExamPaper` data to `.docx` and `.pdf`.
  - Support "Student Version" (no answers) and "Teacher Version" (with answers).

## 4. Feature Implementation (Routes & UI)
- **Textbook Management**: Upload books, manage chapter tree structure.
- **Question Bank**:
  - **Search**: Advanced filtering by subject, chapter, type, difficulty.
  - **AI Generation**:
    1. Select Textbook/Chapter -> AI Generate.
    2. Select Existing Paper/Question -> AI Generate Similar.
  - **Review**: Edit/Verify AI-generated questions before saving.
- **Paper Assembly**:
  - "Basket" system to pick questions.
  - Configuration: Set scores, paper info.
  - **Preview & Export**: Final review page with download buttons.

## 5. Development Steps
1.  **Setup**: Create files, install requirements, configure DB.
2.  **Models**: Write `models.py` with all constraints/relationships.
3.  **Basic UI**: Create base layout and navigation.
4.  **Modules**: Implement Textbook -> Question -> Paper flow sequentially.
5.  **AI Integration**: Connect the DeepSeek logic.
