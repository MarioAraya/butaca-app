# Plan de Implementación: Actualización Scraper Cinépolis + Mapa de Salas y Butacas

> **Objetivo para el modelo ejecutor (Gemini Flash / Pro):**
> Seguir este plan paso a paso sin asumir cambios innecesarios. Primero ejecutar la **Fase 0 (Diagnóstico e Intercepción)** para determinar qué datos siguen disponibles vía GraphQL directo (`api-g.cinepolis.com`) y cuáles requieren navegación UI en Playwright o nuevas queries GraphQL.

---

## 1. URLs y Endpoints Actualmente Escaneados (`src/scraper/cinepolis.py`)

Actualmente el scraper **no interactúa con botones del DOM**. Abre la home con Playwright únicamente para pasar el challenge de Cloudflare y luego ejecuta `fetch()` desde el contexto de la página hacia la API GraphQL:

| Propósito | URL / Endpoint | Operación GraphQL / Uso |
| :--- | :--- | :--- |
| **Landing (Cloudflare cookie)** | `https://cinepolis.com/cl` | `page.goto(SITE_URL, wait_until="networkidle")` |
| **Películas en cartelera** | `https://api-g.cinepolis.com/v2/billboards/graphql` | `query Movies($countryId, $category, $cinemas, $limit)` |
| **Horarios por cine (`Billboard`)** | `https://api-g.cinepolis.com/v1/billboards/graphql` | `query Billboard($countryId, $cinemaId, $timezone, $isOffSelectorDays)` |
| **Precios de entradas (`Tickets`)** | `https://api-g.cinepolis.com/v1/ticket/graphql` | `query Tickets($countryId, $sessionId, $cinemaVistaId)` |
| **Posters / Media CDN** | `https://tickets-static-content.cinepolis.com` | Concatenado con `sizes.large` + `resource` |
| **URL de detalle (guardada en DB)** | `https://cinepolis.com/cl/pelicula/{slug}` | Link externo de referencia en `Movie.detail_url` |

### Cines configurados actualmente (`CINEMAS` y `CINEMA_VISTA_IDS`)
- `cinepolis-vivo-imperio-santiago-centro` → **Cinépolis Vivo Imperio** (`cinemaVistaId: "916"`)
- `cinepolis-estacion-central-santiago-centro` → **Cinépolis Estación Central** (`cinemaVistaId: "712"`)

---

## 2. Contexto del Cambio en el Sitio (`cinepolis.com/cl`)

En la interfaz web actual de Cinépolis Chile:
1. Al entrar a `https://cinepolis.com/cl`, más abajo aparecen dos pestañas: **`Cartelera`** y **`Horarios`**, junto al selector **`Elige tu cine`** (botón `Cines`).
2. Al clickear **`Horarios`** y elegir **`Vivo Imperio`**, se listan las películas con pestañas de fechas (`Hoy`, `Mañana`, etc.) y píldoras de horarios (ej. `20:50`).
3. Al clickear un horario (`20:50`), la web navega a la vista **`Asientos`** (`Horario > Asientos > Comida > Pago`), donde:
   - Aparece la barra **`PANTALLA | Sala 3`** y en el panel derecho (`Tu carrito`) dice **`Sala: 3`**.
   - Se dibuja la grilla completa de butacas (filas `A`, `B`, `C`... con asientos numerados `16` a `1`, indicando `Seleccionado`, `Disponible`, `Ocupado`).
   - Todas las peticiones de fondo siguen siendo llamadas `graphql` hacia `https://api-g.cinepolis.com` (visibles en DevTools → Red → XHR).
4. Al clickear **`Seleccionar mis boletos`**, se abre el modal **`Selecciona tus boletos`** con los tipos de entrada y precios.

---

## 3. Plan de Ejecución Paso a Paso

### Fase 0: Diagnóstico e Intercepción GraphQL ("Solo si es necesario")

Antes de reemplazar las llamadas GraphQL actuales por clicks lentos de UI, verificar si los endpoints actuales siguen funcionando y capturar la query GraphQL que trae la **Sala** y el **Mapa de Asientos**.

#### Paso 0.1 — Probar si el scraper actual sigue funcionando
Ejecutar en terminal:
```bash
python3 -c "
import asyncio
from src.scraper.rate_limiter import RateLimiter
from src.scraper.cinepolis import fetch_cinepolis
movies, showtimes, prices = asyncio.run(fetch_cinepolis(RateLimiter()))
print(f'Movies: {len(movies)}, Showtimes: {len(showtimes)}, Prices: {len(prices)}')
"
```
- **Si devuelve `Movies > 0`, `Showtimes > 0`, `Prices > 0`:** No romper ni reemplazar `_MOVIES_QUERY`, `_BILLBOARD_QUERY` ni `_TICKETS_QUERY`. Solo extenderlos con la información de salas y butacas.
- **Si devuelve `0` o falla (401/400):** Seguir al Paso 0.2 para actualizar `_API_KEY`, URLs o payloads.

