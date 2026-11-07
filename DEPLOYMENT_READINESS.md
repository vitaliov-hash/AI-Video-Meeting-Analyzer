# Статус подготовки GitHub и Vercel

## Рекомендуемая минимальная архитектура

Полный живой Pro E2E уже пройден локально: Google Drive → WebM → Faster-Whisper → один DeepSeek summary → SQLite → reload/dedup. Никакие платные AI calls не нужны для следующих локальных проверок.

Одна кодовая база с двумя deployment surfaces:

1. Vercel раздаёт только статические HTML/CSS/JavaScript файлы из `frontend-dist`.
2. Один Python Docker backend работает на VPS или другом постоянно работающем Docker hosting с постоянным томом `/data`.
3. Backend сохраняет SQLite и кэш Whisper в `/data`; входные видео удаляются после обработки. DeepSeek/OpenAI/Gemini credentials задаются только в секретах backend hosting.
4. `PUBLIC_API_BASE_URL` — публичный HTTPS origin API, это несекретная build variable Vercel. `CORS_ALLOWED_ORIGINS` на backend ограничивается точным origin опубликованного frontend.

Этот вариант использует уже существующий FastAPI, SQLite и один worker, поэтому сохраняет каноническую кодовую базу и минимизирует число платных компонентов. Отдельные managed database, bucket и очередь не нужны для одиночной учебной демонстрации.

## Варианты хостинга и ориентировочная цена (проверено 2026-11-06)

