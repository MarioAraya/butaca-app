# Salas, butacas, precios y unión de duplicados

Resumen del trabajo del 13–14 de noviembre de 2026. Rama: `feat/cinepolis-salas-precios` (sin push ni merge a `main`).

## Commits

| Commit | Contenido |
|---|---|
| `66e0894` | Backend: precios de entradas, sala por horario, mapas de butacas, `GET /api/v1/rooms`, tests |
| `1e4e0a2` | Frontend: precio y sala en cada horario, modal con mapa de butacas |
| `9db77e8` | Docs, `AGENTS.md`, `.agents/`, `.gitignore` |
| `086fcbc` | Unión de películas duplicadas entre cines |
| `2ca427c` | Endpoint único `/billboard`, purga de películas sin funciones, alertas de scrape |

Precios y salas van juntos en un solo commit de backend: los cambios están mezclados en los mismos archivos.

## Qué hace ahora el sistema

### Salas y butacas (Cinépolis)

- Cada horario trae su sala (`Showtime.room_name`), leída del campo `screen` de la query `Billboard` v2.
- Por cada sala se muestrea una sesión y se pide el mapa con la query `Seats` (`POST https://api-g.cinepolis.com/v1/ticket/graphql`).
- `parse_seat_layout` (`src/scraper/cinepolis.py`) normaliza el payload:
  - filas de pantalla a fondo (la API las entrega al revés);
  - butacas en el orden del sitio (número mayor a la izquierda, `columnIndex` parte en 0);
  - filas vacías convertidas en pasillos (`aisles_after`).
- La topología se guarda en `data/cinepolis_rooms.json` con merge: una sala sin función ese día conserva su último mapa.
- `GET /api/v1/rooms` (filtros `cinema_name`, `room_name`) la sirve sin el estado por butaca, porque esa ocupación es de la sesión muestreada y no de la función que mira el usuario.
- `docs/SALAS_CINEPOLIS.html` es una página de inspección local, regenerada en cada scrape e ignorada por git.

### Frontend

- La píldora de horario muestra formato, sala, idioma y precio mínimo.
- Tocar la sala abre `RoomModal` con el mapa, escalado al ancho disponible.

### Unión de duplicados

- Normandie solo entrega título. Si ese título coincide con una película de Cinépolis (ignorando mayúsculas, acentos y puntuación, contra `title` u `original_title`), sus horarios se adjuntan a esa película y la fila `normandie-*` duplicada se elimina.
- `_save_showtimes` ahora reemplaza solo los horarios de los cines del scraper que llama. Antes borraba todos los de la película, lo que habría eliminado los de Cinépolis al guardar Normandie.
- Coincidencia exacta tras normalizar, a propósito: "JU-ON: El grito la maldición" (Normandie) no se une con "JU-ON: El grito" (Cinépolis) porque pueden ser películas distintas.

## Resultados del scrape real (2026-11-14)

- Estado `success`: 31 películas, 481 horarios de Cinépolis (todos con sala), 15 de Normandie, 12 precios.
- 13 salas: Estación Central 7 (137 a 366 butacas), Vivo Imperio 6 (149 a 197).
- 4 películas unidas: Caballo Salvaje Nueve, Yo soy Rocky, Ebenezer, Wildwood.
- `experience` observado: `TRADICIONAL` y `4DX` (Estación Central Sala 2). Ambos responden bien.
- `seatStyle` observado: solo `Normal`.
- `pytest`: 35 passed.

## Defectos corregidos de la implementación inicial

| Dónde | Problema |
|---|---|
| `rooms_html.py` | Se perdía la butaca de la columna 0 en las filas A–F |
| `rooms_html.py` | Fila K arriba en vez de A junto a la pantalla |
| `rooms_html.py` | Numeración ascendente; el sitio la muestra descendente |
| `rooms_html.py` | Pasillos dibujados y contados como filas |
| `router.py` | La API devolvía `room_name: null` siempre |
| `cinepolis.py` | `experience: "TRADICIONAL"` fijo |
| `orchestrator.py` | El JSON de salas se sobrescribía completo en cada scrape |

Defectos menores también corregidos: parseo de butacas inline y no testeable, `onclick` con comillas frágiles en las pestañas, test con fixture sintético que no detectaba nada de lo anterior, frontend sin mostrar la sala, artefactos de exploración sin ignorar.

## Evaluación de `plan.md`

- Buen guion de descubrimiento: Fase 0 (interceptar GraphQL antes de automatizar clicks) fue la decisión correcta y evitó scraping por UI.
- Quedó desactualizado: su checklist sigue sin marcar aunque las fases 0–3 se ejecutaron.
- No fijaba criterios verificables contra el payload real (orden de filas, índice de columna inicial, pasillos), y por eso los defectos de dibujo pasaron con los tests en verde.
- No exigía correr el scrape de punta a punta: el HTML nunca se había generado hasta la corrección.
- Proponía generar el HTML dentro del contenedor, donde `docs/` no es volumen; en producción no se podía ver. Resuelto con `GET /api/v1/rooms` y el modal.

## Cronología

