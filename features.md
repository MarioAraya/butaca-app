# Features: que-ver-cine-hoy

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
- [ ] Interfaz web (Next.js o similar)
- [ ] Vista de cartelera tipo grid
- [ ] Filtros interactivos
- [ ] Detalle de película con trailer embebido

### v0.4.0 — Notificaciones
- [ ] Alertas de estrenos
- [ ] Notificaciones por género favorito
- [ ] Webhook para integraciones
