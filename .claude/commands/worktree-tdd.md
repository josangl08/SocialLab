<github_issue>
#$ARGUMENTS
</github_issue>

# Workflow TDD con Git Worktrees para Issues

Este comando configura un entorno de desarrollo TDD (Test-Driven Development) usando git worktrees para trabajar en un issue de GitHub de forma aislada.

## Pasos del Workflow

1. **Crear git worktree**
   ```bash
   git worktree add ./.trees/feature-issue-$ARGUMENTS -b feature-issue-$ARGUMENTS
   ```
   Crea un worktree en `.trees/feature-issue-{ISSUE_NUMBER}` con una nueva rama.

2. **Cambiar al worktree**
   ```bash
   cd .trees/feature-issue-$ARGUMENTS
   ```

3. **Activar plan mode**
   - Analizar el GitHub issue #$ARGUMENTS
   - Determinar qué agentes de `.claude/agents/` están involucrados
   - Los agentes pueden correr en paralelo si no hay overlapping de tareas
   - Incluso correr instancias paralelas del mismo agente si es necesario
   - **SIEMPRE** mostrar el plan al usuario para confirmación

4. **Trabajar en TDD**
   - **Funcionalidad por funcionalidad, paso a paso**
   - **NO** crear el set completo de tests y luego toda la funcionalidad
   - **Desacoplar** la funcionalidad en piezas pequeñas
   - **Ciclo Red-Green-Refactor:**
     1. Escribir test que falla (Red)
     2. Implementar mínimo código para pasar (Green)
     3. Refactorizar manteniendo tests verdes (Refactor)
     4. Repetir para siguiente pieza

5. **Commit y push**
   - Después de la confirmación del usuario
   - Commit incremental de cada funcionalidad completada
   - Push a la rama feature-issue-$ARGUMENTS

## Agentes Recomendados para TDD

Según el tipo de issue, involucrar:

### Backend Issues
- `python-test-engineer` → Diseñar tests primero
- `fastapi-backend-architect` → Implementar funcionalidad
- Ejecutar: pytest → implementar → pytest (green) → refactor

### Frontend Issues
- `react-test-engineer` → Diseñar tests primero
- `react-frontend-architect` → Implementar componente
- Ejecutar: vitest → implementar → vitest (green) → refactor

### API Issues
- `api-designer` → Diseñar endpoint primero
- `python-test-engineer` → Test del endpoint
- `fastapi-backend-architect` → Implementar endpoint

### UI/UX Issues
- `ui-ux-analyzer` → Analizar requisitos visuales
- `react-test-engineer` → Tests de interacción
- `react-frontend-architect` → Implementar UI

### Full-stack Issues
Orden de ejecución:
1. `api-designer` → Contrato API
2. `python-test-engineer` → Tests backend
3. `fastapi-backend-architect` → Implementar backend
4. `react-test-engineer` → Tests frontend
5. `react-frontend-architect` → Implementar frontend
6. `ui-ux-analyzer` → Validar UX
7. `qa-criteria-validator` → Acceptance criteria E2E

## Ejemplo de Uso

```bash
# Para issue #42: "Añadir generación de captions con IA"
/worktree-tdd 42

# El workflow:
# 1. Crea .trees/feature-issue-42/
# 2. Rama: feature-issue-42
# 3. Analiza issue #42
# 4. Plan sugerido:
#    - api-designer: POST /api/content/generate-caption
#    - python-test-engineer: test_caption_generator.py
#    - fastapi-backend-architect: CaptionGeneratorService
#    - react-test-engineer: PostGenerator.test.tsx
#    - react-frontend-architect: PostGenerator component
# 5. Usuario confirma: "sí, proceder"
# 6. TDD cycle:
#    Test 1: test_generate_caption_with_player_stats() → FAIL
#    Impl 1: CaptionGeneratorService.generate_caption() → PASS
#    Refactor 1: Extract prompt builder
#    Test 2: test_generate_caption_handles_api_error() → FAIL
#    Impl 2: Add try/catch and error handling → PASS
#    ... continúa ...
# 7. Commit + push cuando usuario confirma
```

## Beneficios del TDD Workflow

✅ **Tests primero:** Garantiza que el código sea testable desde el diseño
✅ **Desarrollo incremental:** Pequeñas piezas, cada una probada
✅ **Refactoring seguro:** Tests verdes dan confianza para mejorar código
✅ **Aislamiento:** Git worktree no interfiere con main branch
✅ **Documentación viva:** Los tests documentan el comportamiento esperado

## Limpieza después de merge

Después de hacer merge del PR:

```bash
# Desde el directorio raíz del proyecto
git worktree remove .trees/feature-issue-$ARGUMENTS

# O si el worktree tiene cambios sin commit
git worktree remove --force .trees/feature-issue-$ARGUMENTS

# Eliminar rama remota (después de merge)
git push origin --delete feature-issue-$ARGUMENTS

# Eliminar rama local
git branch -d feature-issue-$ARGUMENTS
```

## Notas Importantes

- ⚠️ **NO** usar `-i` flags en git (git rebase -i, git add -i) - no soportan input interactivo
- ✅ Commits incrementales: Un commit por funcionalidad completada (test + impl + refactor)
- ✅ Mensajes de commit descriptivos en español
- ✅ Ejecutar tests localmente antes de cada commit
- ✅ Push frecuente para backup del trabajo
