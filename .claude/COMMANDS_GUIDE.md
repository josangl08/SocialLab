# 📚 Guía de Comandos de Claude Code - SocialLab

**Versión:** 1.0.0
**Fecha:** 2025-10-19

---

## 📑 Tabla de Contenidos

1. [Comandos Disponibles](#-comandos-disponibles)
2. [Flujo de Trabajo para Features](#-flujo-de-trabajo-para-features)
3. [Flujo de Trabajo para Bugs](#-flujo-de-trabajo-para-bugs)
4. [Workflows Avanzados](#-workflows-avanzados)
5. [Ejemplos Prácticos](#-ejemplos-prácticos)

---

## 🎯 Comandos Disponibles

SocialLab tiene **9 comandos** implementados, cada uno diseñado para una fase específica del desarrollo:

### 1️⃣ `/explore-plan {feature_name}`

**Propósito:** 🌟 **COMANDO PRINCIPAL** - Planificar una feature ANTES de implementarla

**Qué hace:**
1. Crea archivo de sesión: `.claude/sessions/context_session_{feature_name}.md`
2. Explora el código actual relevante
3. Selecciona agentes especializados (backend, frontend, testing, QA)
4. Ejecuta agentes **en paralelo** para obtener planes detallados
5. Genera documentación completa en `.claude/doc/{feature_name}/`

**Workflow interno:**
```
Explore → Team Selection → Plan → Advice (parallel) → Update → Clarification → Iterate
```

**Agentes que puede invocar (en paralelo):**
- `fastapi-backend-architect` → `.claude/doc/{feature}/backend.md`
- `react-frontend-architect` → `.claude/doc/{feature}/frontend.md`
- `python-test-engineer` → `.claude/doc/{feature}/backend_testing.md`
- `react-test-engineer` → `.claude/doc/{feature}/frontend_testing.md`
- `api-designer` → `.claude/doc/{feature}/api_design.md`
- `qa-criteria-validator` → `.claude/doc/{feature}/acceptance-criteria.md`

**Cuándo usar:** Al inicio de cualquier feature nueva

**Ejemplo:**
```bash
/explore-plan generacion_captions_ai
```

**Salida:**
- `.claude/sessions/context_session_generacion_captions_ai.md`
- `.claude/doc/generacion_captions_ai/backend.md`
- `.claude/doc/generacion_captions_ai/frontend.md`
- `.claude/doc/generacion_captions_ai/backend_testing.md`
- `.claude/doc/generacion_captions_ai/frontend_testing.md`
- `.claude/doc/generacion_captions_ai/api_design.md`
- `.claude/doc/generacion_captions_ai/acceptance-criteria.md`

**⚠️ IMPORTANTE:** Este comando **NO implementa**, solo **planifica**. Los agentes proponen, tú decides.

---

### 2️⃣ `/create-new-gh-issue {context_session_file}`

**Propósito:** Crear un issue de GitHub bien estructurado basado en un plan

**Qué hace:**
1. Lee el archivo de contexto de sesión
2. Analiza el código relevante
3. Genera un issue completo con:
   - Problem Statement
   - User Value
   - Definition of Done
   - Manual Testing Checklist
4. Te muestra el draft y espera aprobación
5. Crea el issue con `gh issue create`

**Cuándo usar:** Después de `/explore-plan` cuando ya tienes el plan validado

**Ejemplo:**
```bash
/create-new-gh-issue .claude/sessions/context_session_generacion_captions_ai.md
```

**Salida:**
```
Issue creado: #42
URL: https://github.com/tu-org/SocialLab/issues/42
```

---

### 3️⃣ `/start-working-on-issue-new {issue_number}`

**Propósito:** Comenzar a trabajar en un issue de GitHub existente

**Qué hace:**
1. Fetch latest branches
2. Lee el issue completo con `gh issue view {issue_number} --comments`
3. Crea git worktree en `.trees/feature-issue-{number}`
4. Crea rama `feature-issue-{number}`
5. Cambia al worktree
6. Implementa paso a paso con TDD
7. Crea tests antes de implementar
8. Ejecuta tests constantemente
9. Crea PR o actualiza existente
10. Monitorea CI/CD hasta que esté verde

**Cuándo usar:** Cuando vas a implementar un issue existente

**Ejemplo:**
```bash
/start-working-on-issue-new 42
```

**Workflow completo:**
```
Setup → Worktree → Analysis → Implementation → PR → Monitor CI/CD → Green ✅
```

**Reporte de estado:**
```
<results>
  # Summary of the requirements implemented:
    - Servicio CaptionGeneratorService con Gemini AI
    - Endpoint POST /api/content/generate-caption
    - Componente PostGenerator en frontend

  # Requirements pending:
    - Ninguno

  # Tests implemented and their run status (Backend):
    PASSED backend/tests/test_caption_generator.py::test_generate_caption
    PASSED backend/tests/test_caption_generator.py::test_api_error_handling

  # Tests implemented and their run status (Frontend):
    PASSED frontend/src/__tests__/PostGenerator.test.tsx

  # Proof that all builds pass:
    Backend build: ✅ OK
    Frontend build: ✅ OK

  # Overall status: All Completed
  # PR: https://github.com/tu-org/SocialLab/pull/43
</results>
```

---

### 4️⃣ `/implement-feedback {issue_number}`

**Propósito:** Implementar feedback de code review en un PR existente

**Qué hace:**
1. Lee el issue y **TODOS** los comentarios
2. Analiza el feedback del PR
3. Implementa los cambios solicitados
4. Crea tests para los cambios
5. Ejecuta test suite completo
6. Push a la rama existente
7. Actualiza el PR
8. Monitorea CI/CD hasta verde

**Cuándo usar:** Cuando recibes feedback en un PR y necesitas hacer cambios

**Ejemplo:**
```bash
/implement-feedback 42
```

**Diferencia con `/start-working-on-issue-new`:**
- Este trabaja en rama **existente**
- NO crea nuevo worktree
- Enfocado en **iteraciones** de feedback

---

### 5️⃣ `/update-feedback {issue_number}`

**Propósito:** Validar manualmente un PR con Playwright y generar reporte

**Qué hace:**
1. Lee issue y PR completo
2. Analiza los criterios de testing manual
3. **Invoca agente `qa-criteria-validator`** con Playwright MCP
4. El agente navega la URL de deployment
5. Ejecuta los test cases manuales
6. Captura screenshots
7. Genera reporte de validación
8. Comenta en el PR con el reporte
9. Si todo pasa: comenta "ISSUE READY TO MERGE"
10. Si hay errores: lista los problemas encontrados

**Cuándo usar:** Antes de hacer merge para validación E2E manual

**Ejemplo:**
```bash
/update-feedback 42
```

**Output del agente QA:**
```markdown
## QA Validation Report - Issue #42

### ✅ Passed Scenarios (5/6)
- [✅] Caption generation with player stats
- [✅] Error handling for API failures
- [✅] Loading state while generating
- [✅] Caption preview before posting
- [✅] Integration with Instagram publish

### ❌ Failed Scenarios (1/6)
- [❌] Tone selector not changing caption style
  - Expected: Caption changes when selecting "Professional" tone
  - Actual: Caption remains the same
  - Screenshot: qa-screenshots/tone-selector-bug.png

### 📸 Screenshots
- [View all screenshots](qa-screenshots/)

### 🎯 Recommendation
ISSUE NOT READY TO MERGE - 1 failing scenario needs fix
```

---

### 6️⃣ `/worktree {issue_number}`

**Propósito:** Crear git worktree simple para trabajar en un issue

**Qué hace:**
1. Crea worktree en `.trees/feature-issue-{number}`
2. Crea rama `feature-issue-{number}`
3. Cambia al worktree
4. Activa plan mode
5. Analiza el issue
6. Determina agentes necesarios (con `@project-coordinator`)
7. Muestra plan y espera confirmación
8. Después de implementar: commit y push

**Cuándo usar:** Workflow más simple sin la estructura completa de `/start-working-on-issue-new`

**Ejemplo:**
```bash
/worktree 42
```

**Diferencia con `/start-working-on-issue-new`:**
- Más simple y flexible
- Tú controlas la implementación
- No tiene estructura TDD forzada
- Útil para chores o cambios pequeños

---

### 7️⃣ `/worktree-tdd {issue_number}`

**Propósito:** Workflow TDD estricto con git worktrees

**Qué hace:**
1. Crea worktree en `.trees/feature-issue-{number}`
2. Crea rama `feature-issue-{number}`
3. Cambia al worktree
4. Activa plan mode
5. Analiza issue con agentes
6. **Implementa con TDD estricto:**
   - Red: Escribe test que falla
   - Green: Implementa mínimo código para pasar
   - Refactor: Mejora manteniendo tests verdes
   - Repite por cada funcionalidad pequeña
7. Commit y push cuando usuario confirma

**Cuándo usar:** Cuando quieres seguir TDD estricto paso a paso

**Ejemplo:**
```bash
/worktree-tdd 42
```

**Agentes recomendados por tipo de issue:**

**Backend:**
```
1. python-test-engineer → Diseña tests
2. fastapi-backend-architect → Implementa
3. Ciclo: pytest (red) → code (green) → refactor
```

**Frontend:**
```
1. react-test-engineer → Diseña tests
2. react-frontend-architect → Implementa
3. Ciclo: vitest (red) → code (green) → refactor
```

**Full-stack:**
```
1. api-designer → Contrato API
2. python-test-engineer → Tests backend
3. fastapi-backend-architect → Backend
4. react-test-engineer → Tests frontend
5. react-frontend-architect → Frontend
6. ui-ux-analyzer → Validar UX
7. qa-criteria-validator → Acceptance E2E
```

**Beneficios del TDD:**
- ✅ Tests primero = código testable
- ✅ Desarrollo incremental
- ✅ Refactoring seguro
- ✅ Documentación viva

---

### 8️⃣ `/analyze_bug {bug_description}`

**Propósito:** Investigar un bug sin tomar acción

**Qué hace:**
1. Lee el bug description (puede ser issue de Sentry, logs, etc.)
2. Busca código relevante
3. Analiza posibles causas
4. Identifica archivos involucrados
5. Propone hipótesis
6. **NO implementa fix** (solo investiga)

**Cuándo usar:** Cuando necesitas entender un bug antes de arreglar

**Ejemplo:**
```bash
/analyze_bug "Caption generation failing with 500 error when player_stats is empty dict"
```

**Output:**
```markdown
## Bug Analysis

### Bug Summary
Caption generation endpoint returns 500 when player_stats is {}

### Root Cause Analysis
File: backend/services/caption_generator.py:45

The _build_prompt() method assumes player_stats always has keys:
```python
def _build_prompt(self, request: CaptionRequest) -> str:
    goals = request.player_stats['goals']  # KeyError if empty!
```

### Hypothesis
1. No validation for empty player_stats
2. Missing try/catch for KeyError
3. Pydantic model doesn't validate dict contents

### Files Involved
- backend/services/caption_generator.py (contains bug)
- backend/models/caption_request.py (validation needed)
- backend/tests/test_caption_generator.py (add test case)

### Suggested Fix
1. Add Pydantic validator for player_stats
2. Add try/catch with default values
3. Add test: test_generate_caption_with_empty_stats()

### Next Steps
1. Create issue: "/create-new-gh-issue"
2. Implement fix: "/start-working-on-issue-new {issue_number}"
```

---

### 9️⃣ `/rule2hook {rules}`

**Propósito:** Convertir reglas de proyecto en hooks de Claude Code

**Qué hace:**
1. Lee reglas de CLAUDE.md (o del argumento)
2. Analiza qué hooks crear (PreToolUse, PostToolUse, Stop, Notification)
3. Genera configuración JSON de hooks
4. La guarda en settings.json
5. Proporciona resumen de qué se configuró

**Cuándo usar:** Cuando quieres automatizar verificaciones o acciones

**Ejemplo 1:**
```bash
/rule2hook "Format Python files with black after editing"
```

**Output:**
```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|MultiEdit|Write",
      "hooks": [{
        "type": "command",
        "command": "black . --quiet 2>/dev/null || true"
      }]
    }]
  }
}
```

**Ejemplo 2:**
```bash
/rule2hook "Check for hardcoded secrets before saving files"
```

**Output:**
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [{
        "type": "command",
        "command": "git secrets --scan 2>/dev/null || echo 'No secrets found'"
      }]
    }]
  }
}
```

**Hooks disponibles:**
- `PreToolUse` - Antes de usar herramienta (puede bloquear)
- `PostToolUse` - Después de usar herramienta
- `Stop` - Cuando Claude termina
- `Notification` - Cuando hay notificaciones

---

## 🚀 Flujo de Trabajo para Features

### 📋 Workflow Completo: De Idea a Producción

```
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 1: PLANIFICACIÓN                        │
└─────────────────────────────────────────────────────────────────┘

1️⃣  /explore-plan {feature_name}
    ↓
    Agentes trabajan en paralelo:
    ├─ fastapi-backend-architect
    ├─ react-frontend-architect
    ├─ python-test-engineer
    ├─ react-test-engineer
    ├─ api-designer
    └─ qa-criteria-validator
    ↓
    Generas documentos en .claude/doc/{feature_name}/
    ├─ backend.md
    ├─ frontend.md
    ├─ backend_testing.md
    ├─ frontend_testing.md
    ├─ api_design.md
    └─ acceptance-criteria.md

2️⃣  Revisar todos los planes generados
    ↓
    Hacer preguntas si algo no está claro
    ↓
    Iterar hasta tener plan completo

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 2: CREAR ISSUE                            │
└─────────────────────────────────────────────────────────────────┘

3️⃣  /create-new-gh-issue .claude/sessions/context_session_{feature}.md
    ↓
    Claude genera issue draft:
    - Problem Statement
    - User Value
    - Definition of Done
    - Manual Testing Checklist
    ↓
    Revisas y apruebas
    ↓
    Issue creado: #42

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 3: IMPLEMENTACIÓN                         │
└─────────────────────────────────────────────────────────────────┘

4️⃣  /start-working-on-issue-new 42
    ↓
    Crea worktree: .trees/feature-issue-42/
    Crea rama: feature-issue-42
    ↓
    Implementa con TDD:
    ┌──────────────────────────────────────┐
    │ Backend:                             │
    │ 1. Test (pytest) → FAIL              │
    │ 2. Code → PASS                       │
    │ 3. Refactor                          │
    │ 4. Commit                            │
    └──────────────────────────────────────┘
    ┌──────────────────────────────────────┐
    │ Frontend:                            │
    │ 1. Test (vitest) → FAIL              │
    │ 2. Code → PASS                       │
    │ 3. Refactor                          │
    │ 4. Commit                            │
    └──────────────────────────────────────┘
    ↓
    Crea PR: #43
    ↓
    Push cambios

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 4: CODE REVIEW                            │
└─────────────────────────────────────────────────────────────────┘

5️⃣  CI/CD ejecuta automáticamente:
    - backend-ci.yml (pytest + flake8)
    - frontend-ci.yml (vitest + prettier)
    - e2e.yml (Playwright)
    ↓
    Esperar resultados...
    ↓
    ¿Todo verde? → Continúa
    ¿Algo rojo? → Fix con /implement-feedback 42

6️⃣  Code review manual
    ↓
    Reviewer deja comentarios
    ↓
    /implement-feedback 42
    ↓
    Claude lee comentarios
    ↓
    Implementa cambios
    ↓
    Push a PR (actualiza)
    ↓
    Volver a CI/CD...

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 5: QA MANUAL                              │
└─────────────────────────────────────────────────────────────────┘

7️⃣  /update-feedback 42
    ↓
    Agente qa-criteria-validator:
    - Lee acceptance criteria del issue
    - Navega URL de deployment con Playwright
    - Ejecuta test cases manuales
    - Captura screenshots
    - Genera reporte
    ↓
    Comenta en PR con resultados
    ↓
    ¿Todo pasa?
      ├─ SÍ → Comenta "ISSUE READY TO MERGE"
      └─ NO → Lista problemas → /implement-feedback 42

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 6: MERGE & DEPLOY                         │
└─────────────────────────────────────────────────────────────────┘

8️⃣  Merge PR
    ↓
    Deployment automático (Render + Vercel)
    ↓
    Smoke tests post-deploy
    ↓
    Actualizar issue con comentario final
    ↓
    Cerrar issue
    ↓
    Limpiar worktree:
      git worktree remove .trees/feature-issue-42
      git branch -d feature-issue-42

✅ FEATURE COMPLETADA
```

---

## 🐛 Flujo de Trabajo para Bugs

### 📋 Workflow: De Bug Report a Fix

```
┌─────────────────────────────────────────────────────────────────┐
│                    FASE 1: INVESTIGACIÓN                        │
└─────────────────────────────────────────────────────────────────┘

1️⃣  /analyze_bug "Error description or Sentry issue"
    ↓
    Claude investiga:
    - Busca código relevante
    - Analiza posibles causas
    - Identifica archivos
    - Propone hipótesis
    ↓
    Genera reporte de análisis
    ↓
    Revisas el análisis

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 2: CREAR BUG ISSUE                        │
└─────────────────────────────────────────────────────────────────┘

2️⃣  /create-new-gh-issue "Bug: {description}"
    ↓
    Issue creado como [bug] #44

┌─────────────────────────────────────────────────────────────────┐
│                  FASE 3: FIX                                    │
└─────────────────────────────────────────────────────────────────┘

3️⃣  /start-working-on-issue-new 44
    ↓
    Implementa con TDD:
    1. Test que reproduce el bug → FAIL
    2. Fix el código → PASS
    3. Test para regresión → PASS
    4. Refactor si necesario
    ↓
    PR creado

┌─────────────────────────────────────────────────────────────────┐
│              FASE 4: VERIFICACIÓN & MERGE                       │
└─────────────────────────────────────────────────────────────────┘

4️⃣  CI/CD pasa
    ↓
    Code review
    ↓
    /update-feedback 44 (QA)
    ↓
    Merge
    ↓
    Deploy
    ↓
    Verificar que bug no se reproduce

✅ BUG FIXED
```

---

## 🎨 Workflows Avanzados

### Workflow 1: Feature Full-Stack Compleja

**Escenario:** Implementar "Analytics Dashboard con Recharts"

```bash
# Paso 1: Planificar
/explore-plan analytics_dashboard

# Claude invoca agentes en paralelo:
# - api-designer: GET /api/analytics/engagement-stats
# - fastapi-backend-architect: AnalyticsService
# - python-test-engineer: test_analytics_service.py
# - react-frontend-architect: AnalyticsDashboard component
# - react-test-engineer: AnalyticsDashboard.test.tsx
# - ui-ux-analyzer: Dashboard UX analysis
# - qa-criteria-validator: E2E test scenarios

# Paso 2: Crear issue
/create-new-gh-issue .claude/sessions/context_session_analytics_dashboard.md

# Issue #45 creado

# Paso 3: Implementar
/start-working-on-issue-new 45

# Paso 4: Code review
# (Reviewer deja comentarios)

/implement-feedback 45

# Paso 5: QA
/update-feedback 45

# Paso 6: Merge
# ✅ Done
```

---

### Workflow 2: Hotfix Crítico

**Escenario:** Caption generation está caído en producción

```bash
# Paso 1: Analizar urgente
/analyze_bug "Caption generation returns 500 on production"

# Claude identifica el problema

# Paso 2: Crear hotfix issue
/create-new-gh-issue "Hotfix: Caption generation 500 error"

# Issue #46 creado con label [hotfix]

# Paso 3: Fix rápido (sin TDD estricto)
/worktree 46

# Implementas el fix
# Commit y push

# Paso 4: PR urgente
# Skip code review extensivo

# Paso 5: Deploy inmediato
# Merge to main
# Deploy

# Paso 6: Verificar
/update-feedback 46

# ✅ Hotfix deployed
```

---

### Workflow 3: Refactor con TDD

**Escenario:** Refactorizar ImageComposerService para mejor performance

```bash
# Paso 1: Planificar refactor
/explore-plan image_composer_refactor

# Paso 2: Crear issue
/create-new-gh-issue .claude/sessions/context_session_image_composer_refactor.md

# Issue #47 creado

# Paso 3: TDD estricto
/worktree-tdd 47

# Ciclo por cada optimización:
# 1. Test actual (baseline performance)
# 2. Refactor código
# 3. Test nuevo (better performance)
# 4. Todos los tests verdes
# 5. Commit

# Paso 4: Merge
# ✅ Refactor done con tests verdes
```

---

### Workflow 4: Crear Hook Personalizado

**Escenario:** Quieres que Claude ejecute tests automáticamente después de editar

```bash
# Crear hook
/rule2hook "Run pytest on Python files after editing them"

# Claude genera y guarda en settings.json:
# {
#   "hooks": {
#     "PostToolUse": [{
#       "matcher": "Edit|MultiEdit|Write",
#       "hooks": [{
#         "type": "command",
#         "command": "if git diff --name-only | grep -q '\\.py$'; then pytest tests/ -v; fi"
#       }]
#     }]
#   }
# }

# Ahora cada vez que Claude edite un .py, ejecuta pytest
```

---

## 📚 Ejemplos Prácticos

### Ejemplo 1: Nueva Feature "Post Scheduling"

```bash
# PASO 1: PLANIFICACIÓN
/explore-plan post_scheduling

# Claude consulta agentes en paralelo (5-10 min)
# Genera 6 documentos en .claude/doc/post_scheduling/

# PASO 2: REVISAR PLANES
# Lees:
# - backend.md: APScheduler integration con PostgreSQL
# - frontend.md: Calendar component con date picker
# - api_design.md: POST /api/scheduler/schedule-post
# - backend_testing.md: test_scheduler.py casos
# - frontend_testing.md: Calendar.test.tsx
# - acceptance-criteria.md: Criterios E2E

# PASO 3: ITERAR SI NECESARIO
# Preguntas: "¿Cómo manejamos timezone conversions?"
# Claude actualiza plans

# PASO 4: CREAR ISSUE
/create-new-gh-issue .claude/sessions/context_session_post_scheduling.md

# Issue #50 creado

# PASO 5: IMPLEMENTAR
/start-working-on-issue-new 50

# Claude implementa:
# Backend:
#   - PostScheduler service
#   - APScheduler job store
#   - API endpoint
#   - Tests
# Frontend:
#   - Calendar component
#   - Schedule form
#   - Tests

# PR #51 creado

# PASO 6: CODE REVIEW
# Reviewer: "Add error handling for past dates"

/implement-feedback 50

# Claude añade validación y tests

# PASO 7: QA
/update-feedback 50

# QA pasa ✅

# PASO 8: MERGE
# Deployed to production ✅
```

---

### Ejemplo 2: Bug Fix "Instagram OAuth Expired"

```bash
# PASO 1: INVESTIGAR
/analyze_bug "Users can't connect Instagram - OAuth tokens expired"

# Claude output:
# Root Cause: Token refresh logic missing
# File: backend/auth/instagram_oauth.py:78
# No refresh before 60-day expiration

# PASO 2: CREAR BUG ISSUE
/create-new-gh-issue "Bug: Instagram OAuth tokens expire without refresh"

# Issue #52 [bug] creado

# PASO 3: FIX
/start-working-on-issue-new 52

# Claude implementa:
# 1. Test: test_token_refresh_before_expiry()
# 2. TokenRefresher service
# 3. Cron job para refresh automático
# 4. Tests de regresión

# PR #53 creado

# PASO 4: MERGE RÁPIDO
# CI pasa
# Code review aprobado
# Merge
# Deploy

# ✅ Tokens refreshed automatically
```

---

### Ejemplo 3: Refactor "Caption Generator Performance"

```bash
# PASO 1: PLANIFICAR REFACTOR
/explore-plan caption_generator_optimization

# PASO 2: ISSUE
/create-new-gh-issue .claude/sessions/context_session_caption_generator_optimization.md

# Issue #54 [refactor] creado

# PASO 3: TDD REFACTOR
/worktree-tdd 54

# Ciclo 1: Cache de prompts
#   Test: test_prompt_cache_hit()
#   Code: Implementar cache
#   Tests verdes ✅
#   Commit

# Ciclo 2: Async batch processing
#   Test: test_batch_generation()
#   Code: Async batch
#   Tests verdes ✅
#   Commit

# Ciclo 3: Token optimization
#   Test: test_token_usage_reduced()
#   Code: Optimize prompts
#   Tests verdes ✅
#   Commit

# PASO 4: BENCHMARK
# Performance mejoró 3x ✅

# PASO 5: MERGE
# ✅ Optimization deployed
```

---

## 🎯 Mejores Prácticas

### ✅ DO's

1. **Siempre usa `/explore-plan` antes de implementar**
   - Evita retrabajos
   - Los agentes ven cosas que tú podrías pasar por alto

2. **Lee TODOS los documentos generados**
   - Los agentes pueden detectar edge cases
   - La arquitectura propuesta puede ser mejor que tu idea inicial

3. **Itera en la planificación antes de implementar**
   - Más barato arreglar en plan que en código

4. **Usa `/worktree-tdd` para features críticas**
   - Garantiza calidad desde el diseño

5. **Ejecuta `/update-feedback` antes de merge**
   - Validación E2E automatizada con Playwright
   - Captura bugs antes de producción

### ❌ DON'Ts

1. **NO implementes sin planificar**
   - `/explore-plan` existe por algo

2. **NO ignores los tests propuestos**
   - Los agentes diseñan tests completos con edge cases

3. **NO saltes el QA manual**
   - `/update-feedback` automatiza lo tedioso

4. **NO mezcles múltiples features en un issue**
   - Un issue = una feature = un PR

5. **NO olvides limpiar worktrees**
   - `git worktree remove .trees/feature-issue-{number}`

---

## 🔗 Referencias Rápidas

| Comando | Cuándo Usar | Output |
|---------|-------------|---------|
| `/explore-plan` | Inicio de feature | Docs en `.claude/doc/` |
| `/create-new-gh-issue` | Después de plan | GitHub issue |
| `/start-working-on-issue-new` | Implementar issue | PR con código + tests |
| `/implement-feedback` | Aplicar code review | Actualiza PR |
| `/update-feedback` | Validar antes de merge | Reporte QA |
| `/worktree` | Feature simple | Worktree + rama |
| `/worktree-tdd` | Feature con TDD estricto | TDD workflow |
| `/analyze_bug` | Investigar bug | Análisis detallado |
| `/rule2hook` | Crear automatizaciones | Hook en settings.json |

---

## 📖 Recursos Adicionales

- **CLAUDE.md** - Configuración y reglas del proyecto
- **project.config.json** - Metadata completa del stack
- **IMPLEMENTATION_ANALYSIS_REPORT.md** - Análisis vs demo
- **.claude/agents/** - Agentes especializados disponibles

---

**¡Listo para crear features de forma estructurada y profesional!** 🚀
