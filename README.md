# Butaca

API REST + frontend que scrappean diariamente la cartelera de cines de Santiago (Cinépolis y Normandie) y exponen películas, cines y horarios.

## Arquitectura

- **Backend**: FastAPI + SQLite, scrape diario vía APScheduler.
- **Cinépolis** (`src/scraper/cinepolis.py`): el sitio (`cinepolis.com/cl`) es un micro-frontend Next.js con los datos detrás de una API GraphQL protegida por Cloudflare bot-management. El scraper usa Playwright (Chromium headless) para pasar la protección y llama al GraphQL directo desde la página.
- **Normandie** (`src/scraper/normandie.py`): sitio WordPress server-rendered, se parsea el HTML con BeautifulSoup.
- **Rating IMDb** (`src/scraper/omdb.py`): opcional, vía OMDb API (requiere `OMDB_API_KEY`).
- **Frontend**: Preact + Vite (`frontend/`).

Si algo de esto falla (scrape sin datos de hoy, rating IMDb ausente, Cloudflare bloqueando el scraper), ver **[docs/RUNBOOK.md](docs/RUNBOOK.md)** antes de asumir que es un bug nuevo.

## Requisitos

- Docker y Docker Compose

## Inicio rápido

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd butaca-app

# 2. Crear archivo de variables de entorno
cp .env.example .env   # o crear manualmente (ver sección Variables de entorno)

# 3. Levantar el servicio
docker compose up -d

# 4. Verificar que está corriendo
curl http://localhost:8000/api/v1/health
```

La API queda disponible en `http://localhost:8000`.

## Variables de entorno

Crear un archivo `.env` en la raíz del proyecto:

```env
DATABASE_PATH=data/cinepolis.db
SCRAPE_DELAY_SECONDS=20
SCRAPE_CRON_HOUR=6
SCRAPE_CRON_MINUTE=0
API_ADMIN_KEY=tu-clave-secreta-aqui
OMDB_API_KEY=
```

| Variable | Descripción | Default |
|---|---|---|
| `DATABASE_PATH` | Ruta a la base de datos SQLite | `data/cinepolis.db` |
| `SCRAPE_DELAY_SECONDS` | Delay entre requests al sitio (rate limiting) | `20` |
| `SCRAPE_CRON_HOUR` | Hora del scrape automático diario (CLT) | `6` |
| `SCRAPE_CRON_MINUTE` | Minuto del scrape automático diario | `0` |
| `API_ADMIN_KEY` | Clave para endpoints de administración | `change-me-in-production` |
| `OMDB_API_KEY` | Clave gratis de [omdbapi.com](https://www.omdbapi.com/apikey.aspx) para mostrar rating IMDb. Vacío = feature desactivada, no rompe nada. | *(vacío)* |

## Endpoints

### Películas

```
GET /api/v1/movies                    Lista de películas en cartelera
GET /api/v1/movies/{slug}             Detalle completo con horarios
GET /api/v1/movies/{slug}/showtimes   Horarios filtrados
```

Parámetros de filtro para `/movies`:
- `genre` — filtrar por género (ej. `Acción`)
- `rating` — filtrar por clasificación de edad (ej. `TE+7`)

Parámetros de filtro para `/movies/{slug}/showtimes`:
- `date` — fecha en formato `YYYY-MM-DD`
- `cinema_id` — ID del cine

### Cines

```
GET /api/v1/cinemas                   Lista de cines disponibles
GET /api/v1/cinemas/{id}/showtimes    Horarios de un cine específico
```

### Horarios

```
GET /api/v1/showtimes                 Todos los horarios con filtros
```

### Administración

```
GET  /api/v1/health                   Estado del servicio y último scrape
POST /api/v1/admin/scrape             Disparar scrape manual (requiere API key)
GET  /api/v1/admin/scrape-logs        Historial de ejecuciones de scrape
```

Los endpoints `/admin/*` requieren el header `X-API-Key: <API_ADMIN_KEY>`.

### Documentación interactiva

Disponible en `http://localhost:8000/docs` (Swagger UI).

## Scraping

El scrape corre automáticamente todos los días a las 06:00 CLT.

Para forzar un scrape manual:

```bash
curl -X POST http://localhost:8000/api/v1/admin/scrape \
  -H "X-API-Key: tu-clave-secreta-aqui"
```

## Datos persistentes

Los datos se guardan en el directorio `./data/` mediante un volume de Docker. Al hacer `docker compose down` los datos no se pierden.

Para resetear la base de datos:

```bash
docker compose down
rm -rf ./data/
docker compose up -d
```

## Desarrollo local

```bash
# Instalar dependencias
pip install -e ".[dev]"

# Instalar browsers para Playwright
playwright install chromium

# Correr la API localmente
uvicorn src.main:app --reload --port 8000

# Correr tests
pytest
```

## Producción (VPS con Traefik)

`docker-compose.vps.yml` levanta backend + frontend + Traefik (proxy inverso con HTTPS automático vía Let's Encrypt) en un solo comando.

Las variables de Traefik (dominios, email para el certificado) van en un archivo **separado** de `.env` a propósito: docker compose sustituye `${VAR}` leyendo por defecto un archivo llamado `.env`, y si esas variables vivieran ahí también se inyectarían al contenedor del backend — rompiendo el arranque, porque `pydantic-settings` rechaza variables de entorno no declaradas en `Settings`.

```bash
# 1. Variables de la app (backend)
cp .env.example .env   # completar OMDB_API_KEY, API_ADMIN_KEY, etc.

# 2. Variables de deploy (Traefik/dominios)
cp .env.deploy.example .env.deploy   # completar ACME_EMAIL, API_DOMAIN, FRONTEND_DOMAIN

# 3. Levantar todo
docker compose -f docker-compose.vps.yml --env-file .env.deploy up -d --build
```

Requisitos: los dominios `API_DOMAIN` y `FRONTEND_DOMAIN` apuntando por DNS a la IP del VPS, y los puertos 80/443 libres (Traefik los toma directamente).

**Nota:** la imagen del backend incluye Chromium (Playwright) para el scraper de Cinépolis — es notablemente más pesada que una imagen Python típica y el primer build tarda bastante más. Ver [docs/RUNBOOK.md](docs/RUNBOOK.md) si el build falla por espacio en disco o librerías faltantes.
