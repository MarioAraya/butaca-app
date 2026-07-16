# Runbook — troubleshooting del scraper

Qué hacer cuando falta la cartelera de hoy, el scrape falla, o el rating IMDb no aparece.

## 1. No aparecen películas de hoy / cartelera desactualizada

**Diagnóstico:**

```bash
# Estado general + último scrape
curl <API_URL>/api/v1/health

# Historial de los últimos scrapes
curl -H "X-API-Key: <API_ADMIN_KEY>" "<API_URL>/api/v1/admin/scrape-logs?limit=5"
```

Revisar `last_scrape_status`: si es `failed` o `partial`, seguir a la sección correspondiente más abajo. Si es `success` pero igual falta algo, revisar logs del contenedor backend:

```bash
docker logs <container_backend> 2>&1 | grep -E "ERROR|scrape failed|No .* movies found"
```

**Gatillar un scrape manual** (no repetir seguido — puede disparar bloqueos anti-bot):

```bash
curl -X POST <API_URL>/api/v1/admin/scrape -H "X-API-Key: <API_ADMIN_KEY>"
```

## 2. Cinepolis: scrape falla (401 / 403 / sin películas)

El scraper de Cinepolis (`src/scraper/cinepolis.py`) usa Playwright para pasar la protección Cloudflare del sitio y llama directo al GraphQL interno (`api-g.cinepolis.com`). Dos fallos típicos, ambos logueados explícitamente:

**`401 Unauthorized` — log: `x-apikey likely rotated`**

El header `x-apikey` es una clave pública embebida en el bundle JS del frontend de Cinepolis. Si Cinepolis rehace un deploy, puede cambiar. Para obtener la nueva:

1. Abrir `https://cinepolis.com/cl` en un browser real, DevTools → Network.
2. Filtrar por `billboards`.
3. Copiar el header `x-apikey` de cualquier request a `api-g.cinepolis.com`.
4. Actualizar `_API_KEY` en `src/scraper/cinepolis.py`.

**`403` — log: `likely a Cloudflare bot-management block`**

Cloudflare bloqueó incluso al browser real de Playwright. Puede ser temporal (reintentar más tarde) o un endurecimiento de la protección del sitio. Si persiste:
- Confirmar manualmente en un browser normal que el sitio carga sin captcha.
- Si Cloudflare pide challenge interactivo (no solo JS), este approach deja de alcanzar — requeriría rotación de IP/proxy residencial, fuera del alcance actual.

**El sitio cambió de plataforma otra vez**

Ya pasó una vez (`cinepolischile.cl` → `cinepolis.com/cl`, julio 2026). Si el GraphQL deja de responder por completo (no 401/403, sino timeout o HTML en vez de JSON), repetir el proceso de reverse-engineering:
1. Abrir el sitio nuevo con Playwright, escuchar requests `xhr`/`fetch`.
2. Buscar el host real de datos (suele delatarse por nombre: `billboards`, `schedules`, `showtimes`).
3. Capturar el payload/headers exactos de un request real y replicarlos.

## 3. Normandie: scrape falla o trae 0 películas

`src/scraper/normandie.py` parsea HTML server-rendered (WordPress) — si Normandie rediseña la página, el parser (`parse_cartelera_html`) puede dejar de encontrar `div.contenedorcartelera`. Log a buscar: `Normandie: 0 movies, 0 showtimes` o `Normandie scrape failed`. Diagnóstico: bajar el HTML actual (`curl https://normandie.cl/cartelera/`) y comparar estructura contra lo que espera el parser.

## 4. Rating IMDb (OMDb) no aparece o falla

Log a buscar al final de cada scrape: `IMDb ratings: X/Y movies matched`. Si `X` es 0 o inusualmente bajo:

- **`OMDB_API_KEY` no seteada o vacía** → `find_imdb_rating` retorna `(None, None)` sin llamar a la API (comportamiento esperado, no es un error).
- **Cuota agotada** — el plan gratis de OMDb es ~1000 requests/día. Si se supera, todas las llamadas del resto del día fallan. Log: `OMDb lookup failed for '<título>'` (excepción de red/HTTP, no "no match").
- **`OMDb: no match for '<título>'`** — no es error: el título (ni el `original_title` de fallback) no está en la base de OMDb. Frecuente con anime, conciertos filmados, o estrenos muy nuevos.
- **OMDb devuelve `Response: True` pero `imdbRating: N/A`** — el ID es correcto pero el cache de OMDb está desactualizado respecto a IMDb real (pasó con "Evil Dead: En Llamas" / `tt31170389`: IMDb ya tenía 6.7 con 13k votos, OMDb seguía en `N/A`). No hay fix de código — es un dato de terceros atrasado. Si se vuelve frecuente, evaluar sumar TMDb como fuente alternativa (ver `features.md`, pendiente).

## 5. Chequeo rápido de logs (grep útil)

```bash
docker logs <container_backend> 2>&1 | grep -E \
  "ERROR|Cinepolis scrape failed|OMDb lookup failed|No .* movies found|401 Unauthorized|Cloudflare block|IMDb ratings:"
```

## 6. Playwright / Chromium no arranca en Docker

Si el log muestra `Executable doesn't exist` o errores de librerías faltantes (`libnss3`, `libatk`, etc.), el `Dockerfile` no corrió `playwright install --with-deps chromium` correctamente (falta de espacio en disco durante el build, o capa cacheada vieja). Rebuildear sin cache:

```bash
docker build --no-cache -t que-ver-cine-hoy .
```
