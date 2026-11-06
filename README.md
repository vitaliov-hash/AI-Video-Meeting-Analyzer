# AI Video Meeting Analyzer — DZ Light

Локальное приложение для транскрибации русских и английских видеовстреч и создания структурированного конспекта. Исходное видео и распознавание обрабатываются локально; видео удаляется после обработки. Для конспекта расшифровка передаётся выбранному внешнему AI-провайдеру и затем хранится в локальной SQLite базе.

## Требования

- Python 3.11+
- Интернет при первом запуске, чтобы установить зависимости и загрузить мультиязычную Faster-Whisper модель
- API ключ выбранного summarizer (по умолчанию DeepSeek); вызовы могут тарифицироваться

## Установка и запуск (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
# Добавьте DEEPSEEK_API_KEY в локальный .env
python -m meeting_analyzer
```

Откройте `http://127.0.0.1:8000`. Выберите MP4/WebM: обработка начнётся автоматически. Первый запуск может занять дольше из-за скачивания модели (кэш хранится в `.cache/huggingface` на диске проекта). `data/meetings.sqlite3` хранит историю, `.env` и все данные остаются локальными.

## Настройки

В `.env` задаются `AI_PROVIDER=deepseek|openai|gemini`, ключ и модель соответствующего API, `WHISPER_MODEL`, `WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`, `MAX_UPLOAD_MB`, `HOST`, `PORT`. Смена провайдера не требует изменений бизнес-логики.

## Проверки

```powershell
python -m pytest
python -m compileall -q meeting_analyzer tests
```

Критерии и тест-план описаны в `ACCEPTANCE.md`. Реальные внешние AI-запросы не входят в обычный тестовый прогон.
