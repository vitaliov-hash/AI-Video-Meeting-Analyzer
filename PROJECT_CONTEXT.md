# PROJECT_CONTEXT

## Проект и этап

Путь: `D:\AI Projects\AI-Video-Meeting-Analyzer`. DZ Light проверен на реальных RU/EN записях. DZ Pro добавляет импорт одной публичной записи из Google Drive, не OAuth или мониторинг папки.

Проверенный Lite commit: `e56ba54`; на нём создан локальный annotated tag `dz-lite-v1`. Работа Pro завершена в `feature/dz-pro` и зафиксирована локальным commit после Quality Gate; рабочее дерево чистое.

## Архитектура приложения

- FastAPI + одностраничный HTML/CSS/JS интерфейс.
- FFmpeg audio extraction и Faster-Whisper `small` CPU int8; DeepSeek по умолчанию, OpenAI/Gemini configurable.
- Ручная загрузка и Google Drive import передают файл в одну `process_video()` функцию.
- Google Drive adapter проверяет HTTPS/host, DNS IP, redirect hosts, размер, timeout, HTML и MP4/WebM signature; OAuth отсутствует.
- SQLite сохраняет источник, нормализованную ссылку, фазу и результат. Уникальный индекс защищает от повторного анализа.
- `PUBLIC_API_BASE_URL` позволяет статическому Vercel frontend вызывать отдельный Python backend. CORS включается только по `CORS_ALLOWED_ORIGINS`.
- Docker backend хранит DB и кэш Whisper на постоянном `/data`. Это single-instance конфигурация; in-process worker не переживает рестарт.

## Проверенные результаты Lite и Pro

- Реальная Lite транскрибация: RU 4:46 — 4 508 символов (`ru`, p=.99); EN 4:02 — 3 325 символов (`en`, p=.99). Реальные Lite summaries сохранены в локальной базе.
- **Live Cloud E2E 2026-11-06:** публичный Google Drive WebM (11,484,674 bytes; EBML signature valid) реально скачан, аудио извлечено, Faster-Whisper `small` обработал 4:02 и определил `en` (p=.99; 3,325 transcript characters). Реально выполнен один DeepSeek запрос: HTTP 200, usage 1,106 prompt + 282 completion = 1,388 tokens. Summary, source и transcript сохранены в SQLite; page/list/detail reload и повторная ссылка подтвердили persistence и dedup без нового AI вызова. Полный сценарий занял 632.19 s.
- Manual summary audit использовал сохранённую транскрипцию и официальный источник, без нового DeepSeek запроса. Большая часть содержания подтверждена. Найдены: ASR ошибся в фамилии `Stipano` (`Stepano` в транскрипции/summary); исходная устная арифметика не сходится (14 requests против 1+3+9=13); элемент `decisions` фактически описывает отсутствие решения; один open question является выводом, а не прямым вопросом. Результат встречи в БД не редактировался. Подробности и доказательства — в `ACCEPTANCE.md`.
- Подготовлена отдельная редакторская EN-демонстрация `DEMO_SUMMARY_EN_REVIEWED.md`; оригинальные AI-конспекты и транскрипция не изменялись. AI вызовов не было. План Teacher Live Demo и нулевого по AI-расходам Public Showcase зафиксирован в `DEMO_MODES.md`; режимы пока не развёрнуты.
- GitHub Stage 3 завершён: приватный repo `vitaliov-hash/AI-Video-Meeting-Analyzer`; Lite `main`, Pro `feature/dz-pro` и tag `dz-lite-v1` отправлены. PR #1 прошёл CI и слит 2026-11-06, merge commit `80e15afe303431df2a29e2076874ec539e18217c`.
- GitHub Actions success: runs `42262127724` на PR и `42262426419` после merge; тесты, Ruff, compileall, frontend и security scan прошли. Защита ветки недоступна текущему плану для private repo (403 требует Pro); не обходилась.
- Повторный Quality Gate — 28/28 PASS; workflow использует pytest temp path по умолчанию без фиксированного `.pytest-tmp`. Демонстрационные документы добавлены в Pro ZIP. Локальные ветки синхронизированы с origin, рабочее дерево чистое.
- Prompt уточнён для будущих анализов и добавлен regression test: не заносить нерешённость в decisions, не выводить вопросы из критики, не исправлять имена извне, отмечать внутренние числовые противоречия. Реальный анализ после этой правки **не запускался**.
- Safe logging: HTTPX/HTTPCore logger families (`httpx`, `httpcore`, `httpx2`, `httpcore2`) и Uvicorn access logger подавлены; app logs не содержат IP, URL или meeting ID. Добавлены privacy tests для URL/credentials/ID/IP. Системные журналы не очищались.
- Final Quality Gate: **28 pytest passed**; Ruff, compileall, JavaScript syntax, frontend build, security scan (repository + Pro ZIP) и `git diff --check` проходят. Тесты используют mocks; платных API-вызовов в Quality Gate нет.
- Полный cloud E2E с реальными Faster-Whisper и одним согласованным DeepSeek вызовом завершён; дальнейшие платные вызовы не разрешены этим прогоном.

## Git, релизы и публикация

- Тег `dz-lite-v1` указывает на подтверждённый checkpoint `e56ba54`.
- GitHub remote настроен и приватен; PR #1 слит после двух успешных Actions runs. `main` содержит merge commit `80e15afe303431df2a29e2076874ec539e18217c`; Lite tag `dz-lite-v1` не менялся.
- Защита `main` недоступна текущему GitHub плану для private repo; API вернул 403, требующий Pro. Публичность и обход ограничений не использовались.
- Vercel config и Docker backend build подготовлены локально. Docker daemon недоступен, поэтому `docker build` не проверен. Hosting projects/deployments не создавались.
- Перед публикацией требуется серверная аутентификация/rate limit и ограничение расходов: текущий API не защищён от произвольных вызовов. Права на учебные видео тоже не подтверждены.

## Безопасность и дальнейшая работа

- Не сохранять пользовательские share URLs, API keys, видео, model cache или локальную базу в Git/ZIP.
- Локальный `.env` существует; его значения не читать и не выводить.
- Следующий GitHub шаг: после отдельного согласования создать private repository в аккаунте пользователя, подключить remote, push ветки и открыть PR; merge запрещён до CI/review и отдельного согласования.
- Публичный deployment остаётся заблокирован до server-side auth, rate limiting, ограничений расходов, TLS, persistent storage/backups, выбора host и явного согласования.