| Компонент | Вариант | Ориентировочная стоимость | Примечания |
|---|---|---:|---|
| Frontend | Vercel Hobby | $0/мес | Для персонального некоммерческого проекта. Vercel Pro указан как $20/мес, если понадобится коммерческое использование или командные функции. Цены в USD без налогов. [Vercel pricing](https://vercel.com/pricing) |
| Python backend + модель + SQLite | DigitalOcean Basic Droplet, 2 vCPU / 4 GiB / 80 GiB SSD | $24/мес | Включены локальный диск и transfer; сервер администрируется самостоятельно. Дополнительный block volume — $0.10/GiB-месяц. [Droplet prices](https://www.digitalocean.com/pricing/droplets), [Volume prices](https://docs.digitalocean.com/products/volumes/details/pricing/) |
| Более управляемый backend | Render web service, 2 CPU / 4 GB | $0.40/час, примерно $288 за 720 часов; диск $0.25/GB-месяц | Удобнее управлять, но постоянная работа существенно дороже. Persistent disk доступен на платных compute services. [Render pricing](https://render.com/pricing), [Persistent disks](https://render.com/docs/disks) |

Оценка не включает налоги, домен, резервные копии, egress сверх квоты и стоимость AI вызовов. Тариф зависит от региона/аккаунта и может измениться; до создания платного ресурса перепроверьте сумму в панели провайдера. Для одной учебной демонстрации рекомендован DO Droplet при готовности администрировать VPS.

## Stage 4 — бесплатный статический Showcase

Stage 4 добавила Showcase build на базе одной кодовой базы. Сейчас `vercel.json` использует guarded `node scripts/build_frontend.mjs --vercel`; без Preview guard variables сборка остаётся Showcase, не включает API URL и кладёт только HTML, CSS, JavaScript и синтетический JSON с RU/EN примерами. Из Vercel bundle исключены Python API, локальная SQLite, видео, модель, DeepSeek ключ и пользовательские транскрипты.

Showcase запрашивает только `/static/demo-data.json`; добавление/импорт записи и polling `/api/meetings` отключены. Это статические фиктивные примеры, не результаты AI, полученные опубликованным сайтом. Проверки сборки и поведения добавлены в CI. GitHub Vercel check на `main` сообщил success; точный публичный URL и тариф всё ещё нужно подтвердить перед отправкой handout. Не переходить на тариф, который требует карту или оплату.

По актуальным официальным правилам Vercel Hobby бесплатен, предназначен для личного некоммерческого использования; персональный GitHub-репозиторий можно подключить владельцу аккаунта. Репозиторий проекта принадлежит личной учётной записи GitHub, не организации. Учебный Showcase предполагается некоммерческим. [Vercel Hobby](https://vercel.com/docs/plans/hobby), [Terms](https://vercel.com/legal/terms), [GitHub integration](https://vercel.com/docs/git/vercel-for-github), [private repositories](https://vercel.com/docs/git#deploying-private-git-repositories).

Это подтверждает публичные правила, но **не фактическое состояние тарифа существующего аккаунта пользователя**. Перед созданием проекта план нужно проверить в Vercel Dashboard; если панель предлагает upgrade, карту или платный тариф, остановиться.

## Подготовленные локальные файлы

Согласованные будущие режимы (не развёрнуты) описаны в `DEMO_MODES.md`: Teacher Live Demo ограничен 5 днями (максимум 7) с серверным истечением и квотами; Public Showcase показывает готовые RU/EN примеры без платных AI-вызовов и без публично вызываемых endpoints анализа. `DEMO_SUMMARY_EN_REVIEWED.md` — отдельная редакторская EN-демонстрация; исходные AI-результаты не менялись.

- `vercel.json` собирает безопасный Showcase через `node scripts/build_frontend.mjs --showcase`.
- `scripts/build_frontend.mjs` сохраняет обычный live frontend build для локальной интеграции, но Showcase запрещает `PUBLIC_API_BASE_URL`.
- `scripts/test_showcase_mode.mjs` проверяет RU/EN историю, смену версии summary, отсутствие запросов к `/api` и сохранение выбора после перезагрузки; `scripts/verify_frontend_build.mjs` проверяет изоляцию артефактов обоих режимов.
- `Dockerfile` собирает Python backend и запускает его на `0.0.0.0:8000` с постоянным `/data`.
- `.dockerignore` исключает исходное видео, базы, ключи, модели и локальное окружение из Docker context.
- `.github/workflows/quality.yml` запускает тесты, Ruff, compileall, JS/build и проверку секретов при PR в `main` и push в `main`.
- `CORS_ALLOWED_ORIGINS` допускает только перечисленные origins; при пустом значении CORS не включается.

## Ограничения и безопасность

Сейчас backend не имеет пользовательской аутентификации и rate limit; публичное размещение не готово. CORS ограничивает браузерные вызовы, но не блокирует curl/других HTTP-клиентов. Перед публикацией нужны серверная OIDC/JWT аутентификация и проверка владельца каждой встречи, per-user upload/request limits, дневные/месячные AI spending caps, HTTPS/TLS, защита от abuse, проверенные backup/restore и журналы без IP/URL/record ID. CORS должен точно ограничивать origin frontend, но является только дополнительной защитой. API keys и bearer secrets держать только в backend secrets.

SQLite и один in-process background worker подходят для single-instance учебного показа, но не для горизонтального масштабирования или высокой доступности. Перезапуск во время обработки завершает текущую задачу ошибкой; durable queue не реализована. Перед multi-user production потребуется отдельное архитектурное решение по очереди и базе данных.

Vercel раздаёт только frontend: Python, Whisper и длительный AI pipeline там не запускаются. Реальный E2E выполнен локально; его результат и ограничения приведены в `ACCEPTANCE.md`.

## Stage 5 — временный Teacher Preview за $0 (не активирован)

Текущий код подготовки: отдельная закрытая Teacher Preview сборка Vercel Preview + loopback Python/Faster-Whisper backend на Windows + временный Cloudflare Quick Tunnel + `.teacher-demo-data` SQLite. Персональная база не открывается, DeepSeek key остаётся только в локальном backend `.env`, Public Showcase остаётся статическим. Этот режим не является production и не имеет SLA.

Защитные ограничения в backend: обязательный bearer token на всех API, login/API rate limits, streamed request cap, максимум 2 новых анализа на срок, максимум 100 MB на видео, максимум 8 000 символов транскрипта, 32 000 UTF-8 bytes AI prompt и 600 output tokens. Срок задаётся 5 суток и не может превышать 7; состояние хранится между перезапусками. Kill switch создаёт локальный файл отключения. Режим не включался, публичный tunnel и длительный worker не проверялись.

Для короткой supervised проверки понадобится: отдельный Vercel Preview project/environment; переменная `TEACHER_PREVIEW_BUILD=1` только в Preview; `PUBLIC_API_BASE_URL` с актуальным HTTPS адресом Quick Tunnel; точный Preview origin в backend `CORS_ALLOWED_ORIGINS`; `TEACHER_DEMO_ENABLED=true`, `MAX_UPLOAD_MB=100`, локальные сильные пароль/секрет и действующий серверный `DEEPSEEK_API_KEY`. Любые credentials добавляются только в Windows backend `.env` или Vercel non-secret Preview vars, не Git. Проект и tunnel не активируются без отдельного решения владельца. Чтобы немедленно выключить API во время демонстрации, запустить `python -m meeting_analyzer.teacher_demo --disable`; для остановки всего backend завершить его локальный процесс и tunnel.

Cloudflare Quick Tunnel — бесплатный временный URL для разработки/тестирования; он прекращается при остановке процесса и не является стабильным production endpoint. Для Vercel Hobby учитывайте текущие условия персонального некоммерческого использования; текущий домен и план в этой сессии отдельно не проверены. [Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectivity-options/), [Vercel Hobby](https://vercel.com/docs/plans/hobby), [Vercel Terms](https://vercel.com/legal/terms).

## Финальная сдача и публичный риск

Git repository verdict для переключения visibility: **NOT SAFE**. В полном достижимом Git history есть личные author identities, а история может быть скопирована до возврата репозитория в Private. Оставить исходный repository private. Если публичный код нужен для оценки, подготовить отдельный очищенный репозиторий с минимальной новой историей и без пользовательских материалов.

GitHub Vercel commit status на актуальном `main` (`16fd1363b617d703de184aab33323d6d06ea04ea`) равен success и указывает на [deployment record](https://vercel.com/vitali7/ai-video-meeting-analyzer/EFphwsEGzyXtoC7awCSFw1eAs8iZ). Публичный frontend domain из status API получить нельзя; владелец должен внести его в `TEACHER_HANDOUT.md`. GitHub API и CLI сообщают visibility исходного repo `Public`; владелец выбрал не менять её сейчас. История признана NOT SAFE для распространения, поэтому преподавателю не отправлять этот репозиторий как безопасный submission source; при необходимости подготовить отдельный очищенный repository. Права на прошлую реальную E2E запись не подтверждены, поэтому снимки и запись экрана из неё не публиковать. Полный live proof остаётся требованием до окончательного закрытия сдачи; новых платных запросов не выполнялось.

## GitHub статус

Приватный репозиторий: [AI-Video-Meeting-Analyzer](https://github.com/vitaliov-hash/AI-Video-Meeting-Analyzer). В нём `main` из Lite checkpoint, `feature/dz-pro` с Pro, сохранённый tag `dz-lite-v1`. PR #1 прошёл все CI шаги и слит обычным merge commit `80e15afe303431df2a29e2076874ec539e18217c`. CI run IDs: `42262127724` (PR), `42262426419` (post-merge `main`); оба завершились success.

Защита `main` не включена: GitHub API отказал с HTTP 403 и сообщением, что branch protection для приватного репозитория требует GitHub Pro. Публичность не включалась, ограничение плана не обходилось. Слияние сделано только после успешного PR CI. Рабочее дерево чистое; local `main` синхронизирована с remote.

## Актуальный статус и оставшиеся действия владельца

1. Уточнить публичный `*.vercel.app` URL у владельца и внести его в `TEACHER_HANDOUT.md`; GitHub Vercel deployment status на текущем `main` success, но не раскрывает frontend domain.
2. Если преподавателю нужен GitHub access, пригласить его аккаунт в private repo; не менять visibility исходного проекта.
3. Подтвердить права/согласие на демонстрационный источник или предоставить новый разрешённый MP4/WebM. Права на прежний live E2E клип не подтверждены.
4. Для записи статусов полного нового E2E понадобится ещё один DeepSeek вызов; он не выполнялся и требует отдельного согласования. Если права подтвердятся для прежнего результата, новые кадры финальной persistence/dedup можно сделать без нового анализа, но исторические промежуточные состояния не сохранены.
5. Teacher Preview, Cloudflare tunnel и backend не включать до отдельного согласования владельца.

## Итоговая проверка сдачи — 2026-11-07

- [Текущий Vercel Showcase](https://ai-video-meeting-analyzer.vercel.app) отвечает HTTP 200. Он остаётся статическим и не содержит доступного API обработки.
- Основной [GitHub repository](https://github.com/vitaliov-hash/AI-Video-Meeting-Analyzer) сейчас **Public** по решению владельца. Предыдущий аудит выявил author metadata в истории; история не переписывалась. Преподавателю дана публичная ссылка согласно решению владельца.
- Настоящее Cloud E2E записано в `dist/DZ-Pro-Final-Submission`: WebM SHA-1 совпадает с Commons PD-USGov источником; Faster-Whisper `tiny/int8` определил английский; один DeepSeek вызов успешно вернул структурированный результат; reload и повторная ссылка прошли без второго анализа. Видео/PNG не коммитятся.
- Запись сделана локально и защищённо, без публичного tunnel. Постоянный Showcase не подключён к backend. Будущий Teacher Preview остаётся выключенным и активируется только владельцем по инструкции в финальной папке; бесплатный Quick Tunnel нестабилен, поэтому для сдачи достаточно приложенного live proof.
- Общая длительность 341.541 s; ускоренное короткое видео прямо помечает ×16, raw оригинал сохранён. Точное число токенов этого вызова не доступно, поскольку adapter не пишет API usage поле.
- Для infrastructure использованы уже существующие бесплатные GitHub/Vercel и локальный компьютер; новых платных хостингов, тарифов или подписок нет.
