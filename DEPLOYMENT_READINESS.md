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

## Подготовленные локальные файлы

- `vercel.json` собирает статический frontend командой `node scripts/build_frontend.mjs`.
- `scripts/build_frontend.mjs` принимает `PUBLIC_API_BASE_URL`, проверяет HTTPS и создаёт runtime-конфиг без секретов.
- `Dockerfile` собирает Python backend и запускает его на `0.0.0.0:8000` с постоянным `/data`.
- `.dockerignore` исключает исходное видео, базы, ключи, модели и локальное окружение из Docker context.
- `.github/workflows/quality.yml` запускает тесты, Ruff, compileall, JS/build и проверку секретов при PR в `main` и push в `main`.
- `CORS_ALLOWED_ORIGINS` допускает только перечисленные origins; при пустом значении CORS не включается.

## Ограничения и безопасность

Сейчас backend не имеет пользовательской аутентификации и rate limit; публичное размещение не готово. CORS ограничивает браузерные вызовы, но не блокирует curl/других HTTP-клиентов. Перед публикацией нужны серверная OIDC/JWT аутентификация и проверка владельца каждой встречи, per-user upload/request limits, дневные/месячные AI spending caps, HTTPS/TLS, защита от abuse, проверенные backup/restore и журналы без IP/URL/record ID. CORS должен точно ограничивать origin frontend, но является только дополнительной защитой. API keys и bearer secrets держать только в backend secrets.

SQLite и один in-process background worker подходят для single-instance учебного показа, но не для горизонтального масштабирования или высокой доступности. Перезапуск во время обработки завершает текущую задачу ошибкой; durable queue не реализована. Перед multi-user production потребуется отдельное архитектурное решение по очереди и базе данных.

Vercel раздаёт только frontend: Python, Whisper и длительный AI pipeline там не запускаются. Реальный E2E выполнен локально; его результат и ограничения приведены в `ACCEPTANCE.md`.

## GitHub статус

Локально создана ветка `feature/dz-pro`; тег `dz-lite-v1` указывает на подтверждённый Lite checkpoint `e56ba54`. Подключённый GitHub login подтверждён как `vitaliov-hash`; точного репозитория проекта среди доступных в аккаунте нет. Remote отсутствует, поэтому URL, Actions run, Pull Request и защита `main` ещё не настроены. Workflow подготовлен, но станет CI только после создания private repository и branch rules/required checks. Push и публикация не выполнялись.

После отдельного согласования создайте Private repo `AI-Video-Meeting-Analyzer` без README/.gitignore/license. Подключение и push команд:

```powershell
git remote add origin https://github.com/vitaliov-hash/AI-Video-Meeting-Analyzer.git
git push -u origin dz-lite-v1:refs/heads/main
git push -u origin feature/dz-pro
```

Первая команда push создаёт `main` из исторически сохранённого Lite tag; вторая отправляет Pro feature branch. Эти команды подготовлены, но не запускались. Затем открыть PR `feature/dz-pro` → `main`, проверить Actions и review; не использовать auto-merge.

## Действия перед подключением/публикацией

1. Выбрать VPS/Docker hosting и проверить его актуальные цену, доступность постоянного диска, регион и ограничения времени/CPU.
2. Подтвердить создание private GitHub repository, подключить remote и отправить только проверенные исходники.
3. Включить Pull Request workflow и required checks, настроить защиту `main` в возможностях выбранного GitHub plan.
4. Создать Vercel project для статического frontend и задать `PUBLIC_API_BASE_URL`.
5. Создать backend service с постоянным volume, HTTPS и точным `CORS_ALLOWED_ORIGINS`; добавить API key в backend secrets.
6. До передачи публичной ссылки добавить и проверить серверную аутентификацию/rate limits и подтвердить права на демонстрационное видео.
7. Выполнить deployment и end-to-end smoke только после отдельного подтверждения конкретных ресурсов, расходов и публичной видимости.

Ни GitHub remote, ни hosting project, ни публичный deployment пока не создавались.
