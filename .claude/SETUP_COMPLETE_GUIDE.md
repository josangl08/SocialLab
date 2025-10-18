# 🎯 GUÍA COMPLETA DE CONFIGURACIÓN - SOCIALLAB

## ✅ ARCHIVOS YA CREADOS

### 1. `.claude/project.config.json` ✅
**Ubicación:** `/Users/joseangel/Proyectos/SocialLab/.claude/project.config.json`

**Contenido:** Configuración completa de SocialLab con:
- Stack: Python/FastAPI + React/Vite + Supabase
- Arquitectura: Services (backend) + Feature-based (frontend)
- Testing: pytest + Vitest + Playwright
- Agentes habilitados: 6 agentes especializados
- Comandos de desarrollo
- Convenciones de código

### 2. `.claude/agents/fastapi-backend-architect.md` ✅
**Ubicación:** `/Users/joseangel/Proyectos/SocialLab/.claude/agents/fastapi-backend-architect.md`

**Especialización:**
- FastAPI con service-oriented architecture
- Supabase PostgreSQL (raw SQL)
- APScheduler para jobs
- Instagram Graph API
- Google Gemini AI
- Pillow para imágenes

---

## 📋 ARCHIVOS POR CREAR (PRÓXIMOS PASOS)

### Agentes Faltantes

#### 1. `.claude/agents/react-frontend-architect.md`
```bash
# Crear con:
cat > .claude/agents/react-frontend-architect.md << 'EOF'
---
name: react-frontend-architect
description: Design React frontend with Tailwind, Context API, and Recharts
model: sonnet
color: cyan
---

You are an expert React frontend developer specializing in feature-based
architecture for SocialLab.

## Your Core Expertise
- React 18 with TypeScript
- Vite build tool
- Feature-based component organization
- Context API for global state
- Tailwind CSS for styling
- Recharts for analytics visualization
- React Router for navigation

## SocialLab Feature Structure
```
frontend/src/
├── components/
│   ├── auth/              # Login, Register
│   ├── dashboard/         # Main dashboard
│   ├── posts/             # PostList, PostGenerator
│   ├── calendar/          # CalendarView
│   ├── analytics/         # Analytics charts
│   └── layout/            # MainLayout, Sidebar
├── context/
│   └── AuthContext.tsx    # Authentication state
└── utils/
    └── api.ts             # Axios client
```

## Best Practices
- Components in PascalCase
- Custom hooks start with "use"
- Context for global state only
- Props drilling max 2 levels
- Tailwind for all styling
- TypeScript strict mode

## Output
Save plan in `.claude/doc/{feature_name}/frontend.md`

## Rules
- NEVER do actual implementation
- MUST read context_session_{feature}.md first
- Focus on React 18 patterns
- Include Tailwind utility classes
EOF
```

#### 2. `.claude/agents/python-test-engineer.md`
```bash
cat > .claude/agents/python-test-engineer.md << 'EOF'
---
name: python-test-engineer
description: Design pytest test suites for FastAPI backend
model: sonnet
color: yellow
---

You are an expert Python testing engineer specializing in pytest for
FastAPI applications.

## Testing Framework
- pytest 7+
- pytest-asyncio for async tests
- pytest-cov for coverage
- unittest.mock for mocking

## Test Structure
```
backend/tests/
├── conftest.py              # Shared fixtures
├── test_services/
│   ├── test_caption_generator.py
│   └── test_instagram_publisher.py
├── test_routes/
│   └── test_content_generation.py
└── test_integration/
    └── test_end_to_end.py
```

## Fixtures
```python
# conftest.py
import pytest
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_supabase(mocker):
    return mocker.patch('database.supabase_client.SupabaseClient')
```

## Coverage Target
- Overall: 80%+
- Services: 90%+
- Routes: 80%+

## Output
Save plan in `.claude/doc/{feature_name}/testing.md`
EOF
```

