# Приёмка — DZ Light

Статус каждого критерия: не считать PASS без выполнения; указывать PASS/FAIL/BLOCKED и доказательство.

## Результат текущего прохода — 2026-11-06

| ID | Критерий | Проверка | Ожидаемый результат |
|---|---|---|---|
| A1 | MP4/WebM upload | Валидировать формат API и загрузить реальные WebM RU/EN | **PASS** — оба WebM приняты; неверный `.txt` отклонён с ясным сообщением. MP4 не найден среди тестовых файлов и отдельно ещё не проверен. |
| A2 | Автостарт, один файл | Загрузить запись через upload endpoint | **PASS** — обработка стартует при POST; единственный worker сериализует задачи (`max_workers=1`). Параллельную очередь отдельно не стресс-тестировали. |
| A3 | Реальное извлечение речи | RU 4:46, затем EN 4:02, Faster-Whisper `small` CPU int8 | **PASS** — RU 4 508 символов, язык `ru` p=0,99; EN 3 325 символов, язык `en` p=0,99. Аудио действительно извлекалось пакетным FFmpeg. |
| A4 | Язык оригинала | Проверить первые фрагменты RU/EN и Unicode из SQLite | **PASS** — языки совпадают, перевод не применялся, кириллица сохранена. В RU фрагменте есть небольшая ошибка распознавания имени; требуется человекочитаемая сверка полной транскрипции перед сдачей. |
| A5 | Summary структура | Реальная транскрипция → DeepSeek | **PASS** — RU и EN реальные ответы сохранены; обе записи имеют краткое содержание, решения, задачи и вопросы, язык ответа соответствует записи. |
| A6 | Grounding | Сверить реальный summary с исходной записью | **PARTIAL** — ручная сверка нового EN Cloud E2E завершена (см. аудит ниже): общий смысл основан на записи, но найдены неверное имя ASR, несогласованные числа и ошибка классификации категории. Строгая автоматическая word-overlap эвристика не прошла. RU summary отдельно не пересматривался в этом этапе. |
| A7 | Persistence | Сохранить transcript в SQLite и перечитать новой копией store | **PASS** — имя/статус/язык/транскрипт пережили повторное открытие DB; unit-тест round-trip также PASS. Summary будет доступен тем же способом после реального вызова. |
| A8 | Статусы и ошибки | Невалидный формат, отсутствующий API key | **PASS** — API проверяет формат; статус error сохраняет транскрипт и язык; UI содержит повторную загрузку. Визуальная браузерная проверка отдельно не выполнена. |
| A9 | Privacy | Secrets scan и Git status/history | **PASS** — secrets/local-data scan прошёл по рабочему дереву, Pro ZIP и достижимой Git history; `.env`, DB, модели, видео, результаты и private Drive ID отсутствуют в commit/ZIP. Проверенная история опубликована в приватном remote. |

## AI evals (без платных запросов)

1. Пустые категории → провайдер-адаптер явно добавляет отсутствие на русском/английском. **PASS** (mock).
2. Кириллический вход → UTF-8 round-trip и текст на языке транскрипта. **PASS** (fixture/storage).
3. Невалидный/пустой JSON → отклонение вместо статуса `ready`. **PASS**.
4. Решение без исполнителя/срока и противоречия → prompt-правила + регрессионные проверки классификации. EN live summary вручную сверено: смысл в целом подтверждён, но найдены ошибка ASR в фамилии, арифметическая нестыковка исходной речи и некорректная классификация нерешённости. Ручная сверка реального RU summary остаётся отдельным ограничением.

## Выполненные проверки

Команды: `python -m ruff check meeting_analyzer tests scripts`; `python -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp`; `python -m compileall -q meeting_analyzer tests scripts`; `node --check static/app.js`; `git diff --check`.

Диагностика исходного сбоя pytest: внутри `.venv` использовался Python 3.12.14, но `pip` отсутствовал, а `site-packages/pytest` был пуст. Импорт находил namespace package (`__file__ = None`, без `__version__`, `pytest.__main__` и `console_main`). Одноимённого файла или каталога в проекте нет. `ensurepip` восстановил pip после перенаправления TEMP в каталог проекта; затем переустановлен только pytest 8.4.2 с лёгкими зависимостями `colorama`, `iniconfig`, `packaging`, `pluggy`, `pygments`. Runtime-зависимости приложения не переустанавливались.

