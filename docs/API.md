# API — Butaca

## API propia (FastAPI, prefix `/api/v1`)

Swagger UI disponible en `/docs`.

| Método | Ruta | Descripción | Auth |
|---|---|---|---|
| GET | `/movies` | Lista películas (filtros `genre`, `rating`) | No |
| GET | `/movies/{slug}` | Detalle + showtimes con precios | No |
| GET | `/movies/{slug}/showtimes` | Showtimes filtrados (`date`, `cinema_id`) | No |
| GET | `/cinemas` | Lista cines | No |
| GET | `/cinemas/{id}/showtimes` | Showtimes de un cine (`date`) | No |
| GET | `/showtimes` | Todos los showtimes (`date`, `cinema_id`, `movie_slug`) | No |
| GET | `/rooms` | Topología de butacas por sala Cinépolis (`cinema_name`, `room_name`); lee `data/cinepolis_rooms.json` | No |
| GET | `/health` | Estado + último scrape + conteo de películas | No |
| POST | `/admin/scrape` | Dispara scrape manual en background | Sí (`X-API-Key`) |
| GET | `/admin/scrape-logs` | Historial de scrapes (`limit`) | Sí (`X-API-Key`) |

### Modelos de respuesta

- `MovieSummary`
- `MovieDetail` — incluye `showtimes: ShowtimeOut[]`
- `ShowtimeOut` — incluye `ticket_prices: TicketPriceOut[]`
- `CinemaOut`
- `HealthOut`
- `ScrapeLogOut`

> Nota: el frontend solo consume `GET /movies` y `GET /movies/{slug}` — trae el detalle completo de cada película y filtra client-side por cine (patrones `imperio`, `estaci`, `normandie` en `App.jsx`).

> Discrepancia con README original: el modelo `TicketPrice` y los campos `ticket_prices` en las respuestas de showtimes son funcionalidad más reciente, no documentada previamente.

## APIs externas consumidas por el scraper

### 1. Cinépolis GraphQL (`api-g.cinepolis.com`)
No documentada públicamente, reverse-engineered:
- `POST /v2/billboards/graphql` — query `Movies` (título, sinopsis, género, clasificación, poster, duración)
- `POST /v1/billboards/graphql` — query `Billboard` (horarios por cine/fecha/idioma/formato)
- `POST /v1/ticket/graphql` — query `Tickets` (precios por sesión/formato)

Requiere header `x-apikey` (clave pública embebida en el JS del sitio, rota ocasionalmente) y pasar Cloudflare bot-management — de ahí el uso de Playwright en vez de httpx directo. Cines cubiertos: solo Vivo Imperio y Estación Central (hardcoded en `CINEMAS` dict).

### 2. Normandie (`https://normandie.cl/cartelera/`)
No es API — HTML scraping con BeautifulSoup (WordPress server-rendered).

### 3. OMDb API (`www.omdbapi.com`)
Rating IMDb, opcional (requiere `OMDB_API_KEY`). Busca por título con fallback a título original.

### 4. YouTube (vía `yt-dlp`, sin API key)
Búsqueda de trailers con queries en español ("trailer oficial español", "tráiler oficial subtitulado", "trailer").