#### 3. `.claude/agents/react-test-engineer.md`
```bash
cat > .claude/agents/react-test-engineer.md << 'EOF'
---
name: react-test-engineer
description: Design Vitest + React Testing Library tests
model: sonnet
color: yellow
---

You are an expert frontend testing engineer for React with Vitest.

## Testing Stack
- Vitest
- React Testing Library
- MSW (Mock Service Worker) for API mocking
- @testing-library/user-event

## Test Structure
```
frontend/src/__tests__/
├── components/
│   ├── Dashboard.test.tsx
│   └── PostGenerator.test.tsx
├── context/
│   └── AuthContext.test.tsx
└── integration/
    └── content-generation-flow.test.tsx
```

## Testing Patterns
```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

describe('PostGenerator', () => {
  it('should generate post on button click', async () => {
    const user = userEvent.setup()
    render(<PostGenerator />)

    await user.click(screen.getByRole('button', { name: /generate/i }))

    await waitFor(() => {
      expect(screen.getByText(/generated caption/i)).toBeInTheDocument()
    })
  })
})
```

## Output
Save plan in `.claude/doc/{feature_name}/frontend_testing.md`
EOF
```

#### 4. `.claude/agents/api-designer.md`
```bash
cat > .claude/agents/api-designer.md << 'EOF'
---
name: api-designer
description: Design RESTful API endpoints for SocialLab
model: sonnet
color: green
---

You are an expert API designer specializing in RESTful conventions.

## API Design Principles
- RESTful resource naming
- Proper HTTP methods (GET, POST, PUT, DELETE)
- Standard status codes
- Pagination for lists
- Filtering and sorting
- API versioning

## SocialLab API Structure
```
/api/
├── /auth/
│   ├── POST   /login
│   ├── POST   /register
│   └── POST   /refresh
├── /content/
│   ├── POST   /generate-caption
│   ├── POST   /generate-image
│   └── GET    /templates
├── /posts/
│   ├── GET    /posts
│   ├── POST   /posts
│   ├── PUT    /posts/:id
│   └── DELETE /posts/:id
├── /schedule/
│   ├── POST   /schedule
│   ├── GET    /scheduled-jobs
│   └── DELETE /jobs/:id
└── /analytics/
    ├── GET    /insights
    └── GET    /best-times
```

## Response Format
```json
{
  "success": true,
  "data": {...},
  "meta": {
    "timestamp": "2025-01-18T00:00:00Z",
    "version": "1.0"
  }
}
```

## Output
Save plan in `.claude/doc/{feature_name}/api_design.md`
EOF
```

#### 5. `.claude/agents/qa-criteria-validator.md` (copiar universal)
```bash
# Este agente es 100% universal, copiar desde claude-code-demo
cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/agents/qa-criteria-validator.md \
   .claude/agents/qa-criteria-validator.md
```

---

### Comandos Universales

```bash
# Crear directorio
mkdir -p .claude/commands

# Copiar comandos 100% universales desde claude-code-demo
cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/explore-plan.md \
   .claude/commands/explore-plan.md

cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/implement-feedback.md \
   .claude/commands/implement-feedback.md

cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/start-working-on-issue-new.md \
   .claude/commands/start-working-on-issue-new.md

cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/create-new-gh-issue.md \
   .claude/commands/create-new-gh-issue.md

cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/update-feedback.md \
   .claude/commands/update-feedback.md

cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/worktree.md \
   .claude/commands/worktree.md
```

---

### settings.json

```bash
cat > .claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": [
      "Bash(mkdir:*)",
      "Bash(find:*)",
      "Bash(mv:*)",
      "Bash(ls:*)",
      "Bash(cp:*)",
      "Bash(touch:*)",
      "Bash(git worktree:*)",
      "Write",
      "Edit",
      "Bash(npm:*)",
      "Bash(python:*)",
      "Bash(pytest:*)",
      "Bash(uvicorn:*)",
      "Bash(pip install:*)",
      "mcp__playwright__*",
      "mcp__context7__*",
      "mcp__sequentialthinking__*"
    ],
    "deny": []
  },

  "enabledMcpjsonServers": [
    "context7",
    "playwright",
    "sequentialthinking"
  ],

  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "echo '✅ Task completed'",
        "timeout": 120
      }]
    }],
    "SubagentStop": [{
      "hooks": [{
        "type": "command",
        "command": "echo '✅ Subagent finished'",
        "timeout": 120
      }]
    }]
  }
}
EOF
```

