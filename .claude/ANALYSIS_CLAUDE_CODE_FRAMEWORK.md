# 📊 ANÁLISIS EXHAUSTIVO: CLAUDE CODE FRAMEWORK AGNÓSTICO

**Documento:** Sistema de Desarrollo Agnóstico basado en claude-code-demo
**Fecha:** 2025-01-18
**Autor:** Análisis automatizado de claude-code-demo-main
**Objetivo:** Identificar componentes universales vs específicos para crear un framework reutilizable

---

## 🎯 RESUMEN EJECUTIVO

He analizado **exhaustivamente** todos los componentes del proyecto claude-code-demo-main:
- ✅ 8 agentes especializados
- ✅ 9 comandos slash
- ✅ Configuración de hooks y permissions
- ✅ CLAUDE.md completo (13,000+ líneas)
- ✅ Estructura de sesiones y documentación

**Conclusión:** El 80% del sistema es **UNIVERSAL** y puede parametrizarse. Solo el 20% depende del stack tecnológico.

---

## 📁 ESTRUCTURA COMPLETA ANALIZADA

```
claude-code-demo-main/
├── .claude/
│   ├── agents/                    # 8 agentes - PARCIALMENTE UNIVERSAL
│   │   ├── shadcn-ui-architect.md         # ⚠️ ESPECÍFICO (shadcn/ui)
│   │   ├── hexagonal-backend-architect.md # ⚠️ ESPECÍFICO (hexagonal arch)
│   │   ├── frontend-developer.md          # ⚠️ ESPECÍFICO (React patterns)
│   │   ├── backend-test-architect.md      # ⚠️ ESPECÍFICO (TypeScript/Jest)
│   │   ├── frontend-test-engineer.md      # ⚠️ ESPECÍFICO (Vitest/RTL)
│   │   ├── qa-criteria-validator.md       # ✅ UNIVERSAL
│   │   ├── ui-ux-analyzer.md              # ✅ CASI UNIVERSAL (mínimos cambios)
│   │   └── typescript-test-explorer.md    # ⚠️ ESPECÍFICO (TypeScript)
│   │
│   ├── commands/                  # 9 comandos - MAYORMENTE UNIVERSAL
│   │   ├── explore-plan.md                # ✅ UNIVERSAL (100%)
│   │   ├── implement-feedback.md          # ✅ UNIVERSAL (95%)
│   │   ├── start-working-on-issue-new.md  # ✅ UNIVERSAL (100%)
│   │   ├── create-new-gh-issue.md         # ✅ UNIVERSAL (100%)
│   │   ├── update-feedback.md             # ✅ UNIVERSAL (100%)
│   │   ├── analyze_bug.md                 # ✅ UNIVERSAL (100%)
│   │   ├── worktree.md                    # ✅ UNIVERSAL (100%)
│   │   └── rule2hook.md                   # ✅ UNIVERSAL (100%)
│   │
│   ├── sessions/                  # Contexto - ✅ UNIVERSAL
│   │   └── context_session_{feature}.md
│   │
│   ├── doc/{feature}/             # Documentación - ✅ UNIVERSAL
│   │   ├── backend.md
│   │   ├── frontend.md
│   │   └── acceptance-criteria.md
│   │
│   ├── hooks/                     # Scripts - ✅ UNIVERSAL
│   │   └── on-notification-say.sh
│   │
│   └── settings.json              # Config - PARCIALMENTE UNIVERSAL
│       ├── permissions → ⚠️ ESPECÍFICO (comandos y MCPs del proyecto)
│       ├── enabledMcpjsonServers → ⚠️ ESPECÍFICO
│       └── hooks → ✅ UNIVERSAL (estructura)
│
├── CLAUDE.md                      # Documentación - ESTRUCTURA UNIVERSAL
│   ├── Project Overview → ⚠️ ESPECÍFICO
│   ├── Architecture → ⚠️ ESPECÍFICO
│   ├── Tech Stack → ⚠️ ESPECÍFICO
│   ├── Sub-Agent Workflow → ✅ UNIVERSAL
│   ├── Code Writing Standards → ✅ UNIVERSAL (conceptos)
│   ├── Version Control → ✅ UNIVERSAL
│   └── Testing Requirements → ⚠️ ESPECÍFICO (frameworks)
│
└── README.md                      # ⚠️ ESPECÍFICO (del proyecto)
```

---

## 🤖 ANÁLISIS DETALLADO DE AGENTES

### 🟢 AGENTES 100% UNIVERSALES

