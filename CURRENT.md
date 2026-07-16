# CURRENT — Butaca (ex que-ver-cine-hoy)

Última sesión: 2026-07-16

## En progreso

### Mirror público en GitHub (butaca-app) — EN CURSO, todavía no pusheado

Nombre público decidido: "Butaca". Destino: `https://github.com/MarioAraya/butaca-app.git`, repo **público**. El repo operativo real sigue siendo gitea (privado, homelab) — GitHub es solo un espejo de código, sin la config de deploy específica de infra.

**Decisiones tomadas:**
- `.drone.yml` y `docker-compose.prod.yml` (root + frontend) quedan **excluidos** del mirror de GitHub — contienen IPs privadas del homelab (192.168.0.103/.104) y hostnames internos (`cine.lab`, `cine-api.lab`). No son credenciales explotables (RFC1918 no rutea desde internet) pero sí exponen topología. Gitea (privado) los sigue teniendo completos.
- Se auditó **todo** el historial de git (`git log --all -p`) buscando secretos reales antes de pushear a un remoto público — no se encontró ninguno. Los `from_secret:` en `.drone.yml` son referencias al vault de Drone, no valores.
- El `x-apikey` hardcodeado en `src/scraper/cinepolis.py` NO es secreto — es una clave pública que el propio frontend de Cinepolis manda en cada request (visible en devtools de cualquiera). Documentado como tal en el código.
- Deploy target real del usuario: **VPS Contabo**, con **Traefik** como reverse proxy (mismo que usa en su homelab) — no Caddy. Ver `docker-compose.vps.yml` (nuevo, genérico, sin IPs — sí va a GitHub).

**Plan pa' el mirror (pendiente ejecutar):**
- `main` de gitea sigue con historial completo (incluye `.drone.yml`) — no tocar, sigue apuntando solo a `gitea`.
- Para GitHub: generar una rama/commit squash sin esos 2 archivos y pushear a `github main` como primer commit del mirror público.
- De ahí en adelante, cualquier cambio nuevo que se quiera reflejar en GitHub hay que aplicarlo a mano (no hay sync automático) — evaluar mejor proceso si se vuelve tedioso.

## Completado esta sesión (2026-07-16)

- [x] Reescritura completa del scraper de Cinépolis (`src/scraper/cinepolis.py`) — el sitio migró de `cinepolischile.cl` a `cinepolis.com/cl` (micro-frontend Next.js, GraphQL detrás de Cloudflare bot-management). Usa Playwright para pasar el challenge. Borrados `api_client.py` y `detail.py` (muertos, del sitio viejo).
- [x] Fix OMDb: fallback a `original_title` cuando el título en español no matchea (ej. "Evil Dead: En Llamas" → "Evil Dead Burn").
- [x] Logging accionable agregado: 401 (posible rotación de `x-apikey`) y 403 (posible bloqueo Cloudflare) logueados con mensaje explícito apuntando al runbook; resumen `IMDb ratings: X/Y matched` al final de cada scrape (WARNING si X=0).
- [x] `docs/RUNBOOK.md` creado — qué hacer cuando: no hay cartelera de hoy, Cinepolis da 401/403, Normandie cambia de HTML, OMDb falla o da `N/A` desactualizado, Playwright no arranca en Docker.
- [x] `README.md` actualizado (nombre Butaca, arquitectura, variables de entorno correctas, sección producción sin depender de `docker-compose.prod.yml`).
- [x] CSS: modal de trailer más ancho en desktop (720px) — intento de mitigar que YouTube arranque en 360p (el player elige calidad según tamaño en píxeles).
- [x] Config limpiado: `SCRAPE_CITY` y `CINEPOLIS_BASE_URL` eliminados (ya no se usan, el scraper nuevo hardcodea los 2 cines que muestra el frontend).
- [x] **Fix Normandie: 0 funciones para "hoy"** — Normandie cambió el texto del header de semana ("jueves 16 al miércoles 22 de julio" en vez de "jueves 28 de mayo al miércoles 3 de junio", mes ya no se repite en el día de inicio). El regex viejo agarraba el día equivocado como ancla y toda la semana quedaba corrida — solo se guardaba el último día. Reescrito `_parse_week_dates` en `src/scraper/normandie.py` para anclar en el día final (siempre tiene mes explícito) y derivar el inicio. Verificado con scrape real: 22 showtimes en toda la semana, incluye hoy.
- [x] `docker-compose.vps.yml` + `.env.deploy.example` — deploy a VPS con Traefik (HTTPS automático), separado de `.env` (app) a propósito para no romper `pydantic-settings` (extra_forbidden).

## Pendiente (próximos pasos)

- [ ] **Ejecutar el push del mirror a GitHub** (ver plan arriba) — decidido pero no hecho todavía.
- [ ] Deploy real en el VPS Contabo: falta definir/apuntar `API_DOMAIN` y `FRONTEND_DOMAIN` por DNS antes de poder levantar `docker-compose.vps.yml` ahí.
- [ ] **TMDb como fallback de rating** — OMDb tiene cache propio que puede quedar desactualizado (rating `N/A` aunque IMDb real ya tenga nota, visto con Evil Dead: En Llamas / `tt31170389`). Evaluar sumar TMDb API como fuente alternativa. No implementado todavía.
- [ ] Definir proceso de sync gitea → GitHub si se seguirán reflejando cambios ahí (hoy es manual).
- [ ] Verificar en un tiempo si el `x-apikey` de Cinepolis sigue vigente (puede rotar con sus deploys — ver `docs/RUNBOOK.md` sección 2).
- [ ] Evaluar retry/backoff más fino si el scraper de Cinépolis empieza a fallar seguido (Cloudflare, no el anti-bot viejo del sitio anterior — ese problema quedó obsoleto con la migración).
- [ ] Scrapers pendientes (v0.4.0): El Biógrafo, Cineplanet, Centro Arte Alameda.
- [ ] Filtro por género (v0.3.0).
- [ ] `CinemaFilter.jsx` sigue siendo código muerto en disco (no importado desde `App.jsx`) — evaluar borrar o reactivar.

## Notas

- Backend Docker ahora es notablemente más pesado (incluye Chromium vía Playwright) — builds de CI van a tardar más.
- Correr backend siempre desde raíz del repo (`cd ~/dev/que-ver-cine-hoy && uvicorn src.main:app --reload --port 8000`) — SQLite usa ruta relativa.
- `POST /api/v1/admin/scrape` es asíncrono — revisar resultado con `GET /api/v1/admin/scrape-logs`.
- Ver `docs/RUNBOOK.md` antes de investigar desde cero cualquier falla de scrape — cubre los casos ya conocidos.
