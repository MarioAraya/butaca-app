# LOG — Butaca

Changelog generado desde historial git (no existía CHANGELOG previo).

## 2026-07-24
- fix(frontend): regenerar package-lock.json (drift de deps opcionales de rollup)
- fix(frontend): refrescar package-lock.json para `npm ci`

## 2026-07-23
- deploy: frontend movido a GitHub Pages, VPS pasa a servir solo la API

## 2026-07-22
- docs: notas de sesión, permisos de deploy Vercel

## 2026-07-18
- fix(scraper): reintento de sesión de scrape de Cinépolis ante fallos transitorios
- debug: exponer `ScrapeLog.errors` en endpoint admin de scrape-logs

## 2026-07-16
- docs: agregar RUNBOOK, actualizar README, preparar deploy VPS con Traefik
- fix(scraper): manejar nuevo formato de header de semana same-month de Normandie
- fix(scraper): fallback a `original_title` en búsquedas OMDb
- feat(scraper): reescritura completa del scraper de Cinépolis para cinepolis.com/cl vía Playwright (reemplaza integración anterior, agrega manejo de Cloudflare)

## 2026-07-12
- feat(scraper): rating IMDb vía OMDb API
- feat(logging): middleware de logging de requests custom + silenciar logs de assets estáticos

## 2026-06-25
- chore: `frontend/shot.mjs` y `CURRENT.md`

## 2026-06-06
- feat(frontend): filtro de cine + layout desktop
- docs: actualizar CLAUDE.md con scraper Normandie y arquitectura frontend

## 2026-06-01
- feat(scraper): agregar scraper de cine Normandie

## 2026-05-21
- fix: usar https para VITE_API_URL (bloqueo de mixed content)

## 2026-05-20
- chore: remover scrapers Playwright muertos
- ci: actualizar .drone.yml
- feat: búsqueda de trailer en YouTube vía yt-dlp cuando la API no trae uno
- fix: remover playwright, agregar DNS en CI, agregar modal de detalle de película
- fix: purgar showtimes de fechas pasadas al iniciar el scrape
- feat: scrape al arranque si no hubo scrape exitoso hoy

## 2026-04-29
- chore: trigger ci/cd
- chore: docker-compose usa IP directa en vez de gitea.lab
- ci: pipeline de frontend, paths `~/cine/` y puertos explícitos

## 2026-04-11
- first commit
