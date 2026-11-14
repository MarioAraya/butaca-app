---
name: wrap-session
description: >-
  Use this skill when the user asks to wrap up the session (/wrap-session) and document session state in CURRENT.md (completed work, in-progress items, blockers, decisions, and next steps).
---

# Wrap Session

Documenta el estado de la sesión antes de terminar. Actualiza `CURRENT.md` (o lo crea) con lo hecho, lo pendiente y contexto para continuar en la próxima sesión.

## Instrucciones

Ejecuta estos pasos en orden:

### 1. Recopilar contexto

Lee los archivos clave del proyecto para entender el estado actual:
- `CURRENT.md` (si existe)
- `AGENTS.md` / `CLAUDE.md` (si existe)
- `features.md` o `features.json` (si existe)
- `plan.md` (si existe)
- Ejecuta `git log --oneline -10` para ver commits recientes
- Ejecuta `git status` para ver cambios sin commitear

### 2. Analizar la sesión

Con base en el historial de conversación y los archivos leídos, identifica:
- **Qué se completó** en esta sesión (con evidencia: archivos cambiados, commits, tests pasando)
- **Qué quedó a medias** (en progreso pero sin terminar)
- **Qué está bloqueado** y por qué
- **Decisiones tomadas** que no están en el código (arquitectura, trade-offs, preferencias)
- **Preguntas abiertas** que necesitan respuesta antes de continuar

### 3. Actualizar CURRENT.md

Crea o sobreescribe `CURRENT.md` en la raíz del proyecto con esta estructura:

```markdown
# CURRENT — {nombre del proyecto}

Última sesión: {fecha actual YYYY-MM-DD}

## En progreso

### {Nombre de la tarea principal}

{Descripción breve de qué se está haciendo y por qué}

**Contexto recopilado:**
- {punto clave de contexto}

**Decisiones tomadas (sin implementar o recién implementadas):**
- {decisión arquitectónica o de diseño}

**Preguntas pendientes antes de continuar:**
1. {pregunta bloqueante}

## Completado esta sesión

- [x] {cosa terminada con evidencia}

## Pendiente (próximos pasos inmediatos)

- [ ] {tarea concreta y accionable}
- [ ] {otra tarea}

## Notas

- {Incidentes, workarounds, cosas raras que pasaron}
- {Comandos útiles descubiertos}
```

### 4. Actualizar features.md / features.json (si aplica)

Si en la sesión se completaron features o se definieron nuevas, marca los checkboxes correspondientes o agrega entradas al backlog. Solo si hay cambios reales — no inventes features completadas.

### 5. Confirmar al usuario

Muestra un resumen de lo que escribiste:
- Archivos actualizados
- Los 3-5 puntos más importantes del `CURRENT.md`
- Próximo paso recomendado para retomar trabajo

No hagas commits automáticamente. El usuario decide si commitear `CURRENT.md`.