| Cuándo | Quién | Qué |
|---|---|---|
| 13 nov, hasta 18:50 | Gemini (cine1) | Fases 0–3 de `plan.md`: descubrimiento de queries, scraper, generador HTML, modelo y migración |
| 13 nov, 18:51 | Claude | Evaluación contra el payload capturado: 12 defectos; plan correctivo `plan-fix-salas.md` |
| 13 nov, 18:52–19:00 | Sonnet (subagente) | Correcciones T1–T9, tests con fixture real, primer scrape real |
| 13 nov, tarde | Claude | Endpoint `/api/v1/rooms`, modal de sala, escala del HTML, registro de `experience` |
| 13 nov, 22:07 | servidor local | Scrape completo exitoso (33 películas) |
| 14 nov | Claude | Instalación de Chromium, prueba contra backend real, commits, unión de duplicados, scrape real `success` |

## Cómo se verificó

- Tests unitarios y de API con SQLite en memoria y el payload real como fixture.
- Navegador real (Playwright) a 390 px y 1280 px: las 13 salas abren desde la app con el conteo correcto, el modal cierra con Escape, no abre el modal de película por debajo, sin errores de consola.
- Comparación visual de Vivo Imperio Sala 3 contra la captura del sitio oficial: A arriba, 16 a 1, pasillo tras F, fila K con 17.
- Estación Central Sala 1 (366 butacas) revisada: es real, cuatro bloques con tres pasillos verticales.

## Límites conocidos

- En móvil, la sala de 34 columnas se ve completa pero con números muy pequeños.
- Ninguna sala de Estación Central reporta pasillos horizontales; no se comparó contra el sitio.
- El mapa muestra distribución, no butacas libres.
- La unión de duplicados es por título exacto normalizado: títulos con subtítulo distinto entre cines no se unen.
- Normandie sigue sin sala, póster ni precio propios (solo los hereda al unirse con Cinépolis).

## Incidentes

- `plan-fix-salas.md` y los artefactos de exploración (`scratch/`, `scratch_*.png`, `captured_*.json`, `*_query.txt`) desaparecieron de la raíz entre el 13 y el 14. Gemini dice no haberlos borrado; el subagente Sonnet no ejecutó ningún `rm`. Causa sin determinar. No se perdió nada necesario: el fixture está en `tests/fixtures/`.
- El scrape local del 14 falló primero en Cinépolis por falta del binario de Chromium de Playwright; quedó un registro `partial` (#28) en `scrape_logs`. Resuelto instalando Chromium.
- Dos agentes editaron el mismo árbol de trabajo a la vez. No hubo colisiones, pero conviene no repetirlo sin ramas separadas.

## Pendiente de decisión

- **GitHub Pages:** `.github/workflows/pages.yml` y `frontend/public/CNAME` están borrados en el árbol de trabajo, sin commitear. El commit `97c8891` movió el frontend a GitHub Pages; commitear el borrado lo revierte.
- **`.claude/settings.local.json`:** cambios de permisos locales sin commitear.
- **Merge y deploy** de la rama a `main`.

## Avance 2026-11-19

- **Purga de películas sin funciones:** `_purge_movies_without_showtimes` al final de cada scrape. Primera corrida: 126 eliminadas, quedan 21, todas con funciones. Es segura con scrapes parciales porque un scraper que falla no borra sus horarios.
- **Endpoint único `GET /api/v1/billboard`:** películas con funciones desde hoy, con horarios, sala y precios. El frontend pasó de 1 + N requests (147 con la DB anterior) a 1. Carga local en 1,2 s.
- **Compresión gzip** en la API: la cartelera baja de ~250 KB a ~13 KB.
- **Alerta de scrape:** variable `ALERT_WEBHOOK_URL` (compatible con ntfy). Si el scrape no termina en `success`, envía un POST de texto con el estado y hasta 5 errores. Vacía = desactivada. Nunca interrumpe el scrape.
- `pytest`: 39 passed.

### Incidente: Normandie no resuelve en este Mac

- `normandie.cl` falla con `[Errno 8] nodename nor servname provided` desde el resolver del sistema (también fuera del sandbox), pero `dig normandie.cl @8.8.8.8` responde `201.148.105.162` y el dominio está activo hasta 2028.
- Probable caché negativa de `mDNSResponder`. Solución local: `sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder`.
- No es un bug del código. Verificar que en el homelab no pase lo mismo (`docker logs que-ver-cine-hoy-api`).
- Efecto: en el scrape del 19, Normandie no aportó funciones; sus películas (con fechas ya pasadas) se purgaron correctamente.

## Próximos pasos sugeridos

1. Configurar `ALERT_WEBHOOK_URL` en el `.env` del homelab (topic privado de ntfy).
2. Ocupación en vivo por función: opcional, requiere llamar a Cinépolis bajo demanda con Playwright.

## Notas operativas

- Si Cinépolis falla con `Executable doesn't exist ... chromium_headless_shell`: `python3 -m playwright install chromium`.
- `uvicorn` sin `--reload` no toma código nuevo; reiniciarlo para ver `/api/v1/rooms`.
- `fetch_cinepolis` retorna `(movies, showtimes, prices, rooms)`.
- Regenerar solo las salas:
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
- Fixture real del payload de butacas: `tests/fixtures/cinepolis_seats_sala3.json` (Vivo Imperio Sala 3, 151 butacas, 11 filas).