- Lint: **PASS**
- Tests: **PASS — 28 passed** in isolated Python 3.12.14 environment (mocked API/download/pipeline; no paid AI calls)
- Typecheck: **N/A** (отдельный статический type checker не настроен)
- Build: **PASS** — Vercel static frontend build; Docker image build **NOT RUN** (Docker daemon unavailable)
- Runtime HTTP/CORS smoke: **PASS** (`GET /` → 200; `GET /api/meetings` → 200; configured origin allowed, unlisted origin denied)
- Real STT RU/EN: **PASS** — RU `ru`, 4 508 символов; EN `en`, 3 325 символов
- Real DeepSeek RU/EN summaries: **PASS** — оба статуса `ready`, конспекты сохранены локально
- AI eval mocks/schema: **PASS**; grounding: **PARTIAL**, требуется ручная сверка по исходной записи
- Secrets/privacy scan: **PASS** — repository files and Pro ZIP checked for recognizable secrets, local data/media and non-placeholder Drive file URLs
- Vercel frontend build: **PASS** — `node scripts/build_frontend.mjs` generated `frontend-dist` with HTTPS API base
- Clean Lite package install/runtime: **PASS** — Lite ZIP распакован отдельно, setup создал venv и установил runtime-зависимости; `/` и `/api/meetings` ответили 200
- GitHub Stage 4: **PASS** — commit `8a3a933` из `feature/stage4-showcase` прошёл GitHub Actions (run `42276091985`, все checks success) и слит через PR #3; merge commit `0fd1333`. Tag `dz-lite-v1` не перемещался.

## Формат сдачи

Для Lite `package-lite.ps1` собирает отдельный ZIP из подтверждённого `dz-lite-v1`; для Pro `package.ps1` собирает отдельный ZIP по allowlist. Финальная проверка архивов выполняется после их пересборки. Публикация не выполняется без отдельного подтверждения.

## DZ Pro — облачный импорт

| Требование | Статус | Доказательство/ограничение |
|---|---|---|
| Ссылка и импорт из одного облака | **PASS (live E2E)** | Анонимный Google Drive download завершён: WebM, 11,484,674 байта; валидна EBML/WebM сигнатура. Персональная ссылка не сохраняется в исходниках и материалах сдачи. |
| Проверка URL, SSRF и redirects | **PASS (unit + live)** | Только HTTPS Drive share URLs; download redirects ограничены и каждый переход проверяет Google host и публичный IP. Unit тест блокирует redirect на внешний домен; live Google `303` → `drive.usercontent.google.com` прошёл проверку. |
| MP4/WebM, размер и время | PASS (unit) | Потоковое чтение с лимитом MAX_UPLOAD_MB, timeout и deadline; проверка metadata, HTML и file signature. Моками проверены превышение размера и HTML. |
| Повторное использование Lite pipeline | **PASS (live E2E)** | По скачанному файлу реально выполнен Faster-Whisper, затем один реальный вызов DeepSeek; фазы прошли `downloading → transcription → ai → ready`. |
| Этапы, источник, историю | **PASS (live E2E)** | `source=cloud`, результат и английская транскрипция сохранены в SQLite; GET страницы, списка и карточки после обработки вернули встречу со статусом `ready`. |
| Защита от повторного анализа | **PASS (live E2E)** | Повтор той же нормализованной ссылки вернул ту же встречу с `duplicate=true`; число DeepSeek запросов осталось 1. |
| GitHub и Vercel статус | **PASS / URL follow-up** | Private GitHub repo сохранён; Vercel status на `main` success. Учительский backend не публиковался. Публичный frontend domain ещё не записан; branch protection для private repo недоступна текущему плану GitHub (403; не обходилась). |

### Живой Cloud E2E — 2026-11-06

- **PASS:** настоящая публичная запись получена из Google Drive по редиректу `303 → 200`; скачано 11,484,674 байта. Проверены WebM filename/расширение и EBML сигнатура файла.
- **PASS:** приложение извлекло аудио и Faster-Whisper `small` реально обработал аудио длительностью 4:02; автоматически определён `en` (p=0,99), транскрипция — 3,325 символов.
- **PASS:** выполнен ровно **1** реальный запрос DeepSeek, HTTP 200. Usage из API: prompt 1,106; completion 282; total **1,388 токенов**. Новых запросов после него не было.
- **PASS:** конспект сохранён в локальной БД; краткое содержание непустое, поля решений, задач и открытых вопросов имеют требуемый список-текстовый формат. Перезагрузка страницы, повторное чтение списка и открытие карточки подтвердили сохранность результата.
- **PASS:** повторное добавление той же ссылки открыло ту же встречу; число AI-запросов осталось 1.
- **PARTIAL — проверка groundedness:** ручная EN сверка завершена ниже; числовые утверждения соответствуют формулировкам транскрипта, но транскрипт сам внутренне не сходится по сумме запросов. Строгая проверка совпадения значимых слов не прошла; поэтому автоматическая эвристика не подтверждает точность, хотя ручное сопоставление основных утверждений с протоколом прошло.
- Общее время сценария до проверки дубликата: **632.19 с** (включая реальное скачивание, локальную обработку и проверки persistence/dedup).
- Первая попытка до этого запуска завершилась сетевой ошибкой в ограниченном окружении до AI-вызова (0 DeepSeek calls). Восстановлен и повторно использован тот же тестовый cloud record; второй анализ по другой ссылке или автоматический платный retry не выполнялся.
- Секреты, URL, ID Drive и тексты встречи не внесены в документацию, Git или ZIP.

