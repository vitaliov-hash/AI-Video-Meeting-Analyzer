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
- Manual summary audit использовал сохранённую транскрипцию без нового DeepSeek запроса. Найдены одна ошибка ASR в имени, внутреннее арифметическое противоречие и спорная классификация элемента summary. Конкретные имена и содержание результата не копируются в материалы сдачи из-за неподтверждённых прав на исходный клип. Результат встречи в БД не редактировался.
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
- Stage 3 GitHub завершён: private repository существует; `main`, `feature/dz-pro` и tag `dz-lite-v1` отправлены, PR #1 прошёл CI и слит. Stage 4 PR #3 из `feature/stage4-showcase` также прошёл все CI checks (Actions run `42276091985`) и слит в `main` merge commit `0fd1333060c6f179ba6244ed158198bea9ab9795`; tag `dz-lite-v1` не менялся.
- Публичный deployment backend остаётся заблокирован до server-side auth, rate limiting, ограничений расходов, TLS, persistent storage/backups и выбора хоста. Stage 4 допускает только отдельную статическую Showcase-сборку без backend.

## Stage 4 — завершённая ветка Showcase (историческая запись до Stage 5)

- Ветка `feature/stage4-showcase` создана от актуального `main`; тег `dz-lite-v1` не перемещался.
- Vercel build переключён на статический Showcase. Артефакт содержит только frontend и безопасный синтетический `static/demo-data.json`; живые API-формы и polling в этом режиме выключены. Live mode и прежний Lite/Pro pipeline сохранены.
- Копирование фальшивого RU/EN материала в публичный build сделано только после проверки `MEDIA_LICENSE_NOTES.md`: в файле данных нет пользовательских записей, частных Drive ID или реальной транскрипции. Оба текста явно обозначены вымышленными.
- Временный Teacher Live Demo не реализован и не активирован. FastAPI не опубликован; для будущего режима остаются обязательными auth, квоты, ограничения видео/расхода, срок до 7 дней и серверный kill switch.
- Локально подтверждены: 28 pytest, Ruff, compileall по `meeting_analyzer`, `tests`, `scripts`, JS syntax, RU/EN harness, изоляция live/Showcase build и HTTP smoke (страница/data 200, `/api/meetings` 404). Chrome/CDP проверил RU/EN desktop и mobile width 390 px; `innerWidth=390`, `scrollWidth=390`, один столбец. ZIP после Stage 4 пересобран, security scan PASS, 52 безопасных entries. Скриншоты лежат в `docs/showcase/`; CI для Stage 4 прошёл на PR #3, внешний Vercel deployment пока pending.
- Vercel Hobby должен быть подтверждён в аккаунте до создания project. Для Hobby личного пользователя нужен некоммерческий use; учебный проект предполагается некоммерческим. Если Vercel просит карту/платный upgrade, остановиться.
- Не публиковать транскрипты из SQLite и видео с неподтверждёнными правами. Для преподавателя подготовлен `TEACHER_HANDOUT.md`; фактическую Vercel ссылку и screenshots нужно добавить после внешней проверки.

## Stage 5 — финализация Teacher Preview и сдачи DZ Pro (актуальное состояние)

- Рабочая ветка: `feature/teacher-live-guard`, ответвлена от `main` `dae8bf4`. Изменения Stage 5 пока локальные; commit, PR и merge выполняются только после полного local Quality Gate и зелёного CI.
- Teacher Preview guard реализован локально и выключен по умолчанию. Валидация конфигурации требует loopback bind, отдельного demo data directory, сильного demo password, независимого HMAC secret, одного точного HTTPS CORS origin, DeepSeek provider, MAX_UPLOAD_MB не выше 100 и срока 1–7 дней (5 дней по умолчанию).
- Все `/api/*` endpoints требуют bearer auth в teacher mode до чтения request body; отдельный rate limit применяется к login/API. Ограничение тела stream действует и без Content-Length. Пароли и токены не пишутся в storage/localStorage/logs.
- SQLite счётчик атомарный и сохраняется между перезапусками: не больше 2 новых analysis attempts за период. Повтор существующей облачной ссылки не расходует слот. Не более 8 часов на token; срок приложения создаётся однократно в SQLite и не может выйти за 7 суток.
- Персональная `data/meetings.sqlite3` не используется в Teacher mode; все результаты/загрузки находятся в `.teacher-demo-data/`, которая добавлена в `.gitignore`. Выходной AI ограничен 600 tokens, prompt 32,000 UTF-8 bytes, transcript 8,000 chars; максимум 100 MB upload. Kill switch: `python -m meeting_analyzer.teacher_demo --disable`.
- Vercel guarded build: production и обычный Preview остаются Showcase. Teacher UI строится только при `VERCEL_ENV=preview` и `TEACHER_PREVIEW_BUILD=1` и требует HTTPS backend URL. Отдельный project/Preview env не создан и не активирован; `vercel.json` изменён, чтобы обычный deploy продолжал собирать Showcase.
- Ни backend, ни Quick Tunnel, ни новый DeepSeek вызов не активировались. Проверка фоновой обработки через публичный туннель не выполнялась. Quick Tunnel предназначен лишь для временной supervised демонстрации; Windows PC, backend и tunnel должны оставаться активными.
- Репозиторий перед публичным раскрытием имеет вердикт **NOT SAFE**: в достижимой Git-истории присутствуют личные авторские identities. Сохранять private; при необходимости публичного доступа преподавателю создать отдельный очищенный submission репозиторий. На GitHub не найдено секретов/Drive URL в активных refs и доступных actions logs; прошлые runs не имели artifacts. Несколько локальных недостижимых git blobs содержат приватный Drive ID и не были обнаружены в GitHub refs; не запускать git gc/prune.
- Права на прежнюю реальную E2E запись и ее результат остаются неподтверждёнными, поэтому реальное видео/результат и скриншоты не включены в публичный пакет. Владелец сообщает, что Vercel Showcase работает; точный URL пока не внесён/не проверен в этой сессии.
- Финальная публичная доказательная запись полного процесса Google Drive → статусы → Whisper → AI → reload → dedup не подготовлена. Новых DeepSeek вызовов не было. До сдачи нужны права на источник (либо новая разрешённая запись), фактический Vercel URL и, если нужны кадры процесса с нуля, отдельное согласование одного платного DeepSeek вызова.
- Stage 5 локальный Quality Gate: **35 pytest passed**, Ruff PASS, compileall PASS, Node syntax PASS, Showcase/Teacher harness PASS, frontend build mode checks PASS, `git diff --check` PASS. В TestClient все API сценарии выполнялись с mock pipeline; ключ DeepSeek не вызывался.
- Окончательный Pro ZIP пересобирается `python scripts/package_dz_pro.py` из Git-tracked files с явным исключением `.env`, секретов, баз, видео, моделей и локальных runtime directories. Финальный archive/security scan выполняются перед commit.
- Vercel CI status на `main` — success; Vercel dashboard record связан с GitHub check. Публичный URL домена пока не предоставлен из status API. Vercel backend/tunnel не включались, инфраструктурных расходов нет.
