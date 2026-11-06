import pytest

from meeting_analyzer.providers.summary import (
    ConfiguredSummaryProvider,
    validate_summary,
)


def test_valid_russian_summary_keeps_unicode():
    value = validate_summary('{"short_summary":"Обсудили запуск","decisions":["Запустить пилот"],"next_tasks":["Подготовить план"],"open_questions":["Кто согласует?"]}')
    assert value["short_summary"] == "Обсудили запуск"
    assert value["open_questions"] == ["Кто согласует?"]


@pytest.mark.parametrize("raw", [
    "not json",
    '{"short_summary":"x","decisions":[],"next_tasks":[],"open_questions":1}',
    '{"short_summary":"","decisions":[],"next_tasks":[],"open_questions":[]}',
])
def test_rejects_invalid_ai_output(raw):
    with pytest.raises(ValueError):
        validate_summary(raw)


def test_accepts_fenced_json():
    value = validate_summary('```json\n{"short_summary":"OK","decisions":[],"next_tasks":[],"open_questions":[]}\n```')
    assert value["short_summary"] == "OK"


def test_provider_uses_product_prompt_and_marks_empty_categories(monkeypatch):
    provider = ConfiguredSummaryProvider("deepseek")
    calls = {}

    def response(prompt, system_prompt):
        calls["prompt"] = prompt
        calls["system"] = system_prompt
        return '{"short_summary":"Обсуждали план","decisions":[],"next_tasks":[],"open_questions":[]}'

    monkeypatch.setattr(provider, "_request", response)
    result = provider.summarize("Обсудили план работ.", "ru")
    assert "Обсудили план работ." in calls["prompt"]
    assert "Не добавляй" in calls["system"]
    assert result["decisions"] == ["В записи это не прозвучало."]
    assert result["next_tasks"] == ["В записи это не прозвучало."]
    assert result["open_questions"] == ["В записи это не прозвучало."]


def test_prompt_distinguishes_decisions_inferences_and_source_conflicts():
    from pathlib import Path

    prompt = (Path(__file__).resolve().parents[1] / "prompts" / "meeting_summary.md").read_text(
        encoding="utf-8"
    )
    assert "решение ещё не принято" in prompt
    assert "Не создавай follow-up вопросы из критики" in prompt
    assert "Не исправляй имена по памяти или внешним знаниям" in prompt
    assert "арифметическое несоответствие" in prompt


def test_missing_provider_key_fails_without_request(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    provider = ConfiguredSummaryProvider("deepseek")
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        provider._request("prompt", "system")
