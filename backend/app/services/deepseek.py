from __future__ import annotations

import json
import time
from collections.abc import Iterator

import requests
from flask import current_app


class DeepSeekClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=180)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except Exception as err:
                last_err = err
                if attempt < 2:
                    time.sleep(1 + attempt)
                continue
        raise last_err if last_err else RuntimeError("DeepSeek 请求失败")

    def chat_stream(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> Iterator[str]:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=180, stream=True)
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            delta = obj.get("choices", [{}])[0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                        except Exception:
                            continue
                return
            except Exception as err:
                last_err = err
                if attempt < 2:
                    time.sleep(1 + attempt)
                continue
        raise last_err if last_err else RuntimeError("DeepSeek 流式请求失败")


def get_deepseek_client() -> DeepSeekClient:
    return DeepSeekClient(
        api_key=current_app.config["DEEPSEEK_API_KEY"],
        base_url=current_app.config["DEEPSEEK_BASE_URL"],
        model=current_app.config["DEEPSEEK_MODEL"],
    )
