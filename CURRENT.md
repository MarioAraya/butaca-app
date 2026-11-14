# CURRENT — Butaca (ex que-ver-cine-hoy)

Última sesión: 2026-11-13

## En progreso

### 1. Salas y mapa de butacas Cinépolis — implementado, sin commitear

Scraper extrae sala por horario (`Showtime.room_name`) y topología de butacas por sala; genera `data/cinepolis_rooms.json` y `docs/SALAS_CINEPOLIS.html`.

**Contexto recopilado:**
- Implementación inicial de Gemini (cine1) siguiendo `plan.md`; corregida después por Claude/Sonnet (plan correctivo `plan-fix-salas.md`, ya no existe en disco — alguien lo borró junto con los artefactos de exploración `scratch*`, `captured_*.json`).
- API: `POST https://api-g.cinepolis.com/v1/ticket/graphql`, op `Seats`, vars `{countryId, sessionId, cinemaVistaId, experience}`. `Billboard` pasó a `/v2/billboards/graphql` y trae `screen` + `sessionId` por horario.
- Payload: filas vienen de fondo a pantalla (`rowIndex` 0 = última fila); `columnIndex` parte en 0 y el sitio lo dibuja descendente (butaca mayor a la izquierda); filas vacías = pasillo horizontal. No hay foto de sala, solo ícono SVG del tipo de butaca.
- Scrape real 2026-11-13: 21 películas, 508 horarios, 12 precios, 13 salas (Estación Central 7, Vivo Imperio 6), 0 horarios sin sala. Estación Central Sala 1 tiene 366 butacas (real: 4 bloques, 3 pasillos verticales).
- Fixture real: `tests/fixtures/cinepolis_seats_sala3.json` (Vivo Imperio Sala 3, 151 butacas, 11 filas).
- `pytest`: 28 passed. `npm run build` del frontend OK.

**Decisiones tomadas:**
- Topología de salas en JSON (`data/cinepolis_rooms.json`, gitignored), no en SQLite.
- `_save_rooms` hace merge por `(cinema_id, room_name)`: sala sin función ese día conserva su topología.
- Se muestrea 1 sesión por sala; la ocupación en el HTML es foto del momento del scrape, no en vivo.
- `parse_seat_layout` (en `src/scraper/cinepolis.py`) es función pura, testeada con fixture real.

- Salas expuestas en prod vía `GET /api/v1/rooms` (lee `data/`, que sí es volumen). El endpoint omite el estado por butaca (ocupación obsoleta). `docs/SALAS_CINEPOLIS.html` queda como herramienta de inspección local.
- Frontend: la etiqueta de sala en cada horario abre `RoomModal` con el mapa (solo distribución, sin ocupación).

**Preguntas pendientes antes de continuar:**
1. ¿Commits separados para: precios (`TicketPrice`), salas/butacas, docs, migración a `agy`, limpieza de GitHub Pages?

### 2. Precios de entradas (`TicketPrice`) — implementado, sin commitear

Scraping, persistencia y visualización de precio mínimo por horario (`MovieCard.jsx`, `formatPrice`). Mismo árbol de trabajo que el punto 1.

## Completado esta sesión

- [x] Evaluación de `plan.md` y de la implementación de Gemini: 12 defectos detectados contra el payload real.
- [x] `rooms_html.py`: columna 0 ya no se pierde, fila A junto a pantalla, numeración descendente, pasillos como separador, tabs sin `onclick` inline.
- [x] `router.py`: `_showtime_out` devuelve `room_name` (antes siempre `null`).
- [x] `cinepolis.py`: parser puro `parse_seat_layout`; `experience` tomado del horario muestreado (fallback `TRADICIONAL`).
- [x] `orchestrator.py`: `_save_rooms` con merge.
- [x] `MovieCard.jsx`: muestra sala junto al formato.
- [x] Tests nuevos: `test_cinepolis_seat_layout.py`, `test_cinepolis_rooms.py` (fixture real), `test_api_room_name.py`.
- [x] `.gitignore`: artefactos de exploración, `data/cinepolis_rooms.json`, `.DS_Store`.
- [x] Scrape real end-to-end + verificación visual del HTML (Vivo Imperio Sala 3 coincide con el sitio).
- [x] `GET /api/v1/rooms` + `load_rooms()` en `orchestrator.py`; tests en `tests/test_api_rooms.py`.
- [x] Frontend `RoomModal.jsx`: mapa de butacas al tocar la sala; se ajusta al ancho (probado 390px y 1280px, salas de 18 y 34 columnas, sala sin mapa).
- [x] `rooms_html.py`: tamaño de butaca según columnas; Estación Central Sala 1 ya no requiere scroll.
- [x] `cinepolis.py`: `experience` enviado a `Seats` queda en el log y en el JSON de cada sala.
- [x] Migración de Claude Code a Google Antigravity (`agy`): `AGENTS.md`, `.agents/skills/`, `~/.gemini/config/`.

## Pendiente (próximos pasos inmediatos)

- [ ] Correr scrape completo local (DB local tiene 0 horarios) y probar el modal de sala con datos reales; la prueba visual usó API simulada.
- [ ] Revisar y commitear el árbol de trabajo (ver pregunta 1).
- [ ] Verificar contra el sitio si Estación Central realmente no tiene pasillos horizontales (ninguna sala los detectó).
- [ ] Probar formatos distintos de 2D/3D cuando aparezcan (4DX, VIP…).
- [ ] `seatStyle` solo se vio `Normal` (2.322 butacas); clase `.seat.special` sin ejercitar.
- [ ] Actualizar checklist de `plan.md` (sigue sin marcar) o archivarlo.
- [ ] Decidir y consolidar backend público (Cloudflare Tunnel vs VPS Contabo con `butaca-api.marioaraya.com`).
- [ ] TMDb como fallback de rating cuando OMDb da `N/A`.
- [ ] Monitorear retry/backoff de Cinépolis en el cron de las 06:00 y vigencia del `x-apikey` (`docs/RUNBOOK.md`).
- [ ] Scrapers pendientes (v0.4.0): El Biógrafo, Cineplanet, Centro Arte Alameda.
- [ ] Filtro por género en el frontend (v0.3.0).

## Notas

- Dos agentes editaron el mismo árbol (Gemini cine1 + Claude). Sin colisiones detectadas, pero revisar el diff completo antes de commitear.
- Regenerar salas sin scrape completo de DB:
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
- `fetch_cinepolis` ahora retorna 4-tupla `(movies, showtimes, prices, rooms)`.
- SSH al homelab (`ssh maaya@192.168.0.104`) para logs reales de prod (`docker logs que-ver-cine-hoy-api`).
- Correr backend siempre desde raíz del repo — SQLite usa ruta relativa.
- `POST /api/v1/admin/scrape` es asíncrono — revisar con `GET /api/v1/admin/scrape-logs` (incluye `errors`).
- Ver `docs/RUNBOOK.md` antes de investigar fallas de scrape.