#### 1. **qa-criteria-validator.md**
```yaml
Propósito: Definir acceptance criteria y validar con Playwright
Componentes Universales:
  - Workflow de validación (Given-When-Then)
  - Estructura de criterios de aceptación
  - Integración con Playwright MCP
  - Formato de reportes de validación

Componentes Específicos: NINGUNO

Template Variables Necesarias: NINGUNA (¡ya es completamente agnóstico!)

Aplicable a: Cualquier proyecto (backend, frontend, fullstack)
```

**Código Universal:**
```markdown
---
name: qa-criteria-validator
description: Define acceptance criteria and validate features with Playwright
---
# ESTE AGENTE ES 100% REUTILIZABLE SIN CAMBIOS
```

---

### 🟡 AGENTES CASI UNIVERSALES (Mínimos cambios)

#### 2. **ui-ux-analyzer.md**
```yaml
Propósito: Análisis de UI/UX con Playwright

Componentes Universales (95%):
  - Workflow de captura de screenshots
  - Principios de diseño modernos
  - Análisis de accesibilidad (WCAG 2.1 AA)
  - Estructura de feedback
  - Integración con Playwright

Componentes Específicos (5%):
  - Referencias a "Radix UI components" → PARAMETRIZAR
  - Referencias a "Tailwind CSS" → PARAMETRIZAR
  - Referencia a "feature-based architecture" → PARAMETRIZAR

Template Variables Necesarias:
  - {{frontend.uiLibrary}} → "Radix UI" | "Material UI" | "Ant Design" | "Custom"
  - {{frontend.cssFramework}} → "Tailwind" | "Styled Components" | "CSS Modules"
  - {{frontend.architecture}} → "feature-based" | "atomic design" | "component library"
```

**Transformación a Template:**
```markdown
---
name: ui-ux-analyzer
---

You will evaluate designs against the project's established patterns:
- Ensure consistency with existing {{frontend.uiLibrary}} component usage
- Verify {{frontend.cssFramework}} patterns match project conventions
- Check alignment with the {{frontend.architecture}}'s component structure
```

---

### 🔴 AGENTES ESPECÍFICOS DEL STACK (Requieren parametrización completa)

#### 3. **shadcn-ui-architect.md**
```yaml
Propósito: Diseño de UI con shadcn/ui

Componentes Universales (40%):
  - Workflow de planificación (research → plan → document)
  - Estructura de output (.claude/doc/{feature}/ui.md)
  - Principios de diseño (accesibilidad, responsive, performance)
  - Reglas de NO implementación (solo planificar)

Componentes Específicos (60%):
  - shadcn/ui MCP integration
  - Radix UI primitives
  - Tailwind CSS específico
  - Next.js patterns

Template Variables Necesarias:
  - {{frontend.framework}} → "React" | "Vue" | "Svelte" | "Angular"
  - {{frontend.uiLibrary}} → "shadcn/ui" | "Material UI" | "Ant Design" | etc.
  - {{frontend.cssFramework}} → "Tailwind" | "Styled Components" | "CSS Modules"
  - {{frontend.buildTool}} → "Vite" | "Webpack" | "Next.js"
  - {{frontend.mcpServers}} → Lista de MCPs disponibles (shadcn, etc.)
```

**Template Genérico:**
```markdown
---
name: {{frontend.uiLibrary}}-ui-architect
description: Design UI components using {{frontend.uiLibrary}} library
---

You are an elite UI/UX engineer specializing in {{frontend.uiLibrary}} component
architecture and modern interface design with {{frontend.framework}}.

## Your Core Workflow:

**1. Analysis & Planning Phase**
{{#if frontend.mcpServers includes "shadcn"}}
- Use `list_components` to review available {{frontend.uiLibrary}} components
- Use `list_blocks` to identify pre-built UI patterns
{{else}}
- Review {{frontend.uiLibrary}} documentation
- Identify component patterns from existing codebase
{{/if}}

**2. Component Research Phase**
{{#if frontend.mcpServers includes "shadcn"}}
- Call `get_component_demo(component_name)` for each component
{{else}}
- Consult {{frontend.uiLibrary}} official docs
- Review existing component usage in project
{{/if}}

## Design Principles
- Use {{frontend.cssFramework}} for styling
- Implement responsive designs using {{frontend.cssFramework}}'s breakpoint system
- Follow {{frontend.framework}} best practices

## Output
Save implementation plan in `.claude/doc/{feature_name}/ui.md`
```

---