### Смысловая сверка сохранённого EN summary — без повторного AI-вызова

Сохранённые транскрипция и summary проверялись вручную без повторного обращения к DeepSeek. Проверка выявила ошибку распознавания имени собственного, внутреннее арифметическое противоречие в устной речи и спорную классификацию категории. Согласованные задачи, исполнители и сроки отдельно не подтверждались. Сохранённый результат SQLite не редактировался. Конкретные имена, предмет разговора, транскрипт и Drive-ссылка в пакет не включены из-за неподтверждённых прав на исходное видео.

Для будущих запусков уточнено правило prompt: не помещать нерешённость в `decisions`, не выводить вопросы из критики, не исправлять имена по внешним источникам и отмечать арифметические противоречия. Добавлен регрессионный тест; **реальный анализ по изменённому prompt не запускался**.

Редакторская версия исходного результата остаётся локальным внутренним документом и не включается в публичный Showcase или Pro ZIP. Showcase демонстрирует отдельный вымышленный пример.

## Согласованные будущие режимы демонстрации

- Требования к Teacher Live Demo и Public Showcase записаны в `DEMO_MODES.md`. Teacher Preview auth, двуханализная постоянная квота, лимиты запросов/загрузок/AI, отдельная demo SQLite, срок и kill switch реализованы в коде текущей feature branch.
- Teacher Demo выключен, backend не опубликован и Cloudflare tunnel не активирован. Сквозная обработка через Vercel Preview и долгий background job через интернет не проверены. Public Showcase остаётся статическим build mode без API URL.

### Безопасность журналов и итоговый тестовый прогон

- HTTPX/HTTPCore logger families (`httpx`, `httpcore`, `httpx2`, `httpcore2`) и Uvicorn access logger отключены; приложение журналирует только тип события/исключения, без URL, IP и ID встречи. Системные журналы не удалялись.
- Тесты `tests/test_logging_privacy.py` проверяют подавление HTTP request logs и отсутствие фиктивных URL, bearer/API key и ID встречи в журнале ошибки облачного импорта.
- Итоговый Quality Gate: pytest **28 passed**, Ruff **PASS**, compileall **PASS**, JavaScript syntax и frontend build **PASS**, секреты/архив **PASS**, `git diff --check` **PASS**. Ни один тест не выполняет реальный API-вызов.
- Stage 3 local preflight повторил полный набор: **28 passed**, Ruff PASS, compileall PASS, JS syntax/frontend build PASS, repository/archive security scan PASS. На Windows использован свежий pytest temp-каталог; фиксированный `--basetemp` удалён из GitHub Actions workflow. GitHub Actions `checks` прошёл на PR и post-merge `main` (runs `42262127724`, `42262426419`).

## Stage 4 — Showcase и подготовка Vercel

