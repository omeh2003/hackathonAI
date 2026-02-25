# Polymarket AI Analyst — MCP Server

MCP сервер для поиска и анализа успешных трейдинговых ботов на Polymarket.

## Инструменты (Tools)

### find_top_traders
Поиск топ-N трейдеров по прибыльности с детекцией ботов.

**Параметры:** `limit` (1-50), `timeframe` ("7d" | "30d" | "all_time")

**Выход:** `[{profile_id, pnl, is_bot}]`

### analyze_trader_strategy
Анализ стратегии конкретного трейдера.

**Параметры:** `profile_id` (wallet 0x... или @username)

**Выход:** `{strategy_description, risk_level, risk_justification, success_score, is_bot}`

### generate_batch_report
Батч-отчёт по массиву профилей.

**Параметры:** `profile_ids` (array of strings)

**Выход:** `[{profile_id, pnl, risk_level, success_score, is_bot}]`

## Быстрый старт (Docker)

```bash
# Сборка
docker build -t polymarket-mcp .

# Запуск MCP сервера (HTTP, порт 8000)
docker run -p 8000:8000 --env-file .env polymarket-mcp

# Или через docker compose
cp .env.example .env
docker compose up

# Генерация JSON-артефактов из реальных данных
docker compose run --rm artifact-generator
```

## Конфигурация (.env)

```
POLYMARKET_DATA_API_BASE=https://data-api.polymarket.com
POLYMARKET_GAMMA_API_BASE=https://gamma-api.polymarket.com
REQUEST_TIMEOUT=30
MAX_CONCURRENCY=5
LOG_LEVEL=INFO
MCP_TRANSPORT=http          # http или stdio
MCP_HOST=0.0.0.0
MCP_PORT=8000
BOT_DETECTION_THRESHOLD=0.6
CACHE_TTL=300
```

## Разработка

```bash
# Установка зависимостей
uv sync --dev

# Запуск тестов
uv run pytest tests/ -v

# Запуск сервера локально
PYTHONPATH=src uv run python -m polymarket_mcp

# Генерация артефактов локально
PYTHONPATH=src uv run python scripts/generate_artifacts.py
```

## Архитектура

```
Tools (тонкие, Pydantic) → Service (оркестрация) → Core (чистая логика)
                                   ↓
                             Adapters (httpx клиент)
```

- **Core:** BotDetector (5 эвристик), StrategyAnalyzer (rule-based), PnlCalculator
- **Service:** TraderService — оркестрация API + анализ
- **Adapters:** PolymarketClient — retry, кеш, rate limiting
- **Tools:** FastMCP @mcp.tool с Pydantic-валидацией

## Стек

Python 3.12, FastMCP 3.0, httpx, pydantic, pydantic-settings, structlog, tenacity, pytest, respx, Docker, UV
