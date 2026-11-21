# CURRENT — Butaca (ex que-ver-cine-hoy)

Última sesión: 2026-11-21

## En progreso

### Rama `feat/cinepolis-salas-precios` lista para merge (sin push)

Precios, salas y mapas de butacas de Cinépolis, unión de duplicados con Normandie, endpoint único de cartelera, purga de películas muertas y alerta de scrape. Todo commiteado en la rama; falta merge a `main` y deploy. Detalle completo en `docs/SALAS_Y_DEDUPE.md`.

**Contexto recopilado:**
- Commits: `66e0894` backend precios+salas, `1e4e0a2` frontend, `9db77e8` docs, `086fcbc` unión de duplicados, `2ca427c` billboard + purga + alertas.
- Cinépolis: `Billboard` v2 (`/v2/billboards/graphql`) trae `screen` + `sessionId`; `Seats` en `POST /v1/ticket/graphql` con `{countryId, sessionId, cinemaVistaId, experience}`.
- Payload de butacas: `rowIndex` 0 = última fila; `columnIndex` parte en 0 y se dibuja descendente; filas vacías = pasillo.
- Último scrape real (2026-11-19): `partial` por DNS de Normandie; purga dejó 21 películas, todas con funciones.
- `pytest`: 39 passed. Frontend probado con Playwright contra backend real: 1 request, 13 salas abren bien.

**Decisiones tomadas:**
- Topología de salas en `data/cinepolis_rooms.json` (gitignored, merge por `(cinema_id, room_name)`), no en SQLite.
- `/api/v1/rooms` no expone ocupación (es de la sesión muestreada, no de la función que mira el usuario).
- Unión de duplicados solo por título exacto normalizado (sin fuzzy): "JU-ON" variantes no se unen a propósito.
- Cada scraper reemplaza solo los horarios de sus propios cines; un scraper caído no borra nada.
- Alerta vía `ALERT_WEBHOOK_URL` (ntfy-compatible); vacía = desactivada.

**Preguntas pendientes antes de continuar:**
1. ¿Merge a `main` + deploy ya?
2. ¿Commitear borrado de GitHub Pages (`pages.yml`, `CNAME`)? Revierte `97c8891`.
3. ¿Commitear badges de idioma en `MovieModal.jsx` / `style.css` (cambios de otro agente)?

## Completado esta sesión

- [x] `docs/SALAS_Y_DEDUPE.md`: documentación completa (commits, comportamiento, defectos corregidos, evaluación de `plan.md`, incidentes).
- [x] Previewer de Markdown identificado: QLMarkdown (`brew install --cask qlmarkdown`), abrir con `qlmanage -p`. Guardado en memoria.

## Completado sesiones anteriores (13–19 nov)

- [x] Evaluación de implementación Gemini (cine1): 12 defectos contra payload real, todos corregidos.
- [x] `parse_seat_layout` puro + tests con fixture real; `experience` del horario (`TRADICIONAL`, `4DX`).
- [x] `GET /api/v1/rooms` + `RoomModal.jsx` (mapa al tocar la sala).
- [x] Unión Normandie → Cinépolis (`_find_canonical_movie`); 4 películas unidas en scrape real.
- [x] `GET /api/v1/billboard`: frontend de 1+N requests a 1; gzip (~250 KB → ~13 KB).
- [x] `_purge_movies_without_showtimes` (126 eliminadas en primera corrida).
- [x] `_send_alert` cuando scrape no es `success`.

## Pendiente (próximos pasos inmediatos)

- [ ] Merge de `feat/cinepolis-salas-precios` a `main`, push y deploy.
- [ ] Configurar `ALERT_WEBHOOK_URL` en `.env` del homelab (topic privado ntfy).
- [ ] Flush DNS en el Mac (`sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`) y verificar Normandie en homelab (`docker logs que-ver-cine-hoy-api`).
- [ ] Decidir borrado de GitHub Pages y badges de idioma (ver preguntas).
- [ ] Verificar contra el sitio si Estación Central realmente no tiene pasillos horizontales.
- [ ] `seatStyle` solo `Normal` visto; `.seat.special` sin ejercitar.
- [ ] Archivar o marcar checklist de `plan.md`.
- [ ] Opcional: ocupación en vivo por función (Playwright bajo demanda).
- [ ] Backend público (Cloudflare Tunnel vs VPS Contabo).
- [ ] TMDb fallback de rating cuando OMDb da `N/A`.
- [ ] Scrapers v0.4.0: El Biógrafo, Cineplanet, Centro Arte Alameda.
- [ ] Filtro por género en frontend.

## Notas

- Normandie: `[Errno 8] nodename nor servname provided` en el Mac, pero `dig normandie.cl @8.8.8.8` → `201.148.105.162`. Caché negativa de `mDNSResponder`, no bug de código.
- Cinépolis `Executable doesn't exist ... chromium_headless_shell`: `python3 -m playwright install chromium`.
- `uvicorn` local sin `--reload` no toma código nuevo: reiniciar.
- `fetch_cinepolis` retorna `(movies, showtimes, prices, rooms)`.
- Regenerar solo salas:
  ```bash
  python3 -c "
  import asyncio
  from src.scraper.rate_limiter import RateLimiter
  from src.scraper.cinepolis import fetch_cinepolis
  from src.scraper.orchestrator import _save_rooms
  m, s, p, r = asyncio.run(fetch_cinepolis(RateLimiter()))
  _save_rooms(r)
  "
  ```
- Dos agentes en mismo árbol (Gemini + Claude): sin colisiones, pero `plan-fix-salas.md` y `scratch*` desaparecieron sin causa determinada. Usar ramas/worktrees separados.
- SSH homelab: `ssh maaya@192.168.0.104`. Correr backend desde raíz (SQLite ruta relativa).
- `POST /api/v1/admin/scrape` es asíncrono; ver `GET /api/v1/admin/scrape-logs`.
