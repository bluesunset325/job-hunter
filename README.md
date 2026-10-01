# Job Hunter

Локальный сервис для поиска удалённой работы и фриланса для Python-разработчика.
Каждые 30 минут собирает вакансии и заказы с десятка площадок, отсеивает
неподходящее, оценивает соответствие резюме через локальную LLM (Ollama) и
присылает лучшие карточки в Telegram. Откликаешься сам: бот не отправляет отклики
и не входит в аккаунты на площадках.

Автор: [github.com/bluesunset325](https://github.com/bluesunset325)

## Площадки

| Тип | Площадки |
|---|---|
| Работа (Россия) | hh.ru (RSS), Habr Career, GetMatch |
| Удалёнка (мир) | RemoteOK, We Work Remotely, Himalayas |
| Фриланс (Россия) | Kwork, FL.ru |
| Фриланс (мир) | Freelancer.com, PeoplePerHour, Remotive, Jobicy (только проекты и контракты) |
| Опционально | Telegram-каналы с вакансиями (Telethon) |

Используются только публичные страницы и открытые API.

## Как это работает

```
источники ──► SQLite (дедуп) ──► префильтр ──► Ollama: оценка 0–100 ──► Telegram-карточки
```

- **Дедупликация**: одна и та же вакансия с разных площадок не приходит дважды.
- **Префильтр** без LLM: ключевые слова и стоп-слова, минимальная зарплата,
  минимальный бюджет для зарубежного фриланса ($50, почасовые от $10/ч).
- **Оценка**: модель сравнивает вакансию с резюме и возвращает JSON с баллом,
  кратким «почему подходит» и красными флагами.
- **Карточка** в Telegram с кнопками ⭐ / ✅ Откликнулся / 🙈 Скрыть.
- Падение одной площадки не мешает остальным; после 3 падений подряд приходит
  одно предупреждение.

## Стек

Python 3.12, asyncio, aiohttp, aiogram 3, Telethon, SQLite (WAL), Ollama
(по умолчанию `qwen3:14b`), pytest (тесты на реальных ответах площадок), launchd.

## Установка

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
cp resume.example.md resume.md
```

1. **Бот**: @BotFather → `/newbot` → токен в `.env` (`JH_BOT_TOKEN`).
2. **chat_id**: напиши @userinfobot → число в `config.yaml` → `telegram.chat_id`.
   Затем отправь своему боту `/start`.
3. **Резюме**: впиши своё в `resume.md` (файл в `.gitignore`), свои предпочтения —
   в `candidate_notes` в `config.yaml`.
4. **Ollama**: `ollama pull qwen3:14b`, Ollama должна быть запущена.
5. *(опционально)* **Telegram-каналы**: api_id/api_hash с https://my.telegram.org → `.env`,
   `python -m sources.telegram --login`, каналы в `telethon.channels`, `sources.telegram: true`.

## Запуск

```bash
.venv/bin/python run_once.py   # один прогон сбора и оценки
.venv/bin/python bot.py        # кнопки и команды
```

## Автозапуск (macOS)

В `launchd/*.plist` замени `/path/to/job-hunter` на путь к проекту, затем:

```bash
mkdir -p logs
cp launchd/*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.jobhunter.run.plist
launchctl load ~/Library/LaunchAgents/com.jobhunter.bot.plist
```

Остановить: `launchctl unload ~/Library/LaunchAgents/com.jobhunter.*.plist`.

## Настройка

`config.yaml`: ключевые и стоп-слова, минимальная зарплата и бюджет, порог оценки,
лимиты за прогон, включение площадок.

Подбор порога оценки по ручной разметке:
`python -m tools.scorer_eval export` → разметить `tests/scorer_eval.yaml` →
`python -m tools.scorer_eval run`.

## Команды бота

`/top` — лучшие за сутки · `/starred` — избранное · `/all` — ниже порога ·
`/stats` — статистика по площадкам · `/pause`, `/resume` — пауза рассылки.

## Тесты

```bash
.venv/bin/pytest -q
```
