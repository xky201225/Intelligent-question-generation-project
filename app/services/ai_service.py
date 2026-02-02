import requests
import json
import logging
import base64
import time

# DeepSeek API Key (Plaintext as requested)
DEEPSEEK_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
API_URL = "https://api.deepseek.com/chat/completions" # Corrected Endpoint

logger = logging.getLogger(__name__)

class DeepSeekService:
    @staticmethod
    def _call_api(messages, temperature=0.7):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096
        }
        
        try:
            response = requests.post(API_URL, headers=headers, json=data, timeout=120) # Increased timeout
            response.raise_for_status()
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"DeepSeek API Call Failed: {e}")
            return None

    @classmethod
    def generate_questions_advanced(cls, subject, knowledge, difficulty, count, question_types, total_score, description, chapter_context=None, tags_keywords=None):
        """
        Advanced generation logic ported from Streamlit app
        """
        # Build Prompts
        knowledge_prompt = "\n".join([f"- {kp['name']}：占{kp['percentage']}%" for kp in knowledge if kp['name']])
        
        # Difficulty Prompt
        if isinstance(difficulty, dict):
             difficulty_prompt = f"难度分布：容易{difficulty.get('容易', 0)}%，中等{difficulty.get('中等', 0)}%，困难{difficulty.get('困难', 0)}%"
        else:
             difficulty_prompt = f"难度分布：{difficulty}"

        type_prompt = "\n".join([f"- {t['name']}：占题目总数的{t['percentage']}%" for t in question_types if t['name']])
        
        avg_score = total_score / count
        
        context_prompt = ""
        if chapter_context:
            context_trimmed = chapter_context[:4000]
            context_prompt = f"\n参考章节内容（请严格结合这些内容命题）：\n{context_trimmed}\n"

        tag_prompt = ""
        if tags_keywords:
            tag_prompt = f"\n额外约束（必须紧扣这些标签/关键词命题，避免跑题）：\n{tags_keywords}\n"

        prompt = f"""
        你是专业的{subject}出题老师，需生成{count}道题目，总分{total_score}分。
        
        知识点分布：
        {knowledge_prompt}
        
        {difficulty_prompt}
        
        题型及数量占比：
        {type_prompt}
        
        {context_prompt}

        {tag_prompt}
        
        必须包含所有指定的题型，并严格按照指定的数量占比生成。
        每题分值应根据难度和题型合理分配，总分应为{total_score}分，平均每题约{avg_score:.1f}分。
        
        要求：
        - 也需要兼顾{description}的要求
        - 选择题需包含题干、至少4个选项（A/B/C/D）和正确答案选项
        - 判断题需包含题干和正确答案（对/错）
        - 计算题需包含计算问题和详细解题步骤及答案
        - 写作题需包含问题描述和一篇完整的作文作为答案
        - 其他题型需包含问题描述和详细答案
        
        - 输出格式为JSON数组，严格遵循以下结构：
          [
            {{
              "stem": "题干内容",
              "type": "题型",
              "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}}, 
              "answer": "答案",
              "answer_content": "详细答案内容/解析",
              "knowledge": "{subject}",
              "knowledge_part": "该题所属的具体知识点部分",
              "tags": ["标签1", "标签2"],
              "difficulty": "容易/中等/困难",
              "score": 题目分值（整数）
            }},
            ...
          ]
        - 特别重要：仅输出JSON内容，不添加任何解释、说明或额外文字！
        - 确保JSON格式正确，可被Python的json.loads()直接解析。
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的出题专家。"},
            {"role": "user", "content": prompt}
        ]
        
        response = cls._call_api(messages)
        return cls._parse_json_response(response)

    @classmethod
    def generate_questions_from_document(cls, file_content, file_type, question_count, total_score, subject,
                                     knowledge, difficulty, question_types):
        """
        Generate questions based on uploaded document analysis
        """
        # Encode file content if needed, but DeepSeek API usually takes text context.
        # The referenced implementation sends base64, but generic DeepSeek chat might not support file upload directly in all endpoints.
        # Assuming we extract text first in FileService, we pass text here.
        # Wait, the referenced implementation sends base64 content in user message.
        # I will assume we pass extracted text here for simplicity and better compatibility.
        
        # If file_content is bytes, decode it (assuming it's text). 
        # If it's raw PDF bytes, we should have extracted text before calling this.
        # I will change the signature to accept 'document_text' instead of raw file content.
        pass 

    @classmethod
    def generate_questions_from_text_content(cls, document_text, question_count, total_score, subject,
                                     knowledge, difficulty, question_types):
        
        knowledge_prompt = "\n".join([f"- {kp['name']}：占{kp['percentage']}%" for kp in knowledge if kp['name']])
        
        if isinstance(difficulty, dict):
             difficulty_prompt = f"难度分布：容易{difficulty.get('容易', 0)}%，中等{difficulty.get('中等', 0)}%，困难{difficulty.get('困难', 0)}%"
        else:
             difficulty_prompt = f"难度分布：{difficulty}"

        type_prompt = "\n".join([f"- {t['name']}：占题目总数的{t['percentage']}%" for t in question_types if t['name']])
        
        avg_score = total_score / question_count

        prompt = f"""
        请分析我提供的{subject}教材/试卷内容，理解其中涉及的知识点和难度水平，然后生成一份相似的新试卷。
        要求生成{question_count}道题目，总分{total_score}分，平均每题约{avg_score:.1f}分。

        知识点分布必须严格遵循：
        {knowledge_prompt}

        难度分布必须严格遵循：
        {difficulty_prompt}

        题型及数量占比必须严格遵循：
        {type_prompt}

        参考文档内容：
        {document_text[:15000]}... (内容过长已截断)

        输出格式为JSON数组，结构如下：
        [
            {{
              "stem": "题干内容",
              "type": "题型",
              "options": {{"A": "选项A", ...}},
              "answer": "答案",
              "answer_content": "详细答案内容",
              "knowledge": "{subject}",
              "knowledge_part": "该题所属的具体知识点部分",
              "difficulty": "容易/中等/困难",
              "score": 题目分值（整数）
            }},
            ...
        ]
        特别重要：仅输出JSON内容，不添加任何解释、说明或额外文字！
        """
        
        messages = [
            {"role": "system", "content": "你是一个专业的出题专家。"},
            {"role": "user", "content": prompt}
        ]
        
        response = cls._call_api(messages)
        return cls._parse_json_response(response)

    @staticmethod
    def _parse_json_response(response_text):
        if not response_text:
            return []
        try:
            # Clean up potential markdown code blocks
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            # Find start and end of list
            start = clean_text.find('[')
            end = clean_text.rfind(']') + 1
            if start != -1 and end != -1:
                clean_text = clean_text[start:end]
            return json.loads(clean_text)
        except json.JSONDecodeError:
            logger.error("Failed to parse AI response as JSON")
            return []
