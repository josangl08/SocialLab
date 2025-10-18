# CLAUDE.md - SocialLab Project

## 📋 Información del Proyecto

**Nombre:** SocialLab
**Descripción:** Instagram Content Planner con generación de captions con IA y programación de posts
**Versión:** 1.0.0
**Stack Tecnológico:**
- **Backend:** FastAPI + Python 3.11+
- **Frontend:** React 18 + TypeScript + Vite
- **Base de Datos:** Supabase PostgreSQL
- **Testing:** pytest + Vitest + Playwright

## 🎯 Arquitectura del Proyecto

### Backend (FastAPI)
- **Arquitectura:** Service-oriented (separación estricta de capas)
- **Estructura:**
  ```
  backend/
  ├── routes/              # API endpoints (FastAPI routers)
  ├── services/            # Lógica de negocio
  ├── models/              # Pydantic models y schemas
  ├── database/            # Conexiones Supabase (raw SQL, no ORM)
  ├── utils/               # Funciones auxiliares
  └── tests/               # Tests con pytest
  ```
- **Convenciones:**
  - Usar async/await para operaciones I/O
  - Dependency injection para servicios
  - Pydantic para validación de datos
  - Raw SQL con Supabase (evitar ORMs)
  - Manejo robusto de errores con HTTPException

### Frontend (React)
- **Arquitectura:** Feature-based (componentes organizados por feature)
- **Estructura:**
  ```
  frontend/src/
  ├── components/          # Componentes por feature
  │   ├── auth/
  │   ├── posts/
  │   ├── calendar/
  │   ├── analytics/
  │   └── layout/
  ├── context/             # Context API (estado global)
  ├── utils/               # Utilidades (api.ts, formatters.ts)
  └── __tests__/           # Tests con Vitest + RTL
  ```
- **Convenciones:**
  - TypeScript strict mode
  - Context API para estado global (auth, theme)
  - Tailwind CSS para estilos (utility-first, no custom CSS)
  - Recharts para visualizaciones
  - React Router para navegación

## 🚀 Flujo de Trabajo con Agentes

### Comando Principal: `/explore-plan {feature_name}`

Este comando inicia el workflow multi-agente:

1. **Exploración** (agente principal)
   - Revisa código actual
   - Lee contexto en `.claude/sessions/context_session_{feature_name}.md`

2. **Consulta Paralela de Agentes Especializados** ⚡
   ```
   ┌─ fastapi-backend-architect  → .claude/doc/{feature}/backend.md
   ├─ react-frontend-architect   → .claude/doc/{feature}/frontend.md
   ├─ python-test-engineer       → .claude/doc/{feature}/backend_testing.md
   ├─ react-test-engineer        → .claude/doc/{feature}/frontend_testing.md
   ├─ api-designer               → .claude/doc/{feature}/api_design.md
   └─ qa-criteria-validator      → .claude/doc/{feature}/acceptance-criteria.md
   ```

3. **Implementación** (agente principal)
   - Lee TODOS los documentos generados
   - Implementa siguiendo las recomendaciones
   - Actualiza `context_session_{feature_name}.md`

4. **Validación**
   - Ejecuta tests (pytest + vitest)
   - Valida con `/implement-feedback`
   - QA criteria con Playwright

### Agentes Disponibles

#### 1. fastapi-backend-architect (🔴 Rojo)
**Especialización:** Backend FastAPI con arquitectura de servicios

**Expertise:**
- FastAPI service-oriented architecture
- Supabase PostgreSQL (raw SQL, no ORM)
- APScheduler para jobs programados
- Instagram Graph API integration
- Google Gemini AI (caption generation)
- Pillow (image processing)
- Async/await patterns

**Output:** `.claude/doc/{feature}/backend.md`

#### 2. react-frontend-architect (🔵 Cyan)
**Especialización:** Frontend React con Tailwind CSS

**Expertise:**
- React 18 + TypeScript + Vite
- Feature-based architecture
- Context API (state management)
- Tailwind CSS (utility-first styling)
- Recharts (analytics charts)
- React Router (client-side routing)
- Axios (API communication)

