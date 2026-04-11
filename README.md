# que-ver-cine-hoy

API REST que scrappea diariamente la cartelera de Cinépolis Chile y expone los datos de películas, cines y horarios.

## Requisitos

- Docker y Docker Compose

## Inicio rápido

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd que-ver-cine-hoy

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
SCRAPE_CITY=santiago-centro
SCRAPE_CRON_HOUR=6
SCRAPE_CRON_MINUTE=0
API_ADMIN_KEY=tu-clave-secreta-aqui
```

| Variable | Descripción | Default |
|---|---|---|
| `DATABASE_PATH` | Ruta a la base de datos SQLite | `data/cinepolis.db` |
| `SCRAPE_DELAY_SECONDS` | Delay entre requests al sitio (rate limiting) | `20` |
| `SCRAPE_CITY` | Ciudad a scrapear | `santiago-centro` |
| `SCRAPE_CRON_HOUR` | Hora del scrape automático diario (CLT) | `6` |
| `SCRAPE_CRON_MINUTE` | Minuto del scrape automático diario | `0` |
| `API_ADMIN_KEY` | Clave para endpoints de administración | `change-me-in-production` |

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

## Producción

Usar `docker-compose.prod.yml` con un proxy inverso (nginx-proxy):

```bash
docker compose -f docker-compose.prod.yml up -d
```

Requiere que exista la red externa `proxy` y la variable `API_ADMIN_KEY` en el entorno.
