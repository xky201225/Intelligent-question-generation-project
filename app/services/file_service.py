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