**Output:** `.claude/doc/{feature}/frontend.md`

#### 3. python-test-engineer (🟡 Amarillo)
**Especialización:** Testing backend con pytest

**Expertise:**
- pytest + pytest-asyncio
- FastAPI TestClient
- unittest.mock (mocking)
- pytest-cov (coverage)
- Testing services, routes, integrations
- Mocking Instagram API, Gemini, Supabase
- Testing APScheduler jobs

**Cobertura objetivo:** 80%+ overall, 90%+ services

**Output:** `.claude/doc/{feature}/backend_testing.md`

#### 4. react-test-engineer (🟡 Amarillo)
**Especialización:** Testing frontend con Vitest

**Expertise:**
- Vitest + React Testing Library
- Testing Library user-event
- MSW (Mock Service Worker)
- Testing Context providers
- Testing async operations
- Testing forms and user input
- Accessibility testing

**Cobertura objetivo:** 80%+ overall

**Output:** `.claude/doc/{feature}/frontend_testing.md`

#### 5. api-designer (🟢 Verde)
**Especialización:** Diseño de APIs RESTful

**Expertise:**
- RESTful resource design
- HTTP methods y status codes
- Pydantic schemas
- Pagination, filtering, sorting
- Error response standards
- OpenAPI documentation
- Rate limiting

**API Structure completa:** 30+ endpoints diseñados

**Output:** `.claude/doc/{feature}/api_design.md`

#### 6. qa-criteria-validator (🟡 Amarillo)
**Especialización:** Validación con Playwright (100% UNIVERSAL)

**Expertise:**
- Definir acceptance criteria (Given-When-Then)
- Playwright MCP integration
- E2E testing automation
- Screenshot capture
- Validation reports
- Test execution

**Output:** Comentarios en PR con reporte de validación

## 📝 Convenciones de Código

### Python (Backend)
```python
# Flake8 estricto (88 caracteres)
# Nombres: snake_case para variables/funciones, PascalCase para clases
# Imports organizados: stdlib → terceros → locales
# Docstrings con triple comillas dobles
# Type hints obligatorios

# Ejemplo:
from typing import Optional
from pydantic import BaseModel

class PostCreate(BaseModel):
    """Schema para crear un nuevo post."""

    image_url: str
    caption: str
    media_type: str = "FEED"

async def create_post(post_data: PostCreate) -> dict:
    """
    Crea un nuevo post en la base de datos.

    Args:
        post_data: Datos del post a crear

    Returns:
        dict: Post creado con ID asignado
    """
    # Implementación...
    pass
```

### TypeScript (Frontend)
```typescript
// TypeScript strict mode
// Nombres: PascalCase para componentes, camelCase para variables
// Props interface obligatoria para cada componente
// Tailwind CSS para estilos (no custom CSS)

// Ejemplo:
interface PostCardProps {
  post: {
    id: string
    imageUrl: string
    caption: string
    status: 'draft' | 'scheduled' | 'published'
  }
}

export function PostCard({ post }: PostCardProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <img src={post.imageUrl} alt="Post" className="w-full h-48 object-cover" />
      <p className="text-gray-700 mt-2">{post.caption}</p>
    </div>
  )
}
```

### Commits
- **Idioma:** Español
- **Formato:** `tipo: descripción concisa (sin emoji 🤖)`
- **Tipos:** feat, fix, refactor, test, docs, style, chore
- **Ejemplos:**
  - `feat: añadir generación de captions con Gemini AI`
  - `fix: corregir error en programación de posts`
  - `test: añadir tests para CaptionGeneratorService`
- **Commits incrementales:** Un commit = una funcionalidad o fix específico
- **NUNCA commitear código que no funciona**

## 🧪 Testing

### Backend (pytest)
```bash
# Ejecutar todos los tests
pytest tests/ -v

# Con coverage
pytest tests/ -v --cov=. --cov-report=html

# Solo un archivo
pytest tests/test_services/test_caption_generator.py -v

# Solo async tests
pytest tests/ -v -m asyncio
```

