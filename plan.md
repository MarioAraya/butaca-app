# Plan: que-ver-cine-hoy

## Objetivo

API que hace scraping diario de la cartelera de Cinepolis Chile para servir información de películas, horarios, trailers y más.

## Stack Tecnológico

- **Lenguaje**: Python 3.12
- **API**: FastAPI + Uvicorn
- **Scraping**: httpx + BeautifulSoup (datos estáticos) + Playwright (datos dinámicos)
- **Base de datos**: SQLite con WAL mode
- **Scheduler**: APScheduler (cron diario 06:00 CLT)
- **Deploy**: Docker (single container)

## Arquitectura

```
┌──────────────────────────────────────────────┐
│              Docker Container                 │
│                                               │
│  FastAPI (:8000)  ◄──►  SQLite (/data/)      │
│       ▲                    ▲                  │
│       │                    │                  │
│  APScheduler ──► Scraper (3 fases)           │
│                  1. Listing (Playwright)      │
│                  2. Detalle (httpx+BS4)       │
│                  3. Horarios (Playwright)     │
└──────────────────────────────────────────────┘
```

## Estrategia de Scraping

### Fase 1 — Listing
- URL: `/cartelera/santiago-centro/`
- Tool: Playwright (Angular renderiza client-side)
- Output: Lista de slugs de películas

### Fase 2 — Detalle de Película
- URL: `/pelicula/{slug}` por cada película
- Tool: httpx + BeautifulSoup (data-attributes son HTML estático)
- Output: Título, sinopsis, géneros, clasificación, director, duración, poster
- Rate limit: 20 seg entre requests

### Fase 3 — Horarios + Trailer
- URL: `/pelicula/{slug}` (misma página, pero renderizada con JS)
- Tool: Playwright
- Output: Horarios por cine + URL trailer YouTube
- Rate limit: 20 seg entre páginas

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/movies` | Lista películas |
| GET | `/api/v1/movies/{slug}` | Detalle + horarios |
| GET | `/api/v1/movies/{slug}/showtimes` | Horarios de 1 película |
| GET | `/api/v1/cinemas` | Lista cines |
| GET | `/api/v1/cinemas/{id}/showtimes` | Horarios de 1 cine |
| GET | `/api/v1/showtimes` | Todos los horarios |
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/admin/scrape` | Trigger manual |

## Rate Limiting

- Máximo 1 página cada 20 segundos
- Rate limiter async con lock global
- Si se detecta bloqueo: incrementar delay automáticamente
