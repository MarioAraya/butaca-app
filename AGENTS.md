# AGENTS.md

This file provides guidance to AI coding agents (including Google Antigravity / `agy`) when working with code in this repository.

## Comandos comunes

```bash
# Instalar dependencias (incluye dev)
pip install -e ".[dev]"

# Instalar browser para Playwright
playwright install chromium

# Correr la API localmente (con hot reload)
uvicorn src.main:app --reload --port 8000

# Correr tests
pytest

# Correr un test específico
pytest tests/test_foo.py::test_bar -v

# Levantar con Docker (desarrollo) — API en :8000, frontend en :5175
docker compose up -d

# Levantar con Docker (producción, requiere red externa `proxy`)
docker compose -f docker-compose.prod.yml up -d

# Resetear base de datos
docker compose down && rm -rf ./data/ && docker compose up -d

# Rebuild solo el frontend (después de cambios en frontend/)
docker compose build frontend && docker compose up -d frontend
```

## Arquitectura

API REST en FastAPI + frontend Preact/Vite. Los datos vienen de scrapers que corren una vez al día (cron via APScheduler).

### Pipeline de scraping

**Cinépolis (dos fases):**
1. **Fase 1 — `src/scraper/api_client.py`**: Llama a la API interna de Cinépolis (`GetNowPlayingByCity`) — películas + horarios en un solo request JSON.
2. **Fase 2 — `src/scraper/detail.py`**: Por cada película, visita la página de detalle con httpx+BeautifulSoup para obtener sinopsis y géneros.

**Normandie (`src/scraper/normandie.py`):**
- HTML scraper de `https://normandie.cl/cartelera/` (WordPress, server-rendered).
- Parsea `div.contenedorcartelera` → semanas → días → horarios.
- Slugs prefijados `normandie-*` para evitar colisiones con Cinépolis.
- Sin fase de detalle: solo título + horarios. Trailer buscado vía YouTube.

El orquestador (`src/scraper/orchestrator.py`) coordina ambas fases, hace upsert de películas y reemplaza todos los horarios de cada película en cada ejecución. Los errores por película no abortan el scrape completo: se registran en `ScrapeLog`.

### Estructura de módulos

- `src/main.py` — punto de entrada FastAPI, configura lifespan (crea tablas, arranca scheduler)
- `src/config.py` — settings via `pydantic-settings` (lee del `.env`)
- `src/api/router.py` — todos los endpoints REST
- `src/api/schemas.py` — schemas Pydantic de respuesta
- `src/db/models.py` — modelos SQLAlchemy: `Movie`, `Cinema`, `Showtime`, `ScrapeLog`
- `src/db/engine.py` — engine SQLite + `SessionLocal`
- `src/db/migrations.py` — `create_tables()` (crea tablas si no existen)
- `src/scraper/` — pipeline de scraping (ver arriba)
- `frontend/` — app Preact/Vite; `VITE_API_URL` apunta al backend (vacío = relativo, útil detrás de un proxy)

### Base de datos

SQLite en `./data/cinepolis.db` (montado como volumen en Docker). No hay sistema de migraciones formal: `create_tables()` usa `CREATE TABLE IF NOT EXISTS`.

### Autenticación

Los endpoints `/api/v1/admin/*` requieren el header `X-API-Key` que debe coincidir con `API_ADMIN_KEY` del entorno.
