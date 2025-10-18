# 📋 COMANDOS IMPORTADOS - ANÁLISIS

## ✅ COMANDOS COPIADOS (8 total)

### 1. **explore-plan.md** ⭐ COMANDO PRINCIPAL
**Estado:** Copiado sin cambios (100% universal)
**Tamaño:** 1.7K
**Uso:** `/explore-plan {feature_name}`

**Descripción:**
Workflow completo para planificar features:
1. Create session file
2. Explore codebase
3. Select subagents
4. Create plan
5. Get advice from subagents (in parallel)
6. Update context
7. Ask clarifications (A/B/C format)
8. Iterate until ready

**Aplicable a SocialLab:** ✅ SÍ (sin cambios)

---

### 2. **implement-feedback.md**
**Estado:** Adaptado para SocialLab
**Tamaño:** 2.7K
**Uso:** `/implement-feedback {issue_number}`

**Cambios realizados:**
- ✅ Adaptado ejemplo de tests (gurusup → SocialLab)
- ✅ Añadido sección frontend tests
- ✅ Mantenido estructura de workflow

**Workflow:**
1. Setup (fetch branches, get issue)
2. Analysis (read issue + comments)
3. Implementation (con tests)
4. Report status
5. Monitor PR hasta deploy
6. Fix validations en loop

**Aplicable a SocialLab:** ✅ SÍ (adaptado)

---

### 3. **start-working-on-issue-new.md**
**Estado:** Copiado sin cambios
**Tamaño:** 2.6K
**Uso:** `/start-working-on-issue-new {issue_number}`

**Workflow:**
1. Setup (fetch, get issue title)
2. Worktree phase (create branch)
3. Analysis (read issue + comments)
4. Implementation (tests first)
5. Create/Update PR
6. Monitor validations

**Aplicable a SocialLab:** ✅ SÍ (universal)

---

### 4. **create-new-gh-issue.md**
**Estado:** Copiado sin cambios
**Tamaño:** 2.1K
**Uso:** `/create-new-gh-issue {description}`

**Workflow:**
1. Analysis (review context + code)
2. Draft issue con estructura:
   - Problem Statement
   - User Value
   - Definition of Done
   - Manual Testing Checklist
3. Review con usuario
4. Create issue con `gh issue create`

**Aplicable a SocialLab:** ✅ SÍ (universal)

---

### 5. **update-feedback.md**
**Estado:** Copiado sin cambios
**Tamaño:** 881B
**Uso:** `/update-feedback {issue_number}`

**Workflow:**
1. Setup (fetch, get issue)
2. Analysis (read issue + PR + comments)
3. Obtain feedback (use @qa-criteria-validator)
4. Decision (approve o feedback adicional)

**Aplicable a SocialLab:** ✅ SÍ (universal)

---

### 6. **analyze_bug.md**
**Estado:** Copiado sin cambios
**Tamaño:** 129B
**Uso:** `/analyze_bug {sentry_issue}`

**Descripción:** Investigar issue de Sentry (solo investigar, no actuar)

**Aplicable a SocialLab:** ✅ SÍ (si usas Sentry)

---

### 7. **worktree.md**
**Estado:** Copiado sin cambios
**Tamaño:** 694B
**Uso:** `/worktree {issue_number}`

**Workflow:**
1. Create worktree: `.trees/feature-issue-{number}`
2. CD to worktree
3. Activate plan mode
4. Analyze issue
5. Determine subagents (parallel si es posible)
6. Show plan to user
7. Commit + push after confirmation

**Aplicable a SocialLab:** ✅ SÍ (universal)

---

### 8. **rule2hook.md**
**Estado:** Copiado sin cambios
**Tamaño:** 6.4K
**Uso:** `/rule2hook {rules_or_file}`

**Descripción:**
Convierte reglas en lenguaje natural a hooks de Claude Code.

**Eventos soportados:**
- PreToolUse (antes de ejecutar tool)
- PostToolUse (después de ejecutar tool)
- Stop (al terminar)
- Notification (al notificar)

**Aplicable a SocialLab:** ✅ SÍ (universal)

---

## 📊 ESTADÍSTICAS

| Comando | Tamaño | Estado | Cambios |
|---------|--------|--------|---------|
| explore-plan.md | 1.7K | ✅ Universal | 0 |
| implement-feedback.md | 2.7K | ✅ Adaptado | Ejemplos de tests |
| start-working-on-issue-new.md | 2.6K | ✅ Universal | 0 |
| create-new-gh-issue.md | 2.1K | ✅ Universal | 0 |
| update-feedback.md | 881B | ✅ Universal | 0 |
| analyze_bug.md | 129B | ✅ Universal | 0 |
| worktree.md | 694B | ✅ Universal | 0 |
| rule2hook.md | 6.4K | ✅ Universal | 0 |

**Total:** 8 comandos (17.5K de código reutilizado)

---

## 🎯 COMANDOS CLAVE PARA SOCIALLAB

### Workflow Típico de Desarrollo

**1. Crear nuevo feature:**
```bash
/explore-plan instagram_scheduling
```
- Crea `.claude/sessions/context_session_instagram_scheduling.md`
- Consulta agentes en paralelo
- Plan completo antes de implementar

**2. Trabajar en issue:**
```bash
/start-working-on-issue-new 42
```
- Crea worktree
- Analiza issue
- Implementa con tests
- Crea PR

**3. Implementar feedback:**
```bash
/implement-feedback 42
```
- Lee feedback del issue
- Implementa cambios
- Actualiza PR
- Monitorea hasta deploy

**4. Validar feature:**
```bash
/update-feedback 42
```
- Usa @qa-criteria-validator
- Valida con Playwright
- Reporta resultados

---

## 🔧 COMANDOS AUXILIARES

**Crear issue:**
```bash
/create-new-gh-issue "Agregar soporte para Instagram Reels"
```

**Trabajar con worktrees:**
```bash
/worktree 42
```

**Convertir reglas a hooks:**
```bash
/rule2hook "Format Python files with black after editing"
```

**Analizar bug (Sentry):**
```bash
/analyze_bug SENTRY-123
```

---

## ✅ VALIDACIÓN

```bash
# Verificar que todos los comandos están
ls -l .claude/commands/
# Debe mostrar 8 archivos .md

# Probar comando principal
# (En Claude Code IDE)
/explore-plan test_feature
```

---

## 📝 NOTAS IMPORTANTES

1. **Todos los comandos usan `gh` CLI:**
   - Asegúrate de tener `gh` instalado: `brew install gh`
   - Autenticar: `gh auth login`

2. **Variables en comandos:**
   - `$ARGUMENT$` se reemplaza automáticamente
   - `{feature_name}` es placeholder manual

3. **Agentes referenciados:**
   - Los comandos asumen que los agentes están en `.claude/agents/`
   - Nombrar agentes con `@agente-name` para invocarlos

4. **Session files:**
   - Todos los comandos crean/leen `.claude/sessions/context_session_{feature}.md`
   - Este archivo mantiene el contexto entre iteraciones

---

**Última actualización:** 2025-01-18
**Comandos importados:** 8/8 ✅
**Estado:** Listos para usar