#### Paso 0.2 — Script de descubrimiento de GraphQL (Sala + Butacas + Boletos)
Crear un script temporal en `scratch_discover_cinepolis.py` (y borrarlo al terminar) o ejecutar vía `python3 -c` con Playwright para interceptar todas las llamadas a `api-g.cinepolis.com` durante el flujo de usuario:

```python
# Flujo a automatizar en el script de inspección:
# 1. Ir a https://cinepolis.com/cl
# 2. Registrar page.on("request") y page.on("response") filtrando "api-g.cinepolis.com"
# 3. Clickear tab "Horarios" -> Clickear "Elige tu cine" / "Cines" -> Elegir "Vivo Imperio"
# 4. Clickear el primer horario disponible (ej. "20:50") para entrar a la vista "Asientos"
# 5. Esperar a que cargue "PANTALLA | Sala" y las filas de asientos
# 6. Imprimir:
#    - URL del endpoint GraphQL de asientos/sala (ej. /v1/seat/graphql o /v1/ticket/graphql)
#    - operationName, query string completo y variables enviadas
#    - Estructura JSON de respuesta (nombre de sala, filas, asientos, coordenadas, fotos si hay)
```

**Qué buscar específicamente en los JSON capturados:**
1. En la respuesta de `Billboard` (`billboardByCinema`): revisar si `showtimes` ya incluye un campo como `screenName`, `screenNumber`, `hall` o `vistaSessionId` que no estábamos pidiendo en `_BILLBOARD_QUERY`.
2. En la petición GraphQL que se dispara al entrar a **`Asientos`**:
   - Identificar la query (probablemente recibe `countryId: "CL"`, `cinemaVistaId: "916"`, `sessionId: "..."`).
   - Ver cómo vienen estructuradas las filas (`rows`), las butacas (`seats`: número, fila, columna/posición X-Y, tipo de asiento, estado `available`/`occupied`) y el nombre de la sala (`screenName` / `Sala 3`).
   - Revisar si el JSON o el DOM de la página incluye alguna URL de imagen/foto de la sala.

---

### Fase 1: Actualizar el Scraper (`src/scraper/cinepolis.py`)

#### 1.1. Solo si `Movies` / `Billboard` requieren interacción UI
- **Si GraphQL directo sigue funcionando (lo más probable):** Mantener `page.evaluate(fetch(...))` porque es 10x más rápido y menos propenso a romperse por cambios de CSS.
- **Solo si Cloudflare o Cinépolis bloquea `fetch()` sin interacción previa:**
  Agregar helper `_navigate_to_cinema_schedules(page, cinema_label)`:
  1. `await page.get_by_text("Horarios", exact=True).click()`
  2. `await page.get_by_text("Elige tu cine").click()` (o botón `Cines`)
  3. Seleccionar `"Vivo Imperio"` / `"Estación Central"`
  4. Esperar respuesta de `api-g.cinepolis.com`.

#### 1.2. Extraer el nombre de la Sala (`room_name` / `screen_name`)
1. Si `Billboard` GraphQL soporta el campo de sala dentro de `showtimes` (ej. `screenName` o `screen`), agregarlo directamente a `_BILLBOARD_QUERY` para que **cada horario** tenga su sala sin hacer requests extra.
2. Si el nombre de la sala solo viene en el endpoint de `Asientos` (`Seats` GraphQL):
   - Extraerlo de la respuesta de asientos por `sessionId` (ej. `"Sala 3"`).

#### 1.3. Extraer Mapa de Butacas y Foto de la Sala por cada Sala
Para no hacer 350 llamadas a `Asientos` en cada scrape (una por horario), optimizar así:
1. Agrupar sesiones por `(cinema_id, room_name)` (o si `room_name` no se conoce antes de consultar asientos, muestrear **1 `sessionId` por película/formato** en cada cine hasta cubrir todas las salas activas del cine, p. ej. Salas 1 a 8).
2. Por cada sesión muestreada, llamar a la query GraphQL de **Asientos** (descubierta en Fase 0):
   - Extraer:
     - `cinema_name`: `"Cinépolis Vivo Imperio"` / `"Cinépolis Estación Central"`
     - `room_name`: ej. `"Sala 3"`
     - `format`: ej. `"2D"`, `"VIP"`, `"IMAX"`, etc.
     - `photo_url`: URL de foto de la sala si existe en la API/DOM, o tomar un screenshot de la grilla de asientos si se navega por UI (`docs/salas/`).
     - `rows`: lista de filas (`A`, `B`, `C`...), cada una con sus butacas ordenadas de izquierda a derecha (tal como se ve en pantalla: `16, 15, ..., 1`, incluyendo espacios de pasillo `aisle` donde haya saltos en `columnIndex` / `position`).
     - `total_seats`: conteo total de butacas de la sala.
3. Si una misma sala (`(cinema_name, room_name)`) ya fue escaneada, no repetir su topología.

