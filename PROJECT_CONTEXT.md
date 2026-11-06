# PROJECT_CONTEXT

## Назначение и путь

Локальный AI-анализатор видео встреч, DZ Light. Канонический проект: `D:\AI Projects\AI-Video-Meeting-Analyzer`.

## Текущее состояние

DZ Light частично реализован: локальная одностраничная загрузка, очередь, FFmpeg извлечение, Faster-Whisper STT, провайдеры summary, SQLite история, статусы и понятные ошибки. Не финальная приёмка: нет real-provider summary/grounding проверки, потому что API ключ отсутствует и платный вызов запрещён без отдельного согласования.

До начала работ каталог проекта существовал пустым и без Git. Исходники тестовых записей найдены вне проекта в фактическом каталоге `D:\AI Projects\_DemoMediaAI-Video-Meeting-Analyzer` (имя отличается от пути в запросе): RU и EN. Исходники оставлять вне Git.

Файлы: `Banking_Committee_Hearing_-_Illegal_Foreclosures.webm` — 00:04:02; `Интервью_с_Дмитрием_Емцом.webm` — 00:04:46; дополнительное интервью Nival — 00:06:26. Длительности считаны из Windows Shell metadata.

Официальные Google Docs DZ Light и DZ Pro прочитаны через Google Drive. DZ Light требует ручную загрузку WebM/MP4, фактическую транскрибацию и summary, одну страницу, SQLite/диск persistence, статусы и понятные ошибки. DZ Pro/PRO+ исключены.

## Архитектурные решения

- Python/FastAPI + HTML/CSS/JS; локальный интерфейс.
- Faster-Whisper multilingual `small`, CPU int8 и FFmpeg для извлечения аудио.
- Summarizer provider interface; DeepSeek default, OpenAI/Gemini configurability. Настройки моделей актуализированы по официальным API reference (DeepSeek `deepseek-flash`, OpenAI `gpt-5-mini`, Gemini `gemini-3.8-flash`).
- Локальная SQLite, временные видео удаляются после обработки.
- Нет фиктивного AI результата и никаких реальных API-вызовов без ключа.
- Model cache направлен в `.cache/huggingface` под проектом, чтобы не занять системный диск C.
- Compatibility fallback обходит PyAV `metadata_errors` несовместимость.

## Тесты и проверки

- Ruff: PASS; pytest: **11 passed**; compileall: PASS; JS syntax: PASS.
- HTTP runtime smoke: PASS (страница/API 200).
- STT small CPU int8: RU 4:46 → 4 508 chars, `ru` p=.99; EN 4:02 → 3 325 chars, `en` p=.99. QA SQLite пережила повторное открытие; тестовые базы удалены.
- AI response structure/eval mocks: PASS. Реальная summary и экспертная проверка grounding: BLOCKED до разрешённого обращения к AI API.
- Secrets scan: PASS. Подробнее в `ACCEPTANCE.md`.

## Git/GitHub/Deploy

Локальный репозиторий и ветка `feature/dz-light`; root commit `adf0246` создан после Local Quality Gate. Remote/GitHub не настроены, push/PR не выполнялись. Никакой публикации/deploy.

## Известные ограничения/блокеры

- Реальная генерация конспекта требует API ключа и платного внешнего вызова; без отдельного согласования не запускать.
- Визуальная проверка в браузере недоступна, так как UI browser provider не подключён; HTTP smoke пройден.
- Точность полной транскрипции требует человекочитаемой сверки; короткий RU фрагмент имел ошибку в распознавании имени.

## Следующие действия

Завершить реализацию UI/backend, проверить unit/runtime, выполнить локальную транскрибацию RU и EN если модель доступна, подключить summarizer без платного вызова, проверить AI evals моками, секреты и Git diff. При необходимости запросить ключ/разрешение только перед реальным платным тестом.