**Estructura de tests:**
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_generate_caption_success(mock_gemini):
    """Test generación exitosa de caption."""
    # Arrange
    service = CaptionGeneratorService(api_key="test_key")
    request = CaptionRequest(...)

    # Act
    result = await service.generate_caption(request)

    # Assert
    assert result == "Generated caption"
    mock_gemini.GenerativeModel.assert_called_once()
```

### Frontend (Vitest + RTL)
```bash
# Ejecutar tests
npm run test

# Con coverage
npm run test:coverage

# Watch mode
npm run test:watch
```

**Estructura de tests:**
```typescript
import { describe, it, expect } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '@/__tests__/utils/test-utils'

describe('PostGenerator', () => {
  it('should generate caption when button clicked', async () => {
    // Arrange
    const user = userEvent.setup()
    renderWithProviders(<PostGenerator />)

    // Act
    await user.click(screen.getByRole('button', { name: /generate/i }))

    // Assert
    await waitFor(() => {
      expect(screen.getByText(/generated caption/i)).toBeInTheDocument()
    })
  })
})
```

### E2E (Playwright)
```bash
# Ejecutar E2E tests
npx playwright test

# Con UI
npx playwright test --ui

# Solo un test
npx playwright test tests/e2e/post-generation.spec.ts
```

## 🔧 Integraciones Externas

### Instagram Graph API
- **Rate limit:** 200 calls/hour
- **Media types:** FEED, REELS, STORY
- **OAuth flow:** Manejar en componente separado
- **Tokens:** Renovar antes de expiración (60 días)

### Google Gemini AI
- **Modelo:** gemini-2.0-flash
- **Rate limit:** 100 requests/hour (considerar en testing)
- **Token limit:** ~32K tokens
- **Fallback:** Tener estrategia si API falla

### Supabase
- **Database:** PostgreSQL con RLS policies
- **Storage:** Buckets para imágenes de posts
- **Auth:** JWT tokens
- **Real-time:** Subscriptions para updates (opcional)

### APScheduler
- **Jobs:** Persistir en Supabase para sobrevivir restarts
- **Retry:** Max 3 intentos con exponential backoff
- **Orphaned jobs:** Recovery al inicio
- **Timezone:** Usar UTC internamente, convertir al mostrar

## 📂 Estructura de Archivos Importantes

```
SocialLab/
├── .claude/
│   ├── agents/                    # 6 agentes especializados
│   ├── commands/                  # 8 comandos workflow
│   ├── sessions/                  # Contexto por feature
│   ├── doc/                       # Planes generados por agentes
│   ├── project.config.json        # Configuración del proyecto
│   ├── settings.json              # Permisos, MCP, hooks
│   └── CLAUDE.md                  # Este archivo
│
├── backend/
│   ├── routes/                    # API endpoints
│   ├── services/                  # Lógica de negocio
│   ├── models/                    # Pydantic schemas
│   ├── database/                  # Supabase client
│   ├── utils/                     # Helpers
│   └── tests/                     # pytest tests
│
└── frontend/
    ├── src/
    │   ├── components/            # React components
    │   ├── context/               # Context providers
    │   ├── utils/                 # API client, formatters
    │   └── __tests__/             # Vitest tests
    ├── public/                    # Assets estáticos
    └── package.json
```

## 🎨 Patrones Específicos de SocialLab

### Caption Generation Flow
```python
# Backend Service
class CaptionGeneratorService:
    async def generate_caption(self, request: CaptionRequest) -> str:
        prompt = self._build_prompt(request)
        response = await self.model.generate_content_async(prompt)
        return response.text

    def _build_prompt(self, request: CaptionRequest) -> str:
        # Construir prompt basado en template_type
        # Inyectar player_stats, tone, language
        pass
```

### Post Scheduling
```python
# APScheduler Integration
class PostScheduler:
    def schedule_post(self, post_id: str, scheduled_time: datetime):
        job = self.scheduler.add_job(
            func=self._publish_post,
            trigger='date',
            run_date=scheduled_time,
            args=[post_id],
            id=f'post_{post_id}',
            replace_existing=True
        )
        # Persistir en Supabase
        self._save_job_to_db(job)
