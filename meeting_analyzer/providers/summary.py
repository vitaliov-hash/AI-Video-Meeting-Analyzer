import json
import os
import re
from pathlib import Path
from typing import Any

import httpx


class SummaryProvider:
    def summarize(self, transcript: str, language: str) -> dict[str, Any]:
        raise NotImplementedError


class ConfiguredSummaryProvider(SummaryProvider):
    def __init__(self, provider: str):
        self.provider = provider

    def summarize(self, transcript: str, language: str) -> dict[str, Any]:
        system_prompt = (Path(__file__).resolve().parents[2] / "prompts" / "meeting_summary.md").read_text(encoding="utf-8")
        prompt = f"Язык распознавания: {language}\n\nТранскрипт:\n{transcript}"
        raw = self._request(prompt, system_prompt)
        summary = validate_summary(raw)
        empty_phrase = "В записи это не прозвучало." if language.lower().startswith("ru") else "Not stated in the recording."
        for key in ("decisions", "next_tasks", "open_questions"):
            summary[key] = [item.strip() for item in summary[key] if item.strip()] or [empty_phrase]
        return summary

    def _request(self, prompt: str, system_prompt: str) -> str:
        if self.provider in ("deepseek", "openai"):
            env_prefix = "DEEPSEEK" if self.provider == "deepseek" else "OPENAI"
            key = os.getenv(f"{env_prefix}_API_KEY", "").strip()
            if not key:
                raise RuntimeError(f"Не задан {env_prefix}_API_KEY в локальном файле .env.")
            base = "https://api.deepseek.com" if self.provider == "deepseek" else "https://api.openai.com/v1"
            model = os.getenv(f"{env_prefix}_MODEL", "deepseek-flash" if self.provider == "deepseek" else "gpt-5-mini")
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": system_prompt},
                             {"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
            if self.provider == "deepseek":
                payload["thinking"] = {"type": "disabled"}
            try:
                response = httpx.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {key}"},
                    json=payload, timeout=180)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"AI-провайдер вернул ошибку HTTP {exc.response.status_code}. Проверьте ключ и модель.") from None
            except httpx.HTTPError:
                raise RuntimeError("Не удалось связаться с AI-провайдером. Проверьте интернет и повторите загрузку.") from None
            return response.json()["choices"][0]["message"]["content"]
        if self.provider == "gemini":
            key = os.getenv("GEMINI_API_KEY", "").strip()
            if not key:
                raise RuntimeError("Не задан GEMINI_API_KEY в локальном файле .env.")
            model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            try:
                response = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": key}, json={"systemInstruction": {"parts": [{"text": system_prompt}]},
                            "contents": [{"parts": [{"text": prompt}]}],
                            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}, timeout=180)
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"AI-провайдер вернул ошибку HTTP {exc.response.status_code}. Проверьте ключ и модель.") from None
            except httpx.HTTPError:
                raise RuntimeError("Не удалось связаться с AI-провайдером. Проверьте интернет и повторите загрузку.") from None
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        raise RuntimeError(f"Неизвестный AI_PROVIDER: {self.provider}. Используйте deepseek, openai или gemini.")


def validate_summary(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI-провайдер вернул некорректный JSON. Повторите загрузку.") from exc
    required = {"short_summary": str, "decisions": list, "next_tasks": list, "open_questions": list}
    if not isinstance(value, dict) or any(not isinstance(value.get(k), t) for k, t in required.items()):
        raise ValueError("AI-провайдер вернул ответ не по ожидаемой структуре. Повторите загрузку.")
    for key in ("decisions", "next_tasks", "open_questions"):
        if not all(isinstance(item, str) for item in value[key]):
            raise ValueError(f"Поле {key} содержит элемент не в виде текста.")
    if not value["short_summary"].strip():
        raise ValueError("AI-провайдер вернул пустое краткое содержание.")
    return value
