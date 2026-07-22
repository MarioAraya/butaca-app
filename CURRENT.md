# CURRENT — Butaca (ex que-ver-cine-hoy)

Última sesión: 2026-07-19

## En progreso

### Backend público para el deploy en Vercel — BLOQUEADO, necesita decisión

Se deployó el frontend a Vercel (`https://frontend-mu-six-9nax6ly7b0.vercel.app`, build OK, HTTP 200) con `VITE_API_URL=https://cine-api.lab` seteada como env var de producción en el proyecto Vercel. **Esto no sirve datos reales**: `cine-api.lab` es DNS local (`.lab` solo resuelve vía `/etc/hosts` en las máquinas del usuario) apuntando a una IP privada (192.168.0.104) — Vercel (servidor público) no puede resolverlo ni llegar a esa IP. El sitio va a mostrar "Failed to fetch" hasta resolver esto.

**Decisión pendiente del usuario — dos caminos:**
1. Exponer `cine-api.lab` (o un dominio real) a internet — opción más simple: Cloudflare Tunnel (no requiere abrir puertos ni IP fija).
2. Mover el backend al VPS Contabo (ya hay `docker-compose.vps.yml` con Traefik+HTTPS real listo para eso, ver sesión anterior) — el frontend de Vercel apuntaría ahí en vez de al homelab.

Ninguna se implementó todavía — quedó explícitamente pausado a pedido del usuario ("deploy solo frontend estático, sin backend vivo, por ahora").

## Completado esta sesión (2026-07-19)

- [x] **Mirror público en GitHub completado** (`github.com/MarioAraya/butaca-app`, rama `main`). Primero se pusheó sin `.drone.yml`/`docker-compose.prod.yml` (excluidos por privacidad de IPs), pero el usuario aclaró que **no le importa que las IPs privadas se vean** (RFC1918, no explotable) — solo que no se suba nada realmente sensible (`.env`, credenciales). Se agregaron esos 3 archivos también en un segundo commit (`c75dfa8`) al mirror. Confirmado: no había secretos reales en ningún archivo ni en el historial completo de git (auditado con `git log --all -p` antes del primer push).
- [x] **Fix crítico: cartelera de Cinépolis vacía en prod** — diagnosticado con acceso SSH real al homelab (`ssh maaya@192.168.0.104`, habilitado por el usuario a mitad de sesión). El scrape automático de las 06:00 venía dando `status=partial, movies_found=3` (solo Normandie) tres días seguidos, mientras que triggers manuales corrían perfecto (13 pelis Cinépolis, 350+ showtimes). Causa: bloqueo transitorio de Cloudflare específico de esa ventana horaria, no un problema estructural.
  - Se agregó `errors` al schema `ScrapeLogOut` (`src/api/schemas.py`) para poder diagnosticar sin SSH en el futuro — antes el campo existía en el modelo pero no se serializaba.
  - Se implementó **retry con backoff** en `src/scraper/cinepolis.py` (`fetch_cinepolis`): hasta 3 intentos de sesión completa de browser, 30s entre reintentos, dispara tanto en excepción como en resultado vacío (Cloudflare puede devolver 200 sin nada útil). Camino feliz sin cambios (éxito en intento 1, sin logging extra).
- [x] **Fix: Normandie mostraba 0 funciones para "hoy"** — Normandie cambió el formato del header de semana (antes repetía el mes en ambos días, ahora solo al final: "jueves 16 al miércoles 22 de julio"). El regex viejo anclaba mal y toda la semana quedaba corrida, solo se guardaba el último día. Reescrito `_parse_week_dates` en `src/scraper/normandie.py` para anclar en el día final (siempre tiene mes explícito). Verificado con scrape real (22 showtimes en la semana, incluye hoy).
- [x] **Certificados TLS (`.lab`, mkcert) resueltos para el usuario en macOS y Windows** — el cert wildcard `*.lab` de Traefik es válido (`openssl verify` confirmado contra la CA local), pero `cine-api.lab` daba "Failed to fetch" en el browser porque nunca se había visitado directo (sin excepción de cert, a diferencia de `cine.lab` que sí se navegó). Se instaló la CA (`mkcert -install`, ya estaba en macOS) y se sirvió `rootCA.pem` vía HTTP temporal en la LAN (puerto 8899, cerrado al terminar) para que el usuario la importe en Windows (renombrada a `.cer` porque Windows no asocia `.pem`).
- [x] Frontend deployado a Vercel (ver bloqueo arriba) — build y hosting funcionan, falta backend público.

## Pendiente (próximos pasos)

- [ ] **Decidir y ejecutar backend público** (Cloudflare Tunnel vs VPS Contabo) — bloqueante para que el deploy de Vercel sirva datos reales. Ver sección "En progreso" arriba.
- [ ] Si se elige VPS Contabo: falta definir/apuntar `API_DOMAIN` y `FRONTEND_DOMAIN` por DNS antes de levantar `docker-compose.vps.yml` ahí (pendiente de sesiones anteriores, sigue sin resolver).
- [ ] **TMDb como fallback de rating** — OMDb tiene cache propio que puede quedar desactualizado (rating `N/A` aunque IMDb real ya tenga nota, visto con Evil Dead: En Llamas / `tt31170389`). No implementado.
- [ ] Definir proceso de sync gitea → GitHub si se seguirán reflejando cambios ahí (hoy es manual, sin automatización).
- [ ] Monitorear si el retry/backoff de Cinépolis (agregado hoy) realmente resuelve las fallas del cron de las 06:00, o si el patrón de bloqueo de Cloudflare es más persistente de lo que parece.
- [ ] Verificar en un tiempo si el `x-apikey` de Cinepolis sigue vigente (puede rotar con sus deploys — ver `docs/RUNBOOK.md` sección 2).
- [ ] Scrapers pendientes (v0.4.0): El Biógrafo, Cineplanet, Centro Arte Alameda.
- [ ] Filtro por género (v0.3.0).
- [ ] `CinemaFilter.jsx` — **corrección de nota anterior**: SÍ está en uso (importado y renderizado en `App.jsx`), no es código muerto como se anotó antes.

## Notas

- SSH al homelab (`ssh maaya@192.168.0.104`) está disponible y fue clave para diagnosticar el fallo de Cinépolis sin adivinar — usarlo cuando haga falta ver logs reales de prod en vez de especular.
- Backend Docker sigue siendo pesado (Chromium vía Playwright) — builds de CI tardan más que antes de la migración del scraper.
- Correr backend siempre desde raíz del repo (`cd ~/dev/que-ver-cine-hoy && uvicorn src.main:app --reload --port 8000`) — SQLite usa ruta relativa.
- `POST /api/v1/admin/scrape` es asíncrono — revisar resultado con `GET /api/v1/admin/scrape-logs` (ahora incluye `errors` con el detalle de la falla, no solo el status).
- Ver `docs/RUNBOOK.md` antes de investigar desde cero cualquier falla de scrape — cubre los casos ya conocidos (401/403 Cinépolis, cambios de HTML en Normandie, OMDb).
- `vgradio-api.lab` (otro proyecto en el mismo homelab) usa el mismo cert wildcard `*.lab` — mismo fix de CA aplica ahí también.