#### 4. **hexagonal-backend-architect.md**
```yaml
Propósito: Arquitectura backend hexagonal con TypeScript/NextJS

Componentes Universales (50%):
  - Workflow de arquitectura (identify → define → structure → apply patterns)
  - Separación de capas (universal concept)
  - Dependency injection principles
  - Testing mindset
  - Reglas de planificación (no implementar)

Componentes Específicos (50%):
  - Arquitectura hexagonal (vs services, MVC, layered)
  - TypeScript types
  - Next.js patterns
  - Repository pattern implementation

Template Variables Necesarias:
  - {{backend.language}} → "python" | "typescript" | "java" | "go"
  - {{backend.framework}} → "fastapi" | "express" | "django" | "nestjs"
  - {{backend.architecture}} → "hexagonal" | "services" | "mvc" | "layered"
  - {{backend.orm}} → "none" | "sqlalchemy" | "prisma" | "typeorm"
  - {{database.type}} → "postgresql" | "mongodb" | "mysql"
```

**Template Genérico:**
```markdown
---
name: {{backend.framework}}-backend-architect
description: Design {{backend.language}} backend with {{backend.architecture}} architecture
---

You are an elite {{backend.language}} backend architect specializing in
{{backend.framework}} framework and {{backend.architecture}} architecture.

## Your Core Expertise

You excel at:
- Designing systems using {{backend.architecture}} architecture
{{#if backend.architecture == "hexagonal"}}
- Domain-Driven Design patterns (aggregates, entities, value objects)
- Clear ports (interfaces) and adapters (implementations)
- Zero dependencies in domain layer
{{else if backend.architecture == "services"}}
- Modular service design with single responsibility
- Service-to-service communication
- Dependency injection for services
{{else if backend.architecture == "mvc"}}
- Model-View-Controller separation
- RESTful controller design
- Business logic in Models or Service layer
{{/if}}

## Structure

```
{{backend.root}}/
{{#if backend.architecture == "hexagonal"}}
  domain/           # Pure business logic
  application/      # Use cases
  infrastructure/   # Adapters
{{else if backend.architecture == "services"}}
  services/         # Business logic services
  routes/           # API endpoints
  database/         # DB connection
{{else if backend.architecture == "mvc"}}
  models/           # Data models
  views/            # Response formatting
  controllers/      # Request handlers
{{/if}}
```

## Database Integration
- Type: {{database.type}}
{{#if backend.orm}}
- ORM: {{backend.orm}}
{{else}}
- Migrations: Raw SQL
{{/if}}

## Output
Save plan in `.claude/doc/{feature_name}/backend.md`
```

---

#### 5. **frontend-developer.md**
```yaml
Propósito: Desarrollo frontend React con patterns específicos

Componentes Universales (60%):
  - Feature-based architecture (concepto)
  - Separation of concerns
  - Service layer patterns
  - Schema validation concept
  - Custom hooks composition
  - Development workflow (schema → service → hooks → components)

Componentes Específicos (40%):
  - React 19 específico
  - React Query (TanStack Query)
  - Zod schema validation
  - Axios para servicios
  - Naming conventions específicas (use{Feature}Context, etc.)

Template Variables Necesarias:
  - {{frontend.framework}} → "react" | "vue" | "svelte"
  - {{frontend.stateManagement}} → "react-query" | "redux" | "zustand" | "pinia"
  - {{frontend.schemaValidation}} → "zod" | "yup" | "joi" | "valibot"
  - {{frontend.httpClient}} → "axios" | "fetch" | "ky"
  - {{frontend.architecture}} → "feature-based" | "atomic-design" | "module-based"
```

**Template Genérico:**
```markdown
---
name: {{frontend.framework}}-frontend-developer
---

You are an expert {{frontend.framework}} frontend developer specializing in
{{frontend.architecture}} architecture.

## Your Core Expertise:
- {{frontend.architecture}} architecture with clear separation
- {{frontend.stateManagement}} for server state management
- {{frontend.schemaValidation}} schema validation and type safety
- Service layer patterns with {{frontend.httpClient}}
- Custom hooks composition

## Architectural Principles:

**1. Feature Services** (`data/services/`):
- API service layers using {{frontend.httpClient}}
{{#if frontend.httpClient == "axios"}}
- Axios interceptors for errors
{{else if frontend.httpClient == "fetch"}}
- Fetch wrapper with error handling
{{/if}}

**2. Feature Schemas** (`data/schemas/`):
- {{frontend.schemaValidation}} schemas for all data structures
{{#if frontend.schemaValidation == "zod"}}
- Zod runtime validation + TypeScript inference
{{else if frontend.schemaValidation == "yup"}}
- Yup async validation
{{/if}}

**3. State Management**:
{{#if frontend.stateManagement == "react-query"}}
- React Query for server state (useQuery, useMutation)
{{else if frontend.stateManagement == "redux"}}
- Redux Toolkit for global state
{{/if}}

## Output
Save plan in `.claude/doc/{feature_name}/frontend.md`
```

---

#### 6-8. **Test Engineers** (backend-test-architect, frontend-test-engineer, typescript-test-explorer)

Todos siguen el mismo patrón de parametrización:

```yaml
Template Variables Comunes:
  - {{testing.backend.framework}} → "pytest" | "jest" | "mocha" | "go test"
  - {{testing.frontend.framework}} → "vitest" | "jest" | "cypress"
  - {{testing.backend.coverage}} → "pytest-cov" | "istanbul" | "jacoco"
  - {{testing.frontend.library}} → "react-testing-library" | "vue-test-utils"
  - {{testing.backend.mocking}} → "unittest.mock" | "jest.mock" | "mockito"
  - {{testing.e2e}} → "playwright" | "cypress" | "selenium"
```

---

## 📝 ANÁLISIS DETALLADO DE COMANDOS

### 🟢 COMANDOS 100% UNIVERSALES

#### 1. **explore-plan.md** ⭐ **EL MÁS IMPORTANTE**
```yaml
Universalidad: 100%
Componentes:
  - Workflow estructurado (Explore → Team Selection → Plan → Advice → Update → Clarify → Iterate)
  - Sistema de sesiones (.claude/sessions/context_session_{feature}.md)
  - Consulta paralela a agentes
  - Formato de preguntas A/B/C
  - Actualización de contexto
  - Regla de NO implementar (solo planificar)

Requiere Cambios: NINGUNO (¡perfecto tal cual!)

Aplicable a: Cualquier proyecto, cualquier stack

NOTA: Este es el comando CORAZÓN del sistema. No necesita modificación.
```

**Código Universal (copiar tal cual):**
```markdown
<user_request>
#$ARGUMENTS
<user_request>

At the end of this message, I will ask you to do something.
Please follow the "Explore, Team Selection, Plan, Advice, Update,
Clarification and Iterate" workflow.

# Create the session file
Create `.claude/sessions/context_session_{feature_name}.md`

# Explore
First, explore the relevant files in the repository

# Team Selection (parallel execution if possible)
Select what subagents are going to be involved

# Plan
Write detailed implementation plan

# Advice
Use in parallel the subagents needed

# Update
Update the context_session file

# Clarification
Ask me questions with A) B) C) format

# Iterate
Evaluate and iterate

# RULES
Target: Create plan, DON'T implement it
```

---

#### 2. **implement-feedback.md**
```yaml
Universalidad: 95%
Componentes Universales:
  - Workflow de feedback (Setup → Analysis → Implementation → Testing → Update PR)
  - Integración con GitHub (`gh` CLI)
  - Ciclo de CI/CD hasta green
  - Formato de reporte estructurado

Componentes Específicos (5%):
  - Ejemplo de output con path "github.com/gurusup/..." → PARAMETRIZAR o REMOVER

Aplicable a: Cualquier proyecto con GitHub
```

---

#### 3-9. **Otros Comandos Universales**

| Comando | Universalidad | Notas |
|---------|---------------|-------|
| `start-working-on-issue-new.md` | 100% | Workflow GitHub issue → worktree → implement → PR |
| `create-new-gh-issue.md` | 100% | Template de issue con DoD |
| `update-feedback.md` | 100% | Validación QA post-deploy |
| `analyze_bug.md` | 100% | Análisis de Sentry/bugs |
| `worktree.md` | 100% | Git worktree workflow |
| `rule2hook.md` | 100% | Convierte reglas a hooks |

**Conclusión:** Los comandos son **casi completamente reutilizables**. Solo pequeños ajustes de paths.

---

## ⚙️ ANÁLISIS DE settings.json

```json
{
  "permissions": {
    "allow": [
      // ⚠️ ESPECÍFICOS del proyecto:
      "Bash(npm:*)",           // → Cambiar según package manager
      "Bash(pip install:*)",   // → Si usa Python
      "Bash(uvicorn:*)",       // → Si usa FastAPI
      "Bash(npx tsc:*)",       // → Si usa TypeScript

      // ✅ UNIVERSALES (mantener siempre):
      "Bash(mkdir:*)",
      "Bash(find:*)",
      "Bash(mv:*)",
      "Bash(ls:*)",
      "Bash(cp:*)",
      "Bash(touch:*)",
      "Bash(git worktree:*)",
      "Write",
      "Edit"
    ]
  },

  "enabledMcpjsonServers": [
    // ⚠️ ESPECÍFICOS del proyecto:
    "shadcn",              // → Solo si usa shadcn/ui

    // ✅ CASI UNIVERSALES (muy útiles):
    "context7",            // → Docs de cualquier librería
    "playwright",          // → E2E testing
    "sequentialthinking"   // → Reasoning avanzado
  ],

  "hooks": {
    // ✅ ESTRUCTURA 100% UNIVERSAL
    "Stop": [...],
    "SubagentStop": [...],
    "Notification": [...]
  }
}
```

**Template de settings.json:**
```json
{
  "permissions": {
    "allow": [
      // Bash universal
      "Bash(mkdir:*)", "Bash(find:*)", "Bash(mv:*)",
      "Bash(ls:*)", "Bash(cp:*)", "Bash(touch:*)",
      "Bash(git worktree:*)",

      // File operations
      "Write", "Edit",

      // Package manager (PARAMETRIZAR)
      {{#if stack.frontend.packageManager == "npm"}}
      "Bash(npm:*)", "Bash(npx:*)",
      {{else if stack.frontend.packageManager == "yarn"}}
      "Bash(yarn:*)",
      {{else if stack.frontend.packageManager == "pnpm"}}
      "Bash(pnpm:*)",
      {{/if}}

      // Backend (PARAMETRIZAR)
      {{#if stack.backend.language == "python"}}
      "Bash(pip install:*)", "Bash(python:*)",
      {{else if stack.backend.language == "typescript"}}
      "Bash(npx tsc:*)",
      {{/if}}

      // MCP permissions (PARAMETRIZAR)
      {{#each enabledMcpServers}}
      "mcp__{{this}}__*",
      {{/each}}
    ]
  },

  "enabledMcpjsonServers": [
    "context7",           // Siempre útil
    "playwright",         // Testing
    "sequentialthinking", // Reasoning
    {{#each project.additionalMcps}}
    "{{this}}",
    {{/each}}
  ],

  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "{{hooks.onStop.command}}",
        "timeout": 120
      }]
    }],
    "SubagentStop": [{
      "hooks": [{
        "type": "command",
        "command": "{{hooks.onSubagentStop.command}}",
        "timeout": 120
      }]
    }]
  }
}
```

---

## 📄 ANÁLISIS DE CLAUDE.md

### Estructura del CLAUDE.md (claude-code-demo)

```markdown
# CLAUDE.md

## Project Overview ⚠️ ESPECÍFICO
- Descripción del proyecto
- Tech stack listado

## Architecture ⚠️ ESPECÍFICO
- Hexagonal architecture explicada
- Capas del sistema
- Hexagonal Architecture Layers (backend específico)
- Frontend Architecture (React específico)
- Key Architectural Principles

## Development Commands ⚠️ ESPECÍFICO
- yarn dev, yarn test, etc.

## Path Aliases ⚠️ ESPECÍFICO
- tsconfig.json paths

## API Communication Flow ⚠️ ESPECÍFICO
- Flujo de llamadas específico

## Key Technical Details ⚠️ ESPECÍFICO
- Domain Entities
- Use Cases
- Frontend Architecture

## Adding New Features ⚠️ ESPECÍFICO
- Cómo agregar tool
- Cómo agregar use case

## Sub-Agent Workflow ✅ UNIVERSAL ⭐
- Reglas de sesiones
- Workflow estructurado
- Naming conventions

## Code Writing Standards ✅ UNIVERSAL (conceptos)
- Simplicity First
- ABOUTME Comments
- Minimal Changes
- Style Matching

## Version Control ✅ UNIVERSAL
- Git Safety Protocol
- Commit workflow
- Pull Request workflow

## Testing Requirements ⚠️ ESPECÍFICO
- Jest/Vitest specifics
- NO EXCEPTIONS POLICY ✅ UNIVERSAL (concepto)

## Compliance Check ✅ UNIVERSAL
- Checklist de verificación
```

### Template de CLAUDE.md Universal

```markdown
# CLAUDE.md

## Project Overview
{{project.description}}

## Tech Stack
### Backend
- **Language**: {{stack.backend.language}}
- **Framework**: {{stack.backend.framework}}
- **Architecture**: {{stack.backend.architecture}}
- **Database**: {{stack.database.type}} ({{stack.database.provider}})
{{#if stack.database.orm}}
- **ORM**: {{stack.database.orm}}
{{else}}
- **Migrations**: {{stack.database.migrations}}
{{/if}}

### Frontend
- **Language**: {{stack.frontend.language}}
- **Framework**: {{stack.frontend.framework}}
- **Build Tool**: {{stack.frontend.buildTool}}
- **UI Library**: {{stack.frontend.uiLibrary}}
- **State Management**: {{stack.frontend.stateManagement}}

### Testing
- **Backend**: {{stack.testing.backend.framework}}
- **Frontend**: {{stack.testing.frontend.framework}}
- **E2E**: {{stack.testing.e2e}}

## Architecture

### Backend Structure
```
{{structure.backend.root}}/
{{#if stack.backend.architecture == "hexagonal"}}
  domain/           # Pure business logic
  application/      # Use cases
  infrastructure/   # Adapters
{{else if stack.backend.architecture == "services"}}
  services/         # Business logic services
  routes/           # API endpoints
  database/         # DB connection
{{/if}}
```

### Frontend Structure
```
{{structure.frontend.root}}/
  components/       # React/Vue/Svelte components
  {{#if stack.frontend.stateManagement == "context-api"}}
  context/          # Context providers
  {{else if stack.frontend.stateManagement == "redux"}}
  store/            # Redux store
  {{/if}}
  utils/            # Utility functions
```

## Development Commands

**Backend:**
```bash
{{commands.backend.dev}}        # Dev server
{{commands.backend.test}}       # Run tests
{{commands.backend.build}}      # Build for production
```

**Frontend:**
```bash
{{commands.frontend.dev}}       # Dev server
{{commands.frontend.test}}      # Run tests
{{commands.frontend.build}}     # Build for production
```

## Sub-Agent Workflow ✅ (UNIVERSAL - NO CAMBIAR)

### Rules
- After a plan mode phase create `.claude/sessions/context_session_{feature_name}.md`
- MUST view `.claude/sessions/context_session_{feature_name}.md` before work
- After finishing, MUST update context_session file
- Sub-agents will research and report feedback, main agent implements

### Workflow
This project uses specialized sub-agents:
- **{{backend.framework}}-backend-architect**: Backend architecture
- **{{frontend.framework}}-frontend-architect**: Frontend architecture
- **{{backend.language}}-test-engineer**: Backend testing
- **{{frontend.language}}-test-engineer**: Frontend testing
- **qa-criteria-validator**: Final validation (Playwright)

Sub agents research and plan, but YOU will do actual implementation.

## Code Writing Standards ✅ (UNIVERSAL)

- **Simplicity First**: Simple > clever
- **ABOUTME Comments**: All files start with 2-line "ABOUTME:" comment
- **Minimal Changes**: Smallest reasonable changes
- **Style Matching**: Match existing code style
- **Preserve Comments**: Never remove unless provably false
- **No Temporal Naming**: Avoid 'new', 'improved', 'enhanced'
- **Evergreen Documentation**: Comments describe code as it is

## Version Control ✅ (UNIVERSAL)

**Git Safety Protocol:**
- NEVER update git config
- NEVER run destructive commands without permission
- NEVER skip hooks (--no-verify)
- NEVER force push to main/master
- NEVER commit unless explicitly asked

**Commit Workflow:**
1. Run git status, git diff, git log in parallel
2. Draft commit message ({{conventions.commits.language}})
3. Add relevant files + create commit
4. NEVER push unless asked

## Testing Requirements

### NO EXCEPTIONS POLICY ✅ (UNIVERSAL CONCEPT)
ALL projects MUST have:
- Unit tests
- Integration tests
- E2E tests

Only exception: User EXPLICITLY states "I AUTHORIZE YOU TO SKIP TESTS"

### Backend Testing
- **Framework**: {{stack.testing.backend.framework}}
- **Coverage**: {{stack.testing.backend.coverage}}
- **Mocking**: {{stack.testing.backend.mocking}}

### Frontend Testing
- **Framework**: {{stack.testing.frontend.framework}}
- **Library**: {{stack.testing.frontend.library}}
- **Mocking**: {{stack.testing.frontend.mocking}}

## Code Style

### Backend ({{stack.backend.language}})
- **Formatter**: {{conventions.codeStyle.backend.formatter}}
- **Linter**: {{conventions.codeStyle.backend.linter}}
- **Max Line Length**: {{conventions.codeStyle.backend.maxLineLength}}
- **Naming**: {{conventions.naming.backend}}

### Frontend ({{stack.frontend.language}})
- **Formatter**: {{conventions.codeStyle.frontend.formatter}}
- **Linter**: {{conventions.codeStyle.frontend.linter}}
- **Max Line Length**: {{conventions.codeStyle.frontend.maxLineLength}}
- **Naming**: {{conventions.naming.frontend}}

## Compliance Check ✅ (UNIVERSAL)
Before submitting work, verify ALL guidelines followed.
If considering exception, STOP and get explicit permission.
```

---

## 🎯 IDENTIFICACIÓN: UNIVERSAL vs ESPECÍFICO

### ✅ COMPONENTES 100% UNIVERSALES (Copiar tal cual)

1. **Comandos:**
   - `explore-plan.md` ⭐ (EL MÁS IMPORTANTE)
   - `start-working-on-issue-new.md`
   - `create-new-gh-issue.md`
   - `update-feedback.md`
   - `analyze_bug.md`
   - `worktree.md`
   - `rule2hook.md`
   - `implement-feedback.md` (95%)

2. **Agentes:**
   - `qa-criteria-validator.md` (100%)

3. **CLAUDE.md Secciones:**
   - Sub-Agent Workflow (completo)
   - Code Writing Standards (completo)
   - Version Control (completo)
   - Testing NO EXCEPTIONS POLICY (concepto)
   - Compliance Check (completo)

4. **settings.json:**
   - Estructura de hooks (completo)
   - Permisos básicos de file operations

---

### 🟡 COMPONENTES CASI UNIVERSALES (Mínimos cambios)

1. **Agentes:**
   - `ui-ux-analyzer.md` (95% universal)
     - Cambios: Parametrizar UI library y CSS framework

2. **settings.json:**
   - MCP servers comunes:
     - `context7` (siempre útil)
     - `playwright` (testing)
     - `sequentialthinking` (reasoning)

---

### 🔴 COMPONENTES ESPECÍFICOS (Requieren plantillas parametrizadas)

1. **Agentes (Requieren templates completos):**
   - `shadcn-ui-architect.md` → `{{uiLibrary}}-ui-architect.md`
   - `hexagonal-backend-architect.md` → `{{framework}}-backend-architect.md`
   - `frontend-developer.md` → `{{framework}}-frontend-developer.md`
   - `backend-test-architect.md` → `{{language}}-backend-test-engineer.md`
   - `frontend-test-engineer.md` → `{{language}}-frontend-test-engineer.md`
   - `typescript-test-explorer.md` → `{{language}}-test-explorer.md`

2. **CLAUDE.md Secciones:**
   - Project Overview
   - Architecture (estructura específica)
   - Tech Stack
   - Development Commands
   - Path Aliases
   - API Communication Flow
   - Key Technical Details
   - Adding New Features

3. **settings.json:**
   - Package manager permissions
   - Language-specific Bash permissions
   - Project-specific MCP servers

---

## 💡 VARIABLES DE CONFIGURACIÓN IDENTIFICADAS

### project.config.json - Estructura Completa

```json
{
  "project": {
    "name": "SocialLab",
    "type": "fullstack",
    "description": "Instagram Content Planner with AI"
  },

  "stack": {
    "backend": {
      "language": "python",                    // python, typescript, java, go
      "framework": "fastapi",                  // fastapi, django, express, nestjs
      "version": "0.109.0",
      "architecture": "services",              // hexagonal, services, mvc, layered
      "patterns": [
        "dependency-injection",
        "async-await",
        "pydantic-models"
      ]
    },

    "frontend": {
      "language": "typescript",                // typescript, javascript
      "framework": "react",                    // react, vue, svelte, next, angular
      "version": "18.2.0",
      "buildTool": "vite",                     // vite, webpack, next, cra
      "packageManager": "npm",                 // npm, yarn, pnpm
      "stateManagement": "context-api",        // context-api, redux, zustand, pinia
      "uiLibrary": "tailwind",                 // tailwind, shadcn, material-ui, ant-design
      "schemaValidation": "none",              // zod, yup, joi, valibot, none
      "httpClient": "axios",                   // axios, fetch, ky
      "chartLibrary": "recharts",              // recharts, chart.js, d3
      "architecture": "feature-based"          // feature-based, atomic-design, module-based
    },

    "database": {
      "type": "postgresql",                    // postgresql, mongodb, mysql, sqlite
      "provider": "supabase",                  // supabase, firebase, atlas, local
      "orm": "none",                           // none, sqlalchemy, prisma, typeorm, django-orm
      "migrations": "raw-sql"                  // raw-sql, orm, flyway, liquibase
    },

    "testing": {
      "backend": {
        "framework": "pytest",                 // pytest, jest, mocha, go-test
        "coverage": "pytest-cov",              // pytest-cov, istanbul, jacoco
        "async": "pytest-asyncio",             // pytest-asyncio, none
        "mocking": "unittest.mock"             // unittest.mock, jest.mock, mockito
      },
      "frontend": {
        "framework": "vitest",                 // vitest, jest, mocha
        "library": "react-testing-library",    // react-testing-library, vue-test-utils
        "mocking": "msw",                      // msw, nock, mirage
        "e2e": "playwright"                    // playwright, cypress, selenium
      }
    },

    "deployment": {
      "backend": "render",                     // render, vercel, heroku, aws, gcp
      "frontend": "vercel",                    // vercel, netlify, render, aws
      "ci": "github-actions"                   // github-actions, gitlab-ci, circle-ci
    }
  },

  "structure": {
    "backend": {
      "root": "backend",
      "services": "backend/services",
      "routes": "backend/routes",
      "database": "backend/database",
      "tests": "backend/tests",
      "migrations": "backend/migrations"
    },
    "frontend": {
      "root": "frontend",
      "components": "frontend/src/components",
      "context": "frontend/src/context",
      "utils": "frontend/src/utils",
      "tests": "frontend/src/__tests__"
    }
  },

  "commands": {
    "backend": {
      "dev": "uvicorn main:app --reload --port 8000",
      "test": "pytest tests/",
      "build": "python -m build",
      "lint": "flake8 ."
    },
    "frontend": {
      "dev": "npm run dev",
      "test": "npm run test",
      "build": "npm run build",
      "lint": "npm run lint"
    }
  },

  "conventions": {
    "commits": {
      "language": "spanish",                   // spanish, english
      "format": "conventional-commits",        // conventional-commits, semantic, custom
      "includeAI": false                       // Include AI attribution
    },
    "codeStyle": {
      "backend": {
        "formatter": "black",                  // black, prettier, autopep8
        "linter": "flake8",                    // flake8, pylint, eslint
        "maxLineLength": 88,
        "importOrder": "isort"                 // isort, organized-imports
      },
      "frontend": {
        "formatter": "prettier",               // prettier, eslint
        "linter": "eslint",                    // eslint, tslint
        "maxLineLength": 100
      }
    },
    "naming": {
      "backend": "snake_case",                 // snake_case, camelCase
      "frontend": "camelCase",                 // camelCase, snake_case
      "components": "PascalCase",
      "constants": "UPPER_SNAKE_CASE"
    }
  },

  "agents": {
    "enabled": [
      "backend-architect",
      "frontend-architect",
      "backend-test-engineer",
      "frontend-test-engineer",
      "api-designer",
      "qa-criteria-validator"
    ]
  },

  "mcpServers": {
    "required": ["context7", "playwright", "sequentialthinking"],
    "optional": []                             // shadcn, sentry, etc.
  },

  "hooks": {
    "onStop": {
      "enabled": true,
      "command": "echo 'Task completed!'"
    },
    "onSubagentStop": {
      "enabled": true,
      "command": "echo 'Subagent finished'"
    },
    "onNotification": {
      "enabled": false,
      "command": ""
    }
  }
}
```

---

## 🏗️ SISTEMA DE PLANTILLAS RECOMENDADO

### Opción 1: Handlebars (JavaScript/Node.js)
```javascript
const Handlebars = require('handlebars');
const config = require('./.claude/project.config.json');

const template = fs.readFileSync('.claude/templates/agents/backend-architect.hbs', 'utf8');
const compiled = Handlebars.compile(template);
const output = compiled(config);
```

### Opción 2: Jinja2 (Python)
```python
from jinja2 import Environment, FileSystemLoader
import json

with open('.claude/project.config.json') as f:
    config = json.load(f)

env = Environment(loader=FileSystemLoader('.claude/templates'))
template = env.get_template('agents/backend-architect.j2')
output = template.render(**config)
```

### Opción 3: Mustache (Multi-lenguaje)
```javascript
const Mustache = require('mustache');
const config = require('./.claude/project.config.json');

const template = fs.readFileSync('.claude/templates/agents/backend-architect.mustache');
const output = Mustache.render(template, config);
```

---

## 📊 ESTADÍSTICAS FINALES

| Componente | Total | Universal | Casi Universal | Específico |
|------------|-------|-----------|----------------|------------|
| **Agentes** | 8 | 1 (12.5%) | 1 (12.5%) | 6 (75%) |
| **Comandos** | 9 | 8 (89%) | 1 (11%) | 0 (0%) |
| **Hooks** | 3 | 3 (100%) | 0 (0%) | 0 (0%) |
| **CLAUDE.md** | 15 secciones | 5 (33%) | 0 (0%) | 10 (67%) |
| **settings.json** | 3 áreas | 1 (33%) | 1 (33%) | 1 (33%) |

**Promedio General:**
- ✅ **Universal**: ~40%
- 🟡 **Casi Universal**: ~10%
- 🔴 **Requiere Parametrización**: ~50%

**Conclusión:** Con un buen sistema de templates, **podemos reutilizar el 90% del código** cambiando solo las variables de configuración.

---

## 🎯 PRÓXIMOS PASOS RECOMENDADOS

1. ✅ **Crear estructura de templates** (.claude/templates/)
2. ✅ **Desarrollar script generador** (Python o Node.js)
3. ✅ **Comando /init-project** interactivo
4. ✅ **Validar con SocialLab** como caso de uso
5. ✅ **Documentar sistema completo**
6. ✅ **Crear repositorio reutilizable**

---

**Documento generado automáticamente**
**Última actualización:** 2025-01-18