| Критерий | Статус | Доказательство / ограничение |
|---|---|---|
| Статический Showcase build | **PASS (local)** | Vercel config использует guarded `--vercel`; по умолчанию build — Showcase, только явно настроенный Vercel Preview может собрать Teacher Preview. Сборка Showcase не содержит backend API URL. |
| Подготовленные RU/EN примеры и сравнение версий | **PASS (local)** | `static/demo-data.json` содержит две явно вымышленные беседы, их транскрипции и отдельно подписанные исходный пример/редакторскую версию. Права на реальные записи не требуются, реальные тексты не опубликованы. |
| Запросы Showcase | **PASS (local harness + static HTTP)** | Node harness увидел ровно один запрос `/static/demo-data.json`; запросов к `/api` нет. Через локальный HTTP-сервер главная страница и demo JSON дали 200, `/api/meetings` — 404. Живой публичный URL ещё не проверен. |
| Обновление страницы | **PASS (local harness)** | Тест проверил сохранение выбранной встречи и версии summary в localStorage после повторной инициализации. |
| Обычный Lite/Pro frontend | **PASS (mode checks)** | Live build остаётся по умолчанию; тест проверяет, что ручная загрузка и форма Google Drive имеют активные обработчики, а live mode продолжает обращаться к истории `/api/meetings`. |
| Браузер и мобильная ширина | **PASS (local Chrome/CDP)** | Проверены desktop RU/EN и mobile viewport 390 px. В CDP `innerWidth=390`, `scrollWidth=390`; мобильные карточки переключены в один столбец, горизонтального переполнения нет. Скриншоты лежат в `docs/showcase/`; они не доказывают публичный deployment. |
| Публичный Vercel URL и расходы | **DEPLOYMENT STATUS SUCCESS / DOMAIN MISSING** | GitHub Vercel check на `main` success и указывает на [deployment record](https://vercel.com/vitali7/ai-video-meeting-analyzer/B9fwJxhThQBua2XWTk4XMe1Vbey3). Check API не сообщает публичный frontend domain; владелец должен записать фактический URL. Платный upgrade не запрашивался, план требует подтверждения в dashboard. |
| Teacher Live Demo | **GUARDED LOCALLY / NOT ACTIVATED** | Auth, quota 2, limits, 5–7-day server expiry, isolated database and kill switch implemented. Backend/tunnel/deployment not activated or public-tested. |

Stage 4 local checks were **28 pytest passed** (без внешних API), Ruff PASS, compileall PASS по `meeting_analyzer`, `tests` и `scripts`, Node syntax PASS, Showcase/live mode harness PASS, frontend build isolation PASS, security scanner PASS по репозиторию и ZIP. ZIP contained 52 entries without `.env`, DBs, media, models or `node_modules`. Stage 5 guard implementation has its own final Quality Gate recorded below after completion.

## Stage 5 — Teacher Preview guardrails и финальная подготовка сдачи

| Проверка | Результат | Примечания |
|---|---|---|
| Полный pytest | **35 passed** | Использована изолированная `.quality-venv`; временный каталог потребовал разрешённого Windows доступа. Никаких реальных AI/API вызовов. |
| Teacher backend auth | **PASS** | Неавторизованные list/detail/manual/cloud/status запросы получают 401 до парсинга request body. Login доступен только с лимитом попыток; токен подписан HMAC и не хранится в browser storage. |
| Постоянная квота | **PASS** | Два анализа максимум на весь срок; третий отклоняется, SQLite сохраняет счётчик после создания нового Guard. Повтор той же Google Drive ссылки не расходует слот. Пайплайн в тестах замокан. |
| Отдельные demo данные | **PASS** | Конфигурация использует отдельный путь `.teacher-demo-data`; тест сверяет, что он не совпадает с личной базой. Каталог добавлен в `.gitignore`. |
| Размер и AI лимиты | **PASS** | Streaming body limit работает без Content-Length; размеры конфигурации ограничены 100 MB, transcript 8,000 chars, prompt 32,000 UTF-8 bytes, output 600 tokens. Ни один тест не отправлял запрос DeepSeek. |
| Срок и выключение | **PASS (tests)** | По умолчанию 5 дней; config запрещает срок выше 7. Срок фиксируется один раз, HMAC токен не превышает 8 часов; expiry и kill switch тестируются. |
| Showcase/Teacher frontend isolation | **PASS** | Node harness: Showcase не вызывает `/api`, Teacher UI не делает запросов до входа и не сохраняет bearer token; Lite/Pro формы остаются на месте. |
| Frontend build modes | **PASS** | `--vercel`: Production остаётся Showcase; Teacher Preview доступен только с Preview env guard и HTTPS backend URL. Showcase исключает API URL; Teacher Preview исключает synthetic public demo JSON. |
| Python quality | **PASS** | Ruff и compileall прошли по `meeting_analyzer`, `tests`, `scripts`. |
| JS/build checks | **PASS** | Node syntax, Showcase harness и `verify_frontend_build.mjs` прошли. Итоговый локальный `frontend-dist` восстановлен как Showcase. |
| Runtime/API | **PASS (mocked TestClient)** | Auth, status, upload/processing quota и duplicate flows проверены TestClient без сети/DeepSeek. Публичный tunnel/API smoke не выполнялся. |
| Публичное доказательство Cloud E2E | **PENDING** | Ранее фактический Cloud E2E прошёл, но право демонстрации исходной записи не подтверждено и промежуточные screen frames не были записаны. Нет публикации реальных материалов. |

Teacher Live Demo, локальный FastAPI в публичном доступе, Cloudflare tunnel и Vercel Teacher Preview **не активированы**. Новых платных AI вызовов не было. Инфраструктурные платные сервисы не подключались. Состояние репозитория: **NOT SAFE** для временного переключения на Public из-за личных author identities в достижимой истории; private сохраняется.