---

### CLAUDE.md

```bash
cat > CLAUDE.md << 'EOF'
# CLAUDE.md - SocialLab

## Project Overview

SocialLab is an Instagram Content Planner with AI that automates content creation,
scheduling, and publishing for Hong Kong Football League.

**Key Features:**
- AI-powered content generation (Google Gemini 2.0 Flash)
- Template-based image composition (Pillow)
- Instagram Graph API integration (Feed, Reels, Stories)
- Automated scheduling (APScheduler)
- Analytics dashboard (Recharts)

## Tech Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI 0.109.0
- **Architecture**: Service-oriented
- **Database**: Supabase PostgreSQL (raw SQL)
- **Scheduling**: APScheduler
- **AI**: Google Gemini 2.0 Flash
- **Image Processing**: Pillow

### Frontend
- **Language**: TypeScript
- **Framework**: React 18.2.0
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Charts**: Recharts
- **State**: Context API

### Testing
- **Backend**: pytest + pytest-asyncio
- **Frontend**: Vitest + React Testing Library
- **E2E**: Playwright

## Architecture

### Backend Structure
```
backend/
├── main.py                    # FastAPI entry
├── services/                  # Business logic
│   ├── caption_generator.py
│   ├── instagram_publisher.py
│   └── scheduler/
├── routes/                    # API endpoints
├── database/                  # Supabase client
└── tests/
```

### Frontend Structure
```
frontend/src/
├── components/
│   ├── auth/
│   ├── dashboard/
│   ├── posts/
│   └── calendar/
├── context/
└── utils/
```

## Development Commands

**Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000    # Dev server
pytest tests/                             # Run tests
```

**Frontend:**
```bash
cd frontend
npm run dev              # Dev server (port 5173)
npm run test             # Run tests
```

**Fullstack:**
```bash
python start.py          # Start both servers
```

## Sub-Agent Workflow

### Rules
- After plan mode create `.claude/sessions/context_session_{feature_name}.md`
- MUST read context_session file before starting work
- After finishing, MUST update context_session file
- Sub-agents plan, main agent implements

### Workflow
This project uses specialized sub-agents:
- **fastapi-backend-architect**: Backend architecture & services
- **react-frontend-architect**: Frontend components & state
- **python-test-engineer**: Backend testing (pytest)
- **react-test-engineer**: Frontend testing (Vitest)
- **api-designer**: RESTful API design
- **qa-criteria-validator**: Final validation (Playwright)

## Code Writing Standards

- **Simplicity First**: Simple > clever
- **ABOUTME Comments**: All files start with 2-line "ABOUTME:" comment
- **Minimal Changes**: Smallest reasonable changes
- **Style Matching**: Match existing code style
- **No Temporal Naming**: Avoid 'new', 'improved', 'enhanced'

## Version Control

**Git Safety:**
- NEVER update git config
- NEVER run destructive commands
- NEVER skip hooks
- NEVER commit unless asked

**Commit Workflow:**
```bash
# 1. Check status
git status
git diff
git log --oneline -5

# 2. Add files
git add file1.py file2.py

# 3. Commit (Spanish, no AI attribution)
git commit -m "feat(backend): agregar endpoint de programación"
```

## Testing Requirements

**NO EXCEPTIONS POLICY:**
ALL features MUST have:
- Unit tests (pytest for backend, Vitest for frontend)
- Integration tests
- E2E tests (Playwright for critical flows)

