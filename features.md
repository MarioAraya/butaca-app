# Features: Butaca

## v0.1.0 — MVP

### Scraping
- [x] Scraping diario automático (06:00 CLT)
- [x] Extracción de listado de películas en cartelera
- [x] Detalle de cada película: título, sinopsis, géneros, clasificación de edad, duración, director, actores
- [x] URL de poster de cada película
- [x] URL de trailer (YouTube)
- [x] Horarios por cine: nombre del cine, idioma, formato, horas
- [x] Rate limiting: máximo 1 request cada 20 segundos
- [x] Trigger manual de scrape vía API
- [x] Log de cada ejecución de scrape

### API REST
- [x] `GET /api/v1/movies` — Lista de películas con filtros (género, clasificación)
- [x] `GET /api/v1/movies/{slug}` — Detalle completo con horarios
- [x] `GET /api/v1/movies/{slug}/showtimes` — Horarios filtrados por fecha y cine
- [x] `GET /api/v1/cinemas` — Lista de cines
- [x] `GET /api/v1/cinemas/{id}/showtimes` — Horarios por cine
- [x] `GET /api/v1/showtimes` — Todos los horarios con filtros
- [x] `GET /api/v1/health` — Health check con estado último scrape
- [x] `POST /api/v1/admin/scrape` — Scrape manual (protegido con API key)
- [x] `GET /api/v1/admin/scrape-logs` — Historial de scrapes

### Infraestructura
- [x] Docker container único (FastAPI + Scraper + SQLite)
- [x] docker-compose.yml con volume para datos persistentes
- [x] Variables de entorno configurables

## Futuro (backlog)

### v0.2.0 — Más ciudades
- [ ] Soporte para múltiples ciudades (no solo santiago-centro)
- [ ] Endpoint para listar ciudades disponibles
- [ ] Selección de ciudad en filtros

### v0.3.0 — Frontend
- [x] Interfaz web (Preact/Vite)
- [x] Vista de cartelera tipo grid (columnas en desktop)
- [x] Filtro por fecha (tabs horizontales con scroll)
- [x] Filtro por cine (toggle multi-select, mismo estilo que fechas)
- [x] Detalle de película con trailer embebido (modal bottom sheet)
- [ ] Filtro por género
- [x] Rating IMDb (OMDb API) por película, badge en card + link en modal
- [ ] TMDb como fallback de rating cuando OMDb tiene cache desactualizado (da `N/A` aunque IMDb real ya tenga nota) — ver `docs/RUNBOOK.md` sección 4

### v0.4.0 — Más cines (scrapers pendientes)

- [ ] **El Biógrafo** — `https://elbiografo.cl/category/cartelera/` — cine arte, WordPress, server-rendered
- [ ] **Cineplanet** — `https://www.cineplanet.cl/peliculas` — cadena grande, JS-heavy (Angular/React), tiene API interna probable. Sucursales: CP Alameda, CP La Reina, etc.
- [ ] **Centro Arte Alameda** — `https://centroartealameda.cl` — cine comunitario/arte, cartelera semanal con días y horas por película, imagen de cartelera como fuente principal

### v0.5.0 — Notificaciones
- [ ] Alertas de estrenos
- [ ] Notificaciones por género favorito
- [ ] Webhook para integraciones

### Infra / Deploy
- [x] Mirror público en GitHub (`github.com/MarioAraya/butaca-app`) — sin `.drone.yml`/`docker-compose.prod.yml` (IPs privadas de homelab)
- [x] `docker-compose.vps.yml` con Traefik (HTTPS automático) para deploy en VPS (Contabo)
- [ ] Deploy real en el VPS Contabo (dominios aún no definidos/apuntados)
- [ ] Definir proceso de sync gitea → GitHub para cambios futuros (hoy es manual)