```

### Analytics Visualization
```typescript
// Recharts Component
import { LineChart, Line, XAxis, YAxis, Tooltip } from 'recharts'

export function EngagementChart({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="likes" stroke="#3b82f6" />
        <Line type="monotone" dataKey="comments" stroke="#10b981" />
      </LineChart>
    </ResponsiveContainer>
  )
}
```

## 🚨 Reglas Importantes

### LOS AGENTES SOLO PLANIFICAN, NO IMPLEMENTAN
- **fastapi-backend-architect:** SOLO propone plan → `.claude/doc/{feature}/backend.md`
- **react-frontend-architect:** SOLO propone plan → `.claude/doc/{feature}/frontend.md`
- **python-test-engineer:** SOLO propone tests → `.claude/doc/{feature}/backend_testing.md`
- **react-test-engineer:** SOLO propone tests → `.claude/doc/{feature}/frontend_testing.md`
- **api-designer:** SOLO propone API → `.claude/doc/{feature}/api_design.md`
- **qa-criteria-validator:** SOLO propone criterios → `.claude/doc/{feature}/acceptance-criteria.md`

**El agente principal lee TODOS estos planes e implementa.**

### Antes de Implementar
1. ✅ Leer contexto en `.claude/sessions/context_session_{feature}.md`
2. ✅ Ejecutar `/explore-plan {feature}` para generar planes
3. ✅ Revisar TODOS los archivos generados en `.claude/doc/{feature}/`
4. ✅ Implementar siguiendo las recomendaciones
5. ✅ Ejecutar tests (pytest + vitest)
6. ✅ Validar con `/implement-feedback`

### Durante Implementación
- ❌ NO mezclar código backend y frontend
- ❌ NO usar ORMs (usar raw SQL con Supabase)
- ❌ NO usar custom CSS (usar Tailwind utilities)
- ❌ NO hardcodear API keys o secrets
- ✅ Usar async/await para operaciones I/O
- ✅ Validar datos con Pydantic (backend) y TypeScript (frontend)
- ✅ Manejar errores gracefully
- ✅ Escribir tests para nueva funcionalidad

### Después de Implementar
1. ✅ Ejecutar linters (flake8 para Python, prettier para TypeScript)
2. ✅ Ejecutar tests completos
3. ✅ Verificar cobertura (80%+ objetivo)
4. ✅ Commits incrementales con mensajes descriptivos
5. ✅ Actualizar documentación si es necesario

## 🔍 Comandos Disponibles

### Workflow de Features
- `/explore-plan {feature}` - ⭐ PRINCIPAL: Inicia workflow multi-agente
- `/implement-feedback` - Valida implementación contra planes
- `/update-feedback {context}` - Actualiza contexto de feature

### Gestión de Issues
- `/start-working-on-issue-new {issue_number}` - Inicia trabajo en issue
- `/create-new-gh-issue` - Crea nuevo issue en GitHub

### Debug y Análisis
- `/analyze_bug {description}` - Analiza y diagnostica bugs
- `/worktree` - Gestiona git worktrees
- `/rule2hook` - Convierte reglas a hooks

## 📚 Recursos

### Documentación Oficial
- **FastAPI:** https://fastapi.tiangolo.com
- **React:** https://react.dev
- **Tailwind CSS:** https://tailwindcss.com
- **Supabase:** https://supabase.com/docs
- **Vitest:** https://vitest.dev
- **Pytest:** https://docs.pytest.org
- **Instagram Graph API:** https://developers.facebook.com/docs/instagram-api
- **Google Gemini:** https://ai.google.dev/docs

### Herramientas MCP
- **context7:** Documentación de librerías actualizada
- **playwright:** Tests E2E automatizados
- **render:** Deploy automatizado

---

**Última actualización:** 2025-01-18
**Versión:** 1.0.0
**Estado:** ✅ Configuración completa - Listo para desarrollo