Only exception: User EXPLICITLY states "I AUTHORIZE YOU TO SKIP TESTS"

**Coverage Targets:**
- Backend: 80%+
- Frontend: 80%+

## Code Style

### Backend (Python)
- **Formatter**: black (88 chars)
- **Linter**: flake8
- **Import Order**: isort
- **Type Hints**: Required for all functions
- **Docstrings**: Google style

### Frontend (TypeScript)
- **Formatter**: prettier
- **Linter**: eslint
- **Quotes**: single
- **Semi**: true
- **Max Line**: 100 chars

## Path Aliases

**Backend:**
```python
from services.caption_generator import CaptionGeneratorService
from database.supabase_client import SupabaseClient
```

**Frontend:**
```typescript
import { AuthContext } from '@/context/AuthContext'
import { api } from '@/utils/api'
```

## Environment Variables

**Backend (.env):**
```
SUPABASE_URL=...
SUPABASE_KEY=...
GEMINI_API_KEY=...
INSTAGRAM_APP_ID=...
INSTAGRAM_APP_SECRET=...
```

**Frontend (.env):**
```
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=...
```

## Compliance Check

Before submitting work, verify ALL guidelines followed.
If considering exception, STOP and get explicit permission first.
EOF
```

---

## 🚀 SCRIPT DE AUTO-COMPLETADO

```bash
#!/bin/bash
# .claude/scripts/complete-setup.sh

echo "🚀 Completing SocialLab .claude setup..."

# Crear directorios faltantes
mkdir -p .claude/{sessions,doc,hooks}

# Copiar agentes universales (si existen)
if [ -d "/Users/joseangel/Proyectos/claude-code-demo-main/.claude/agents" ]; then
  cp /Users/joseangel/Proyectos/claude-code-demo-main/.claude/agents/qa-criteria-validator.md \
     .claude/agents/ 2>/dev/null && echo "✅ Copied qa-criteria-validator"
fi

# Copiar comandos universales
if [ -d "/Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands" ]; then
  for cmd in explore-plan implement-feedback start-working-on-issue-new create-new-gh-issue update-feedback worktree; do
    cp "/Users/joseangel/Proyectos/claude-code-demo-main/.claude/commands/${cmd}.md" \
       .claude/commands/ 2>/dev/null && echo "✅ Copied ${cmd}.md"
  done
fi

echo ""
echo "📊 Setup Status:"
echo "✅ project.config.json"
echo "✅ agents/fastapi-backend-architect.md"
echo "📋 TODO: Create remaining agents (react-frontend, test engineers, api-designer)"
echo "📋 TODO: Copy universal commands"
echo "📋 TODO: Generate settings.json"
echo "📋 TODO: Generate CLAUDE.md"
echo ""
echo "Next step: Run /explore-plan {feature_name} to test the workflow!"
```

---

## ✅ VALIDACIÓN

```bash
# Verificar estructura
ls -la .claude/
# Debería mostrar:
# - project.config.json ✅
# - agents/ ✅
# - commands/ (pendiente)
# - sessions/ ✅
# - doc/ ✅

# Validar JSON
python3 -m json.tool .claude/project.config.json > /dev/null && echo "✅ JSON válido"

# Contar agentes
ls .claude/agents/ | wc -l
# Objetivo: 6 agentes
```

---

## 🎯 PRÓXIMOS PASOS

1. **Completar agentes faltantes** (copiar los snippets de arriba)
2. **Copiar comandos universales** desde claude-code-demo
3. **Generar CLAUDE.md** (copiar snippet de arriba)
4. **Generar settings.json** (copiar snippet de arriba)
5. **Probar workflow:**
   ```bash
   /explore-plan test_scheduling_feature
   ```

6. **Validar que funciona correctamente**
7. **ENTONCES extraer framework global** a `~/.claude-framework/`

---

**Documento generado:** 2025-01-18
**Estado:** Fase 1 completada (project.config.json + 1 agente)
**Siguiente:** Completar agentes y comandos
