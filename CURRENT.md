# CURRENT — que-ver-cine-hoy

Última sesión: 2026-06-25

## En progreso

### Limpieza del filtro por cine (sin commitear)

Cambios en working tree sin stagear:

- `frontend/src/App.jsx` — removido `CinemaFilter`, su estado (`selectedCinemas`), `allCinemas` memo y lógica de filtro
- `frontend/src/style.css` — removidos estilos `.cinema-filter*` y `.cinema-tab`
- `features.md` — revertido a estado más antiguo: v0.3.0 sin checkboxes completados, sin backlog v0.4.0 scrapers

**No está claro si esta limpieza es intencional o trabajo a medias.** El componente `CinemaFilter.jsx` sigue existiendo en disco pero ya no se usa.

**Preguntas antes de continuar:**
1. ¿La remoción del filtro por cine es definitiva o se va a reimplementar diferente?
2. ¿El `features.md` revertido es intencional o fue un reset accidental?
3. ¿Commitear estos cambios o descartar con `git restore`?

## Completado (sesiones anteriores)

- [x] **Normandie scraper** — `src/scraper/normandie.py`, slugs `normandie-*`, trailer vía yt-dlp
- [x] **Filtro por cine** — `CinemaFilter.jsx` toggle multi-select (actualmente removido del App)
- [x] **Layout desktop** — columnas en desktop, `feat(frontend): add cinema filter and desktop layout`
- [x] **CLAUDE.md** — documentación completa Normandie + arquitectura frontend
- [x] **3 commits pendientes de push** a `gitea/main`:
  - `6ede4c2` feat(scraper): add Normandie cinema scraper
  - `20dfafc` docs: update CLAUDE.md
  - `1a5f63a` feat(frontend): add cinema filter and desktop layout

## Pendiente (próximos pasos inmediatos)

- [ ] Decidir qué hacer con cambios sin stagear (¿commitear remoción del filtro o descartar?)
- [ ] Push a `gitea/main` — `git push gitea main` o `/deploy`
- [ ] Responder 3 preguntas del Proxmox dev env (ver abajo) e implementar `docker-compose.dev.yml` con Vite HMR
- [ ] Scrapers pendientes: El Biógrafo (WordPress, fácil), Cineplanet (API interna probable), Centro Arte Alameda

## Notas

- `CinemaFilter.jsx` existe en `frontend/src/components/` pero no está importado en App.jsx
- `frontend/shot.mjs` — archivo untracked, origen desconocido
- Proxmox dev env: Traefik → `cine.lab` → Vite HMR. Preguntas bloqueantes:
  1. ¿`docker-compose.yml` tiene labels Traefik?
  2. ¿VM en Proxmox tiene el repo clonado?
  3. ¿Auto-pull: cron, webhook, o manual?
- `POST /admin/scrape` es **asíncrono** (devuelve `"Scrape started in background"`)
- Incidente disco lleno Docker (2026-06-02): `docker system prune -a --volumes -f` → 6GB libres
