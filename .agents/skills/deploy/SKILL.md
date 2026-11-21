---
name: deploy
description: >-
  Use this skill when the user asks to deploy or run /deploy to push the current branch to origin (GitHub -> Vercel) and/or gitea (Gitea -> Drone CI homelab) simultaneously.
---

# Deploy (Vercel + Drone CI Homelab)

Deploy completo: pushea a `origin` (GitHub → Vercel) y `gitea` (Gitea → Drone CI → homelab).

## Pasos
1. Verificar branch limpio: `git status --short`. Si hay cambios sin commit, abortar y avisar.
2. Branch actual: `git branch --show-current`
3. Push a origin: `git push origin <branch>`
4. Push a gitea: `git push gitea <branch>`
5. Reportar resultado de ambos pushes.
6. Indicar qué pipeline se dispara en cada remote:
   - `origin` → Vercel (ver en https://vercel.com/dashboard)
   - `gitea` → Drone CI (ver en dashboard homelab)

## Argumentos opcionales
- Si el usuario pide `"origin"`: solo pushear a origin (solo Vercel).
- Si el usuario pide `"gitea"`: solo pushear a gitea (solo Drone).
- Si pide `"all"` o sin argumentos: pushear a ambos.

No force-push. No `--no-verify`.
