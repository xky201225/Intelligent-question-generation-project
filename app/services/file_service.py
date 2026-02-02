import os
import re
import docx
import fitz  # PyMuPDF
import PyPDF2
from werkzeug.utils import secure_filename
from flask import current_app

class FileService:
    @staticmethod
    def save_file(file, subfolder=''):
        filename = secure_filename(file.filename)
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
        
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return file_path

    @staticmethod
    def extract_text(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        content = ""
        
        try:
            if ext == '.docx':
                doc = docx.Document(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])
            elif ext == '.pdf':
                # Try PyMuPDF first (better quality)
                try:
                    with fitz.open(file_path) as doc:
                        for page in doc:
                            content += page.get_text() + "\n"
                except Exception as e:
                    print(f"PyMuPDF failed, falling back to PyPDF2: {e}")
                    # Fallback to PyPDF2
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages:
                            content += page.extract_text() + "\n"
            elif ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
        except Exception as e:
            print(f"Error extracting text from {file_path}: {e}")
            return None
            
        return content

    @staticmethod
    def heuristic_recognize_chapters(text):
        """
        Identify chapters based on regex patterns (simplified version of logic from 1/api_calls.py).
        Returns list of dicts: [{'title': 'Chapter 1...', 'content': '...'}]
        """
        if not text:
            return []
            
        # Regex to find chapter titles like "第X章", "Chapter X"
        # Using a slightly simplified pattern
        pattern = r"(第[一二三四五六七八九十百0-9]+章\s*.*|Chapter\s*\d+\s*.*)"
        
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        
        chapters = []
        if not matches:
            # If no chapters found, treat whole text as one chapter
            chapters.append({
                'title': '正文',
                'content': text
            })
            return chapters

        for i in range(len(matches)):
            start_pos = matches[i].start()
            title = matches[i].group().strip()
            
            # End pos is start of next match or end of text
            if i < len(matches) - 1:
                end_pos = matches[i+1].start()
            else:
                end_pos = len(text)
                
            # Content is text between start (after title) and end
            content = text[matches[i].end():end_pos].strip()
            
            chapters.append({
                'title': title,
                'content': content
            })
            
        return chapters

    @staticmethod
    def heuristic_parse_questions(text):
        """
        Heuristically parse a question document into a list of questions.
        Output: [{'content': str, 'answer': str, 'analysis': str}]
        This is intentionally conservative and should be followed by manual review.
        """
        if not text:
            return []

        # Normalize whitespace
        raw = text.replace('\r\n', '\n').replace('\r', '\n')
        raw = re.sub(r'\n{3,}', '\n\n', raw).strip()
        if not raw:
            return []

        # Split by common question number patterns:
        # 1. xxx / 1、xxx / 1)xxx / （1）xxx / 一、xxx
        split_pattern = re.compile(
            r'(?m)^(?:\s*)(?:'
            r'(\d{1,3})[\.、\)]\s+|'
            r'（\d{1,3}）\s*|'
            r'[一二三四五六七八九十]{1,3}、\s+'
            r')'
        )

        # Find starts
        starts = [m.start() for m in split_pattern.finditer(raw)]
        if not starts:
            # Fallback: treat whole doc as one question
            blocks = [raw]
        else:
            starts.append(len(raw))
            blocks = []
            for i in range(len(starts) - 1):
                block = raw[starts[i]:starts[i + 1]].strip()
                if len(block) >= 5:
                    blocks.append(block)

        questions = []
        for block in blocks:
            # Try to extract answer/analysis markers
            # Common markers: "答案:" "参考答案:" "解析:" "答案：" etc.
            answer = ''
            analysis = ''
            content = block

            m_ans = re.search(r'(?i)(?:答案|参考答案)\s*[:：]\s*', block)
            m_ana = re.search(r'(?i)(?:解析|答案解析)\s*[:：]\s*', block)

            if m_ans and m_ana:
                # whichever comes first splits content vs rest
                first = min(m_ans.start(), m_ana.start())
                content = block[:first].strip()
                # extract answer and analysis portions
                if m_ans.start() < m_ana.start():
                    answer = block[m_ans.end():m_ana.start()].strip()
                    analysis = block[m_ana.end():].strip()
                else:
                    analysis = block[m_ana.end():m_ans.start()].strip()
                    answer = block[m_ans.end():].strip()
            elif m_ans:
                content = block[:m_ans.start()].strip()
                answer = block[m_ans.end():].strip()
            elif m_ana:
                content = block[:m_ana.start()].strip()
                analysis = block[m_ana.end():].strip()

            # Cleanup extremely short content
            if len(content) < 5:
                continue

            questions.append({
                'content': content,
                'answer': answer,
                'analysis': analysis
            })

        return questions
