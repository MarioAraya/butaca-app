# CURRENT — que-ver-cine-hoy

Última sesión: 2026-07-12

## En progreso

### Feature: rating IMDb (OMDb API) — WIP sin commitear

Se agregó integración con OMDb para mostrar rating IMDb en cada película (badge ★ en card y modal, con link a IMDb).

**Contexto recopilado:**
- `src/scraper/omdb.py` (nuevo, sin trackear) — `find_imdb_rating(title)` llama a OMDb API, devuelve `(rating, imdb_url)` o `(None, None)` si falla o no hay `OMDB_API_KEY` configurada. Falla silenciosa (try/except interno), no rompe el scrape.
- `src/scraper/orchestrator.py` — llama `find_imdb_rating` para cada película (Cinépolis y Normandie) antes de guardar.
- `src/db/models.py` + `src/db/migrations.py` — columnas nuevas `imdb_rating`, `imdb_url` en `movies`, con `ALTER TABLE` automático en `_add_missing_columns()` (no hay sistema de migraciones formal, así que esto corre en cada `create_tables()`).
- `src/api/schemas.py` — `MovieSummary` expone ambos campos.
- `frontend/MovieCard.jsx` / `MovieModal.jsx` / `style.css` — badge `★ {rating}` (card) y link a IMDb (modal).
- `.env.example` — documenta `OMDB_API_KEY` (key gratis en omdbapi.com).

**Decisiones tomadas:**
- Rating opcional: si no hay `OMDB_API_KEY` en `.env` de prod, el feature queda inactivo sin romper nada (`find_imdb_rating` retorna `None, None` de inmediato).

**Preguntas pendientes antes de continuar:**
1. ¿Se seteó `OMDB_API_KEY` en el `.env` de prod (cine.lab)? Sin eso el rating no aparece nunca.
2. ¿Falta commitear `src/scraper/omdb.py` (actualmente `??` en git status) junto con el resto de los cambios?

### Debug: "no está lo de hoy" en cine.lab (2026-07-12)

Usuario reportó que cine.lab no mostraba cartelera de hoy. Log del backend mostrado no tenía errores (puros 200 OK). Sin acceso a red desde el sandbox de esta sesión (TLS handshake a `cine.lab` cuelga) — no se pudo confirmar la causa raíz en vivo.

**Contexto recopilado:**
- `orchestrator.py` purga showtimes `< today` al inicio de cada scrape y reemplaza showtimes por película en cada corrida → si el scrape de hoy corrió OK, "hoy" debería estar.
- `App.jsx` arma tabs de fecha desde todas las fechas presentes en los showtimes y selecciona la más antigua por default — no hay bug evidente ahí si los datos están limpios.
- Sospecha principal: el scrape de hoy no corrió o falló (`movies_scraped=0` / status `failed`). Pendiente confirmar con `GET /api/v1/health` o `GET /api/v1/admin/scrape-logs` (requiere `X-API-Key`) — **usuario no compartió el resultado todavía**.

**Preguntas pendientes antes de continuar:**
1. ¿Qué devuelve `curl https://cine.lab/api/v1/health` y `curl -H "X-API-Key: ..." https://cine.lab/api/v1/admin/scrape-logs?limit=5`? Sin esto, el diagnóstico queda sin confirmar.
2. Si el scrape falló: ¿por el anti-bot 302 de Cinépolis (ya documentado en sesión 2026-07-06) o por algo nuevo (p. ej. el feature de OMDb, aunque en teoría no debería romper nada)?

## Completado esta sesión

- [x] Middleware de logging en `src/main.py` — loguea método, path, status, duración (ms) y client IP por request; nivel WARNING si status ≥ 400.
- [x] `Dockerfile` — agregado `--no-access-log` a uvicorn para no duplicar el log de requests (ahora solo el middleware propio loguea).
- [x] `frontend/nginx.conf` — `access_log off` para assets estáticos (js/css/svg/png/ico/woff/webmanifest/sw.js), mantiene log solo en rutas relevantes (`/`, index).
- [x] Feature IMDb rating implementada end-to-end (scraper, DB, API, frontend) — **falta commitear y confirmar `OMDB_API_KEY` en prod**.

## Pendiente (próximos pasos inmediatos)

- [ ] Confirmar causa raíz de "no está lo de hoy" con `/api/v1/health` + `/api/v1/admin/scrape-logs` (ver preguntas arriba).
- [ ] Commitear feature OMDb (`src/scraper/omdb.py` + cambios relacionados) si se decide dejarla activa.
- [ ] Setear `OMDB_API_KEY` en `.env` de prod si se quiere el rating visible en cine.lab.
- [ ] Commitear + pushear cambios de logging (`src/main.py`, `Dockerfile`, `frontend/nginx.conf`) — actualmente sin commitear.
- [ ] Rebuild + redeploy backend y frontend en prod para que los cambios de logging y OMDb tomen efecto (`docker compose build` + `up -d`, o `/deploy`).
- [ ] Evaluar retry/backoff en `api_client.py` para el 302 anti-bot de Cinépolis (pendiente desde sesión 2026-07-06, sigue sin resolver).
- [ ] Scrapers pendientes (v0.4.0): El Biógrafo, Cineplanet, Centro Arte Alameda.
- [ ] Filtro por género (v0.3.0).

## Notas

- Sandbox de esta sesión no tiene acceso de red a `cine.lab` (handshake TLS cuelga) — cualquier diagnóstico en vivo de prod requiere que el usuario corra los `curl` y pegue el resultado.
- `_should_scrape_on_startup` en `src/main.py` compara fechas en UTC — si el cron/hora del contenedor no está en la tz esperada, podría desalinearse con "hoy" en Chile. No confirmado como causa, pero vale revisar si el problema persiste.
- Correr backend siempre desde raíz del repo (`cd ~/dev/que-ver-cine-hoy && uvicorn src.main:app --reload --port 8000`) — SQLite usa ruta relativa.
- `POST /api/v1/admin/scrape` es asíncrono — revisar resultado con `GET /api/v1/admin/scrape-logs`.
- `CinemaFilter.jsx` sigue siendo código muerto en disco (no importado desde `App.jsx`).