#### 1.4. Precios desde el modal "Selecciona tus boletos"
- Si `_TICKETS_QUERY` (`https://api-g.cinepolis.com/v1/ticket/graphql`) sigue respondiendo directamente con `sessionId` y `cinemaVistaId`, mantenerlo.
- Si ahora requiere estado de sesión previo o cambió la firma de la query al abrir el modal **`Selecciona tus boletos`** (tras clickear `Seleccionar mis boletos`), actualizar `_TICKETS_QUERY` con el payload capturado en Fase 0.

---

### Fase 2: Modelo de Datos y API (Opcional / Ligero)

1. **`Showtime` (`src/db/models.py` y `src/api/schemas.py`):**
   - Si el nombre de la sala (`room_name`, ej. `"Sala 3"`) está disponible en el horario, agregar columna opcional `room_name = Column(String, nullable=True)` en `Showtime` (y en `ShowtimeOut` / `MovieShowtimeOut`).
   - Nota sobre SQLite sin migraciones: en `src/db/migrations.py`, agregar un bloque seguro con `ALTER TABLE showtimes ADD COLUMN room_name TEXT` ignorando error si la columna ya existe.
2. **Datos de Salas y Butacas (`data/cinepolis_rooms.json`):**
   - Guardar la estructura completa de salas y mapas de butacas en `data/cinepolis_rooms.json` en cada scrape exitoso para no complejizar SQLite con cientos de filas de coordenadas de asientos.

---

### Fase 3: Generar HTML Visualizador de Salas y Butacas (`docs/SALAS_CINEPOLIS.html`)

Crear un módulo `src/scraper/rooms_html.py` con una función `generate_rooms_html(rooms_data: list[dict], output_path: str = "docs/SALAS_CINEPOLIS.html")` (que se invoca automáticamente al final de `fetch_cinepolis` o `run_scrape`, y también puede correrse standalone).

#### Requisitos visuales de `docs/SALAS_CINEPOLIS.html`:
1. **Diseño:**
   - Tema oscuro limpio consistente con `docs/FLOWS.html` (`background: #0d1117`, tarjetas `#161b22`), más el estilo del mapa de asientos de Cinépolis.
   - Navegación superior por cine (**Cinépolis Vivo Imperio**, **Cinépolis Estación Central**) y chips para saltar a cada sala (`Sala 1`, `Sala 2`, `Sala 3`...).
2. **Por cada Sala mostrar:**
   - **Encabezado:** Nombre del cine + **`Sala X`** + formato(s) detectados + **Capacidad total** (ej. `184 butacas en 12 filas`).
   - **Foto de la sala:** Si Cinépolis provee imagen de la sala o foto del tipo de sala, mostrarla; si no hay foto oficial en el payload, indicarlo limpiamente o mostrar captura.
   - **Barra de pantalla:** Barra gris redondeada superior con el texto **`PANTALLA | Sala X`** (igual a la captura 3).
   - **Plano de butacas dibujado en HTML/CSS:**
     - Cada fila con su letra a la izquierda (`A`, `B`, `C`...).
     - Cada butaca dibujada como un recuadro redondeado (`border: 1.5px solid #6b7280; border-radius: 6px; width: 32px; height: 32px`) con su número adentro (`16`, `15`, ..., `1`).
     - Respetar los **pasillos (espacios vacíos)** usando una celda invisible del mismo ancho cuando la coordenada X/columna de la API salte posiciones.
     - Distinguir con ícono o color si la API marca asientos especiales (silla de ruedas / preferencial) o estado (`Disponible` vs `Ocupado` en la función muestreada).

---

### Fase 4: Verificación y Tests

1. **Tests unitarios (`tests/test_cinepolis_rooms.py`):**
   - Testear el parser del payload de asientos/sala con un fixture JSON real capturado en la Fase 0.
   - Verificar que `generate_rooms_html()` genera `docs/SALAS_CINEPOLIS.html` válido con las filas, números de butaca y nombre de sala (`PANTALLA | Sala 3`).
2. **Prueba end-to-end:**
   - Correr `pytest` y confirmar que todos los tests pasan.
   - Abrir o verificar que `docs/SALAS_CINEPOLIS.html` se haya generado con todas las salas encontradas de Vivo Imperio y Estación Central.

---

## 4. Criterios de Aceptación (Checklist para el modelo ejecutor)

- [ ] Fase 0 ejecutada: confirmadas qué queries GraphQL siguen activas y cuál es la query exacta de `Asientos` / `Sala`.
- [ ] `src/scraper/cinepolis.py` obtiene películas, horarios, precios y además extrae nombre de sala (`Sala X`) + mapa de butacas.
- [ ] `docs/SALAS_CINEPOLIS.html` generado con todas las salas listadas y sus planos de butacas dibujados (filas `A, B, C...` y asientos numerados como en el sitio oficial).
- [ ] `pytest` pasa sin regresiones.
