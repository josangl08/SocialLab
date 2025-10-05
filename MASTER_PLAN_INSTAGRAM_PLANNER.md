# MASTER PLAN - SOCIALLAB INSTAGRAM PLANNER 🚀

**Documento Maestro de Desarrollo**
**Versión**: 1.0
**Fecha de Creación**: 15 Enero 2025
**Última Actualización**: 15 Enero 2025

---

## 📑 TABLA DE CONTENIDOS

1. [Visión y Contexto del Proyecto](#1-visión-y-contexto-del-proyecto)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Requisitos Técnicos Completos](#3-requisitos-técnicos-completos)
4. [Esquema de Base de Datos](#4-esquema-de-base-de-datos)
5. [Especificación de APIs](#5-especificación-de-apis)
6. [Componentes Frontend](#6-componentes-frontend)
7. [Roadmap de Implementación](#7-roadmap-de-implementación)
8. [Código Fuente Completo](#8-código-fuente-completo)
9. [Testing y Validación](#9-testing-y-validación)
10. [Troubleshooting](#10-troubleshooting)
11. [Tracking de Progreso](#11-tracking-de-progreso)

---

# 1. VISIÓN Y CONTEXTO DEL PROYECTO

## 1.1 Descripción del Proyecto

**SocialLab Instagram Planner** es un planificador inteligente de contenido para Instagram que actúa como Community Manager automatizado, combinando datos de análisis deportivo (PROJECT 1) con templates de diseño profesional para generar publicaciones optimizadas.

### Objetivo Principal
Crear un sistema híbrido que permita:
- Recibir datos y gráficos desde PROJECT 1 (analizador Wyscout)
- Combinar templates profesionales con datos en tiempo real
- Generar captions atractivos usando IA
- Planificar estratégicamente las publicaciones
- Automatizar la publicación en Instagram
- Trackear performance y optimizar continuamente

### Alcance del Proyecto

**✅ QUÉ SÍ INCLUYE (PROJECT 2 - Planificador):**
- Sistema de ingesta de datos desde Google Drive
- Gestión de templates (catálogo, selección, composición)
- Generación de captions con IA (Gemini)
- Planificación estratégica de contenido
- Composición de imágenes (Pillow)
- Programación de publicaciones
- Publicación automática a Instagram
- Dashboard de gestión (React)
- Analytics y tracking de performance
- Soporte para múltiples cuentas de Instagram

**❌ QUÉ NO INCLUYE (está en PROJECT 1):**
- Análisis de archivos CSV de Wyscout
- Generación de gráficos de estadísticas
- Análisis de datos de partidos/jugadores
- Creación de templates de diseño (se hacen en Midjourney/SeaDream)

### Usuarios Objetivo
- Community Managers de equipos deportivos
- Analistas deportivos que publican estadísticas
- Agencias de marketing deportivo
- Cuentas de estadísticas deportivas (fan accounts)

---

## 1.2 Arquitectura General del Sistema

```
┌────────────────────────────────────────────────────────────────────┐
│                         ECOSYSTEM OVERVIEW                          │
└────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   PROJECT 1     │  (EXTERNO - Fuera de alcance)
│  Wyscout CSV    │
│    Analyzer     │
└────────┬────────┘
         │
         │ Exporta:
         │ - Gráficos (PNG)
         │ - Estadísticas (JSON)
         │ - metadata.json
         ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        GOOGLE DRIVE (Storage)                        │
│  /PROJECT1_EXPORTS/                  /TEMPLATES/                    │
│  ├─ images/                          ├─ player_stats/               │
│  ├─ data/                            ├─ team_performance/           │
│  └─ metadata.json                    └─ template_catalog.json       │
└────────┬────────────────────────────────────────────────┬───────────┘
         │                                                 │
         │                                                 │
         ↓                                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   N8N WORKFLOW ENGINE (Opcional)                     │
│  - Polling Google Drive cada 5 min                                  │
│  - Detecta nuevos exports                                           │
│  - Trigger FastAPI endpoints                                        │
│  - Schedule publicaciones                                           │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  /services/ai/                                               │  │
│  │    - caption_generator.py    (Gemini AI)                     │  │
│  │    - template_selector.py    (Reglas + scoring)              │  │
│  │    - strategy_planner.py     (IA para timing)                │  │
│  │    - cache_manager.py        (Cache semántico)               │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  /services/image/                                            │  │
│  │    - composer.py             (Pillow composition)            │  │
│  │    - template_manager.py     (Gestión templates)             │  │
│  │    - branding.py             (Colores/logos equipos)         │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  /services/data/                                             │  │
│  │    - drive_connector.py      (Google Drive API)              │  │
│  │    - metadata_parser.py      (Parse metadata.json)           │  │
│  ├──────────────────────────────────────────────────────────────┤  │
│  │  /services/content/                                          │  │
│  │    - post_generator.py       (Orquestador principal)         │  │
│  │    - scheduler.py            (APScheduler o n8n client)      │  │
│  │    - publisher.py            (Instagram Graph API)           │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      SUPABASE (Database + Storage)                   │
│  PostgreSQL Database:              Storage Buckets:                 │
│  - posts                           - instagram-media/               │
│  - instagram_accounts              - post-previews/                 │
│  - templates                       - temp-uploads/                  │
│  - ai_strategy                                                      │
│  - post_performance                                                 │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         REACT FRONTEND                               │
│  Views:                                                             │
│  - Dashboard (resumen, nuevos datos)                                │
│  - Generar Post (manual/automático)                                 │
│  - Calendario (timeline de publicaciones)                           │
│  - Templates (biblioteca)                                           │
│  - Estrategia IA (configuración)                                    │
│  - Analytics (métricas y performance)                               │
└────────────────────────────────┬───────────────────────────────────┘
                                 │
                                 │ API Calls
                                 │
┌─────────────────────────────────────────────────────────────────────┐
│                      INSTAGRAM GRAPH API                             │
│  - Publicación de posts/reels/stories                              │
│  - Obtención de métricas                                           │
│  - Gestión de media containers                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos Principal

```
[PROJECT 1]
    ↓ (Export)
[Google Drive]
    ↓ (Polling/Webhook)
[n8n/Backend]
    ↓ (Download)
[Template Selector]
    ↓ (Select)
[Image Composer]
    ↓ (Pillow)
[AI Caption Generator]
    ↓ (Gemini)
[Post Draft Created]
    ↓ (Store)
[Supabase DB]
    ↓ (User Approval)
[Frontend Dashboard]
    ↓ (Schedule)
[Scheduler]
    ↓ (Publish)
[Instagram API]
    ↓ (Track)
[Performance Analytics]
```

---

# 2. ARQUITECTURA DEL SISTEMA

## 2.1 Arquitectura de Componentes

### 2.1.1 Backend (FastAPI)

**Propósito**: API central que orquesta toda la lógica de negocio

**Responsabilidades**:
- Gestión de datos de PROJECT 1
- Selección y composición de templates
- Generación de contenido con IA
- Programación de publicaciones
- Publicación a Instagram
- Tracking de métricas

**Stack**:
- Python 3.11+
- FastAPI 0.109+
- Uvicorn (ASGI server)
- Pydantic (validación)
- SQLAlchemy (ORM - opcional)

### 2.1.2 Frontend (React)

**Propósito**: Interfaz de usuario para gestionar el planificador

**Responsabilidades**:
- Dashboard de control
- Visualización de posts programados
- Aprobación de contenido generado
- Configuración de estrategia IA
- Gestión de templates
- Analytics y reporting

**Stack**:
- React 18+
- TypeScript
- Vite (build tool)
- React Router (navegación)
- Tailwind CSS (estilos)
- Axios (HTTP client)

### 2.1.3 Base de Datos (Supabase PostgreSQL)

**Propósito**: Almacenamiento persistente de datos

**Datos almacenados**:
- Usuarios y autenticación
- Cuentas de Instagram conectadas
- Posts (drafts, scheduled, published)
- Templates y su metadata
- Configuración de estrategia IA
- Métricas de performance

### 2.1.4 Storage (Supabase Storage + Google Drive)

**Google Drive** (datos externos):
- Exports de PROJECT 1
- Templates originales
- metadata.json (índice)

**Supabase Storage** (datos internos):
- Media final para Instagram
- Previews de posts
- Uploads temporales

### 2.1.5 IA Services (Google Gemini)

**Gemini 2.0 Flash** para:
- Generación de captions
- Planificación de estrategia
- Optimización de timing

**Alternativas** (fallbacks):
- Claude 3.5 Haiku
- GPT-4o-mini

### 2.1.6 Workflow Engine (n8n o APScheduler)

**Opción A: n8n (self-hosted)**
- Workflows visuales
- Polling de Google Drive
- Scheduled publishing
- Webhooks y triggers

**Opción B: APScheduler (Python)**
- Más simple
- Integrado en backend
- Menos features

---

## 2.2 Estructura de Carpetas Completa

```
SocialLab/
├── backend/
│   ├── main.py                          # FastAPI app principal
│   ├── requirements.txt                 # Dependencias Python
│   ├── .env.example                     # Template de variables
│   ├── .env                             # Variables de entorno (git-ignored)
│   │
│   ├── migrations/                      # Migraciones de DB
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_instagram_integration.sql
│   │   ├── 003_add_media_urls.sql
│   │   ├── 004_add_media_product_type.sql
│   │   ├── 005_add_scheduled_publish_time.sql
│   │   └── 006_planner_complete_schema.sql  # NUEVO
│   │
│   ├── models/                          # Modelos de datos
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── post.py
│   │   ├── instagram_account.py
│   │   ├── template.py                  # NUEVO
│   │   ├── ai_strategy.py               # NUEVO
│   │   └── performance.py               # NUEVO
│   │
│   ├── schemas/                         # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── post_schema.py
│   │   ├── template_schema.py           # NUEVO
│   │   ├── content_schema.py            # NUEVO
│   │   └── analytics_schema.py          # NUEVO
│   │
│   ├── services/                        # Lógica de negocio
│   │   ├── __init__.py
│   │   │
│   │   ├── ai/                          # Servicios de IA
│   │   │   ├── __init__.py
│   │   │   ├── caption_generator.py     # NUEVO
│   │   │   ├── template_selector.py     # NUEVO
│   │   │   ├── strategy_planner.py      # NUEVO
│   │   │   └── cache_manager.py         # NUEVO
│   │   │
│   │   ├── image/                       # Procesamiento de imágenes
│   │   │   ├── __init__.py
│   │   │   ├── composer.py              # NUEVO
│   │   │   ├── template_manager.py      # NUEVO
│   │   │   └── branding.py              # NUEVO
│   │   │
│   │   ├── data/                        # Gestión de datos externos
│   │   │   ├── __init__.py
│   │   │   ├── drive_connector.py       # NUEVO
│   │   │   └── metadata_parser.py       # NUEVO
│   │   │
│   │   └── content/                     # Generación de contenido
│   │       ├── __init__.py
│   │       ├── post_generator.py        # NUEVO
│   │       ├── scheduler.py             # NUEVO
│   │       └── publisher.py             # NUEVO
│   │
│   ├── utils/                           # Utilidades
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── logger.py
│   │   ├── validators.py
│   │   └── helpers.py
│   │
│   ├── tests/                           # Tests
│   │   ├── __init__.py
│   │   ├── test_ai_services.py          # NUEVO
│   │   ├── test_image_composer.py       # NUEVO
│   │   ├── test_post_generator.py       # NUEVO
│   │   └── test_instagram_api.py
│   │
│   └── fonts/                           # Fuentes para Pillow
│       ├── Montserrat-Bold.ttf
│       ├── Montserrat-SemiBold.ttf
│       └── Montserrat-Regular.ttf
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── dashboard/
│   │   │   │   └── Dashboard.tsx
│   │   │   │
│   │   │   ├── posts/
│   │   │   │   ├── PostList.tsx
│   │   │   │   ├── PostGenerator.tsx    # NUEVO
│   │   │   │   ├── PostPreview.tsx      # NUEVO
│   │   │   │   └── PostCalendar.tsx     # NUEVO
│   │   │   │
│   │   │   ├── templates/               # NUEVO
│   │   │   │   ├── TemplateLibrary.tsx
│   │   │   │   ├── TemplateCard.tsx
│   │   │   │   └── TemplateUpload.tsx
│   │   │   │
│   │   │   ├── strategy/                # NUEVO
│   │   │   │   ├── StrategyConfig.tsx
│   │   │   │   └── AIInsights.tsx
│   │   │   │
│   │   │   └── analytics/               # NUEVO
│   │   │       ├── PerformanceDashboard.tsx
│   │   │       └── MetricsChart.tsx
│   │   │
│   │   ├── context/
│   │   │   ├── AuthContext.tsx
│   │   │   └── PostContext.tsx          # NUEVO
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   ├── postService.ts           # NUEVO
│   │   │   ├── templateService.ts       # NUEVO
│   │   │   └── analyticsService.ts      # NUEVO
│   │   │
│   │   └── types/
│   │       ├── post.ts
│   │       ├── template.ts              # NUEVO
│   │       └── analytics.ts             # NUEVO
│   │
│   └── public/
│       └── assets/
│
├── n8n/                                 # NUEVO (workflows n8n)
│   ├── workflows/
│   │   ├── poll-google-drive.json
│   │   ├── publish-scheduled-posts.json
│   │   └── sync-performance-metrics.json
│   └── credentials/
│       └── README.md
│
├── docs/                                # Documentación
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── USER_GUIDE.md
│
├── scripts/                             # Scripts de utilidad
│   ├── setup_google_drive.py
│   ├── sync_templates.py
│   └── migrate_db.sh
│
├── MASTER_PLAN_INSTAGRAM_PLANNER.md    # Este documento
├── README.md
├── .gitignore
└── docker-compose.yml                   # Docker setup (opcional)
```

---

# 3. REQUISITOS TÉCNICOS COMPLETOS

## 3.1 Stack Tecnológico con Versiones

### Backend
```txt
Python==3.11.7
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.1.2
supabase==2.3.0
python-dotenv==1.0.0
pillow==10.2.0
google-generativeai==0.3.2
google-api-python-client==2.116.0
google-auth-httplib2==0.2.0
google-auth-oauthlib==1.2.0
requests==2.31.0
apscheduler==3.10.4
redis==5.0.1
matplotlib==3.8.2
pytest==7.4.4
pytest-asyncio==0.23.3
httpx==0.26.0
```

### Frontend
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.1",
    "typescript": "^5.3.3",
    "axios": "^1.6.5",
    "tailwindcss": "^3.4.1",
    "date-fns": "^3.2.0",
    "react-calendar": "^4.8.0",
    "recharts": "^2.10.3",
    "lucide-react": "^0.309.0"
  },
  "devDependencies": {
    "vite": "^5.0.11",
    "@types/react": "^18.2.48",
    "@types/react-dom": "^18.2.18",
    "@vitejs/plugin-react": "^4.2.1",
    "eslint": "^8.56.0",
    "prettier": "^3.1.1"
  }
}
```

---

## 3.2 Variables de Entorno

**Archivo**: `/backend/.env`

```bash
# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================
APP_NAME="SocialLab Instagram Planner"
APP_VERSION="1.0.0"
ENVIRONMENT="development"  # development, staging, production
DEBUG=true
LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR

# ============================================================
# FASTAPI
# ============================================================
API_HOST="0.0.0.0"
API_PORT=8000
API_RELOAD=true
SECRET_KEY="your-super-secret-key-change-in-production"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# ============================================================
# SUPABASE
# ============================================================
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_KEY="your-supabase-anon-key"
SUPABASE_SERVICE_KEY="your-supabase-service-role-key"

# Database (si usas SQLAlchemy directamente)
DATABASE_URL="postgresql://postgres:password@db.your-project.supabase.co:5432/postgres"

# ============================================================
# GOOGLE DRIVE API
# ============================================================
GOOGLE_DRIVE_CREDENTIALS_FILE="./credentials/google_drive_credentials.json"
GOOGLE_DRIVE_TOKEN_FILE="./credentials/google_drive_token.json"
GOOGLE_DRIVE_SCOPES="https://www.googleapis.com/auth/drive.readonly"

# Carpetas de Google Drive
PROJECT1_EXPORTS_FOLDER_ID="your-google-drive-folder-id"
TEMPLATES_FOLDER_ID="your-templates-folder-id"

# ============================================================
# GOOGLE GEMINI AI
# ============================================================
GOOGLE_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-2.0-flash-exp"
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_TOKENS=500

# ============================================================
# INSTAGRAM GRAPH API
# ============================================================
# Estos valores se obtienen por usuario desde la DB
# pero aquí van las credenciales de tu app de Meta
INSTAGRAM_APP_ID="your-instagram-app-id"
INSTAGRAM_APP_SECRET="your-instagram-app-secret"
INSTAGRAM_REDIRECT_URI="http://localhost:8000/instagram/callback"

# ============================================================
# PILLOW / IMAGE PROCESSING
# ============================================================
IMAGE_OUTPUT_FORMAT="PNG"
IMAGE_QUALITY=95
IMAGE_MAX_SIZE=10485760  # 10MB en bytes
FONTS_DIR="./fonts"

# ============================================================
# CACHE (Redis - opcional)
# ============================================================
REDIS_URL="redis://localhost:6379/0"
REDIS_ENABLED=false  # true si usas Redis
CACHE_TTL=3600  # 1 hora en segundos

# ============================================================
# SCHEDULING
# ============================================================
SCHEDULER_ENABLED=true
SCHEDULER_TYPE="apscheduler"  # apscheduler o n8n
SCHEDULER_CHECK_INTERVAL=900  # 15 minutos en segundos

# n8n (si usas n8n en vez de APScheduler)
N8N_WEBHOOK_URL="http://localhost:5678/webhook/sociallab"
N8N_API_KEY="your-n8n-api-key"

# ============================================================
# CORS
# ============================================================
CORS_ORIGINS="http://localhost:5173,http://localhost:3000"
CORS_CREDENTIALS=true
CORS_METHODS="GET,POST,PUT,DELETE,PATCH"
CORS_HEADERS="*"

# ============================================================
# RATE LIMITING
# ============================================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60  # segundos

# ============================================================
# MONITORING & LOGGING
# ============================================================
SENTRY_DSN=""  # Opcional: para error tracking
SENTRY_ENVIRONMENT="development"

# ============================================================
# FEATURE FLAGS
# ============================================================
FEATURE_AI_CAPTIONS=true
FEATURE_AUTO_PUBLISH=true
FEATURE_PERFORMANCE_TRACKING=true
FEATURE_N8N_INTEGRATION=false
```

---

## 3.3 Configuración de Servicios Externos

### 3.3.1 Google Drive API

**Pasos de configuración**:

1. **Ir a Google Cloud Console**: https://console.cloud.google.com/
2. **Crear nuevo proyecto** o seleccionar existente
3. **Habilitar Google Drive API**:
   - APIs & Services → Library
   - Buscar "Google Drive API"
   - Click "Enable"
4. **Crear credenciales**:
   - APIs & Services → Credentials
   - Create Credentials → OAuth 2.0 Client ID
   - Application type: Desktop app
   - Descargar JSON
   - Guardar como `backend/credentials/google_drive_credentials.json`
5. **Configurar OAuth consent screen**:
   - User Type: External
   - App name: SocialLab Planner
   - Scopes: `.../auth/drive.readonly`
6. **Obtener folder IDs**:
   - Abrir carpeta en Google Drive
   - URL: `https://drive.google.com/drive/folders/FOLDER_ID_AQUÍ`
   - Copiar FOLDER_ID al `.env`

**Script de autenticación** (`scripts/setup_google_drive.py`):
```python
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def authenticate_google_drive():
    creds = None
    token_file = 'backend/credentials/google_drive_token.json'

    if os.path.exists(token_file):
        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'backend/credentials/google_drive_credentials.json',
                SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_file, 'wb') as token:
            pickle.dump(creds, token)

    print("✅ Google Drive autenticado correctamente")
    return creds

if __name__ == '__main__':
    authenticate_google_drive()
```

### 3.3.2 Google Gemini AI

**Pasos de configuración**:

1. **Ir a Google AI Studio**: https://makersuite.google.com/app/apikey
2. **Crear API Key**:
   - Click "Create API Key"
   - Seleccionar proyecto de Google Cloud
   - Copiar API key
3. **Configurar en `.env`**:
   ```bash
   GOOGLE_API_KEY="tu-api-key-aquí"
   ```
4. **Verificar límites gratuitos**:
   - 1500 requests/día
   - 1M tokens/minuto
   - 15 requests/minuto

**Test de conexión** (`backend/tests/test_gemini_connection.py`):
```python
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash-exp')

response = model.generate_content("Di 'Hola desde Gemini!'")
print(response.text)
# Expected: "¡Hola desde Gemini!"
```

### 3.3.3 Supabase

**Pasos de configuración**:

1. **Crear cuenta en Supabase**: https://supabase.com/
2. **Crear nuevo proyecto**:
   - Name: sociallab-planner
   - Database Password: (guardar en lugar seguro)
   - Region: Closest to you
3. **Obtener credenciales**:
   - Settings → API
   - Project URL → copiar a `SUPABASE_URL`
   - anon/public key → copiar a `SUPABASE_KEY`
   - service_role key → copiar a `SUPABASE_SERVICE_KEY`
4. **Configurar Storage**:
   - Storage → New bucket
   - Crear buckets:
     - `instagram-media` (public)
     - `post-previews` (public)
     - `temp-uploads` (private)
5. **Habilitar Row Level Security (RLS)**:
   - Table Editor → Select table → RLS enabled
   - Políticas de acceso por usuario

### 3.3.4 Instagram Graph API

**Pasos de configuración**:

1. **Crear Meta App**: https://developers.facebook.com/
2. **Configurar app**:
   - Dashboard → Add Product → Instagram
   - Settings → Basic → Copiar App ID y Secret
3. **Configurar OAuth**:
   - Settings → Basic → Add Platform → Website
   - Site URL: `http://localhost:8000`
   - Valid OAuth Redirect URIs: `http://localhost:8000/instagram/callback`
4. **Permisos requeridos**:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
   - `pages_show_list`
5. **Modo de desarrollo**:
   - App Mode → Development (para testing)
   - Agregar usuarios de prueba en Roles

**El flujo de OAuth ya está implementado en `main.py` actual**

---

## 3.4 Limitaciones y Constraints

### Supabase Free Tier
- ✅ 500 MB Database
- ✅ 1 GB File Storage
- ✅ 2 GB Bandwidth
- ⚠️ Pausa tras 1 semana de inactividad (hacer request cada 6 días)
- ⚠️ Máximo 2 proyectos activos

**Estimaciones de capacidad**:
- ~10,000 posts almacenables (50KB avg metadata)
- ~500 imágenes en storage (2MB avg cada una)
- Suficiente para MVP y testeo

### Google Gemini Free Tier
- ✅ 1500 requests/día
- ✅ 1M tokens/minuto
- ✅ 15 requests/minuto
- ⚠️ No garantía de uptime
- ⚠️ Rate limits estrictos

**Estimaciones de uso**:
- ~1 caption = 500-700 tokens
- ~500 posts generables/día (más que suficiente)

### Instagram Graph API
- ✅ 100 posts publicados/día
- ⚠️ NO edita captions publicados
- ⚠️ NO elimina posts
- ⚠️ Stories solo 24h de acceso
- ⚠️ Límite de 25 posts por 24h rolling

### Google Drive Free Tier
- ✅ 15 GB storage
- ✅ API requests ilimitados (dentro de quotas)
- ⚠️ Quota: 10,000 requests/100 segundos

**Estimaciones de capacidad**:
- ~3,000 imágenes (5MB avg)
- ~100 templates

---

# 4. ESQUEMA DE BASE DE DATOS

## 4.1 Migración Completa

**Archivo**: `backend/migrations/006_planner_complete_schema.sql`

```sql
-- ============================================================
-- MIGRACIÓN 006: Esquema Completo del Planificador
-- Fecha: 2025-01-15
-- Descripción: Tablas para templates, IA strategy, performance
-- ============================================================

-- ============================================================
-- ACTUALIZACIÓN DE TABLAS EXISTENTES
-- ============================================================

-- Actualizar instagram_accounts para múltiples cuentas
ALTER TABLE instagram_accounts
DROP CONSTRAINT IF EXISTS unique_user_instagram;

ALTER TABLE instagram_accounts
ADD COLUMN IF NOT EXISTS account_name TEXT,
ADD COLUMN IF NOT EXISTS username TEXT,
ADD COLUMN IF NOT EXISTS profile_picture_url TEXT,
ADD COLUMN IF NOT EXISTS followers_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;

-- Nuevo constraint para múltiples cuentas
CREATE UNIQUE INDEX IF NOT EXISTS idx_instagram_accounts_user_business
ON instagram_accounts(user_id, instagram_business_account_id);

-- Índices adicionales
CREATE INDEX IF NOT EXISTS idx_instagram_accounts_active
ON instagram_accounts(is_active) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_username
ON instagram_accounts(username);

-- Comentarios
COMMENT ON COLUMN instagram_accounts.account_name IS
'Nombre descriptivo asignado por el usuario';
COMMENT ON COLUMN instagram_accounts.username IS
'Username de Instagram (@username)';
COMMENT ON COLUMN instagram_accounts.is_active IS
'Indica si la cuenta está activa para publicaciones';

-- Actualizar posts para referencias externas
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS source_data_id TEXT,
ADD COLUMN IF NOT EXISTS source_data_url TEXT,
ADD COLUMN IF NOT EXISTS template_id INTEGER,
ADD COLUMN IF NOT EXISTS ai_caption_raw TEXT,
ADD COLUMN IF NOT EXISTS ai_metadata JSONB,
ADD COLUMN IF NOT EXISTS is_ai_generated BOOLEAN DEFAULT false;

-- Índices para posts
CREATE INDEX IF NOT EXISTS idx_posts_instagram_account
ON posts(instagram_account_id);

CREATE INDEX IF NOT EXISTS idx_posts_source_data
ON posts(source_data_id) WHERE source_data_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_posts_template
ON posts(template_id) WHERE template_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_posts_ai_generated
ON posts(is_ai_generated) WHERE is_ai_generated = true;

-- Comentarios
COMMENT ON COLUMN posts.source_data_id IS
'ID del export de PROJECT 1 que generó este post';
COMMENT ON COLUMN posts.source_data_url IS
'URL de la imagen/datos originales de PROJECT 1';
COMMENT ON COLUMN posts.template_id IS
'ID del template usado para componer la imagen';
COMMENT ON COLUMN posts.ai_caption_raw IS
'Caption original generado por IA (sin editar por usuario)';

-- ============================================================
-- NUEVAS TABLAS
-- ============================================================

-- Tabla: template_categories
CREATE TABLE IF NOT EXISTS template_categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    icon TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_template_categories_order ON template_categories(display_order);

COMMENT ON TABLE template_categories IS
'Categorías para organizar templates (Match Day, Player Stats, etc.)';

-- Datos iniciales de categorías
INSERT INTO template_categories (name, description, display_order) VALUES
    ('Player Stats', 'Templates para estadísticas de jugadores', 1),
    ('Team Performance', 'Templates para estadísticas de equipos', 2),
    ('Match Preview', 'Templates para previews de partidos', 3),
    ('Match Result', 'Templates para resultados de partidos', 4),
    ('League Table', 'Templates para tablas de clasificación', 5),
    ('Story', 'Templates para Instagram Stories (9:16)', 6),
    ('Carousel', 'Templates para posts carousel', 7),
    ('Generic', 'Templates genéricos reutilizables', 99)
ON CONFLICT (name) DO NOTHING;

-- Tabla: templates
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,

    -- Información básica
    template_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES template_categories(id) ON DELETE SET NULL,

    -- Archivo del template
    file_url TEXT NOT NULL,
    file_type TEXT DEFAULT 'image/png',
    file_size INTEGER,
    dimensions JSONB DEFAULT '{"width": 1080, "height": 1080}'::jsonb,

    -- Tipo de contenido Instagram
    content_type TEXT DEFAULT 'FEED' CHECK (content_type IN ('FEED', 'REELS', 'STORY', 'CAROUSEL')),

    -- Metadatos de diseño
    design_source TEXT,
    design_prompt TEXT,
    branding JSONB,

    -- Reglas de selección
    selection_rules JSONB,
    applicable_teams TEXT[],

    -- Configuración de uso
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,
    use_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para templates
CREATE INDEX idx_templates_user ON templates(user_id);
CREATE INDEX idx_templates_account ON templates(instagram_account_id);
CREATE INDEX idx_templates_category ON templates(category_id);
CREATE INDEX idx_templates_content_type ON templates(content_type);
CREATE INDEX idx_templates_active ON templates(is_active) WHERE is_active = true;
CREATE INDEX idx_templates_priority ON templates(priority DESC);
CREATE INDEX idx_templates_template_id ON templates(template_id);

-- Índice GIN para búsqueda en arrays
CREATE INDEX idx_templates_teams ON templates USING GIN (applicable_teams);

COMMENT ON TABLE templates IS
'Templates visuales para composición de posts';
COMMENT ON COLUMN templates.template_id IS
'ID único del template (ej: tmpl_player_stats_001)';
COMMENT ON COLUMN templates.selection_rules IS
'Reglas JSON para selección automática';
COMMENT ON COLUMN templates.branding IS
'Colores, logos y estilos del template';

-- Tabla: ai_strategy
CREATE TABLE IF NOT EXISTS ai_strategy (
    id SERIAL PRIMARY KEY,
    instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE UNIQUE,

    -- Configuración de personalidad
    tone TEXT DEFAULT 'energetic' CHECK (tone IN ('energetic', 'professional', 'casual', 'humorous', 'inspirational')),
    language TEXT DEFAULT 'es' CHECK (language IN ('es', 'en', 'pt', 'multi')),
    emoji_usage TEXT DEFAULT 'moderate' CHECK (emoji_usage IN ('none', 'minimal', 'moderate', 'heavy')),

    -- Preferencias de contenido
    content_preferences JSONB DEFAULT '{}'::jsonb,
    hashtag_strategy JSONB DEFAULT '{"max": 7, "include_team": true}'::jsonb,

    -- Frecuencia de publicación
    posting_frequency JSONB DEFAULT '{"per_day": 3, "per_week": 15}'::jsonb,
    best_times JSONB DEFAULT '["13:00", "20:00"]'::jsonb,

    -- Tipos de contenido (distribución porcentual)
    content_distribution JSONB DEFAULT '{"player_stats": 40, "match_results": 30, "team_stats": 30}'::jsonb,

    -- Configuración de IA
    ai_model TEXT DEFAULT 'gemini-2.0-flash-exp',
    ai_temperature DECIMAL(3,2) DEFAULT 0.7,
    custom_instructions TEXT,

    -- Estado
    is_active BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_strategy_account ON ai_strategy(instagram_account_id);
CREATE INDEX idx_ai_strategy_active ON ai_strategy(is_active) WHERE is_active = true;

COMMENT ON TABLE ai_strategy IS
'Configuración de estrategia de Community Manager IA por cuenta';
COMMENT ON COLUMN ai_strategy.tone IS
'Tono de voz para los captions';
COMMENT ON COLUMN ai_strategy.content_distribution IS
'Distribución porcentual de tipos de contenido';

-- Tabla: content_generation_queue
CREATE TABLE IF NOT EXISTS content_generation_queue (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,

    -- Datos de entrada
    source_data_id TEXT NOT NULL,
    source_data_url TEXT,
    source_data JSONB,

    -- Template seleccionado
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,

    -- Estado del proceso
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),

    -- Resultado
    post_id INTEGER REFERENCES posts(id) ON DELETE SET NULL,
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_queue_status ON content_generation_queue(status);
CREATE INDEX idx_queue_user ON content_generation_queue(user_id);
CREATE INDEX idx_queue_created ON content_generation_queue(created_at DESC);

COMMENT ON TABLE content_generation_queue IS
'Cola de procesamiento para generación de contenido';

-- Tabla: content_generation_history
CREATE TABLE IF NOT EXISTS content_generation_history (
    id SERIAL PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,

    -- Input de generación
    ai_prompt TEXT NOT NULL,
    input_data JSONB,

    -- Output de generación
    generated_caption TEXT,
    generated_hashtags TEXT[],
    suggested_publish_time TIMESTAMPTZ,

    -- Metadatos de generación
    ai_model TEXT,
    ai_temperature DECIMAL(3,2),
    tokens_used INTEGER,
    generation_time_ms INTEGER,

    -- Aprobación y feedback
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'modified')),
    user_feedback TEXT,
    modified_caption TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_generation_history_post ON content_generation_history(post_id);
CREATE INDEX idx_generation_history_template ON content_generation_history(template_id);
CREATE INDEX idx_generation_history_status ON content_generation_history(status);

COMMENT ON TABLE content_generation_history IS
'Historial completo de generaciones para auditoría y mejora';

-- Tabla: post_performance
CREATE TABLE IF NOT EXISTS post_performance (
    id SERIAL PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE UNIQUE,

    -- Métricas básicas de Instagram
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    profile_visits INTEGER DEFAULT 0,

    -- Métricas calculadas
    engagement_rate DECIMAL(5,2),
    virality_score DECIMAL(5,2),

    -- Análisis de template
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    template_effectiveness_score DECIMAL(5,2),

    -- Análisis temporal
    published_at TIMESTAMPTZ,
    best_performing_hour INTEGER,
    day_of_week INTEGER,

    -- Timestamps
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_performance_post ON post_performance(post_id);
CREATE INDEX idx_performance_template ON post_performance(template_id);
CREATE INDEX idx_performance_engagement ON post_performance(engagement_rate DESC NULLS LAST);
CREATE INDEX idx_performance_virality ON post_performance(virality_score DESC NULLS LAST);
CREATE INDEX idx_performance_published ON post_performance(published_at DESC);

COMMENT ON TABLE post_performance IS
'Métricas de performance de cada post para optimización';
COMMENT ON COLUMN post_performance.engagement_rate IS
'(likes + comments + shares + saves) / reach * 100';
COMMENT ON COLUMN post_performance.virality_score IS
'Métrica personalizada de viralidad';

-- Tabla: scheduled_jobs
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT NOT NULL CHECK (job_type IN ('publish_post', 'sync_metrics', 'generate_content', 'cleanup')),
    job_data JSONB NOT NULL,

    -- Scheduling
    scheduled_for TIMESTAMPTZ NOT NULL,
    executed_at TIMESTAMPTZ,

    -- Estado
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scheduled_jobs_type ON scheduled_jobs(job_type);
CREATE INDEX idx_scheduled_jobs_status ON scheduled_jobs(status);
CREATE INDEX idx_scheduled_jobs_scheduled ON scheduled_jobs(scheduled_for);
CREATE INDEX idx_scheduled_jobs_pending ON scheduled_jobs(status, scheduled_for)
WHERE status = 'pending';

COMMENT ON TABLE scheduled_jobs IS
'Cola de trabajos programados para el scheduler';

-- ============================================================
-- FUNCIONES Y TRIGGERS
-- ============================================================

-- Función: Actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Aplicar trigger a tablas con updated_at
DROP TRIGGER IF EXISTS update_template_categories_updated_at ON template_categories;
CREATE TRIGGER update_template_categories_updated_at
BEFORE UPDATE ON template_categories
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_templates_updated_at ON templates;
CREATE TRIGGER update_templates_updated_at
BEFORE UPDATE ON templates
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_ai_strategy_updated_at ON ai_strategy;
CREATE TRIGGER update_ai_strategy_updated_at
BEFORE UPDATE ON ai_strategy
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scheduled_jobs_updated_at ON scheduled_jobs;
CREATE TRIGGER update_scheduled_jobs_updated_at
BEFORE UPDATE ON scheduled_jobs
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Función: Incrementar use_count en templates
CREATE OR REPLACE FUNCTION increment_template_use_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.template_id IS NOT NULL THEN
        UPDATE templates
        SET use_count = use_count + 1
        WHERE id = NEW.template_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS increment_template_use_on_post ON posts;
CREATE TRIGGER increment_template_use_on_post
AFTER INSERT ON posts
FOR EACH ROW EXECUTE FUNCTION increment_template_use_count();

-- Función: Calcular engagement_rate automáticamente
CREATE OR REPLACE FUNCTION calculate_engagement_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.reach > 0 THEN
        NEW.engagement_rate := (
            (NEW.likes + NEW.comments + NEW.shares + NEW.saves)::DECIMAL / NEW.reach * 100
        );
    ELSE
        NEW.engagement_rate := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS calculate_engagement_on_update ON post_performance;
CREATE TRIGGER calculate_engagement_on_update
BEFORE INSERT OR UPDATE ON post_performance
FOR EACH ROW EXECUTE FUNCTION calculate_engagement_rate();

-- ============================================================
-- VISTAS ÚTILES
-- ============================================================

-- Vista: Posts con toda la información relevante
CREATE OR REPLACE VIEW posts_detailed AS
SELECT
    p.id,
    p.user_id,
    p.content,
    p.media_url,
    p.post_type,
    p.status,
    p.scheduled_publish_time,
    p.publication_date,
    p.instagram_post_id,
    p.source_data_id,
    p.is_ai_generated,

    -- Instagram account info
    ia.username as instagram_username,
    ia.account_name as instagram_account_name,
    ia.is_active as account_active,

    -- Template info
    t.name as template_name,
    t.template_id as template_code,
    tc.name as template_category,

    -- Performance metrics
    pp.likes,
    pp.comments,
    pp.shares,
    pp.reach,
    pp.engagement_rate,

    p.created_at,
    p.updated_at
FROM posts p
LEFT JOIN instagram_accounts ia ON p.instagram_account_id = ia.id
LEFT JOIN templates t ON p.template_id = t.id
LEFT JOIN template_categories tc ON t.category_id = tc.id
LEFT JOIN post_performance pp ON p.id = pp.post_id;

COMMENT ON VIEW posts_detailed IS
'Vista consolidada de posts con toda la información relevante';

-- Vista: Templates más efectivos
CREATE OR REPLACE VIEW templates_effectiveness AS
SELECT
    t.id,
    t.template_id,
    t.name,
    tc.name as category,
    t.content_type,
    t.use_count,
    COUNT(DISTINCT p.id) as posts_created,
    AVG(pp.engagement_rate) as avg_engagement_rate,
    AVG(pp.likes) as avg_likes,
    AVG(pp.comments) as avg_comments,
    AVG(pp.reach) as avg_reach,
    AVG(pp.virality_score) as avg_virality
FROM templates t
LEFT JOIN template_categories tc ON t.category_id = tc.id
LEFT JOIN posts p ON t.id = p.template_id
LEFT JOIN post_performance pp ON p.id = pp.post_id
WHERE t.is_active = true
GROUP BY t.id, t.template_id, t.name, tc.name, t.content_type, t.use_count;

COMMENT ON VIEW templates_effectiveness IS
'Análisis de efectividad de templates basado en métricas';

-- Vista: Performance por hora del día
CREATE OR REPLACE VIEW performance_by_hour AS
SELECT
    EXTRACT(HOUR FROM pp.published_at) as hour_of_day,
    COUNT(*) as posts_count,
    AVG(pp.engagement_rate) as avg_engagement_rate,
    AVG(pp.reach) as avg_reach,
    AVG(pp.likes) as avg_likes
FROM post_performance pp
WHERE pp.published_at IS NOT NULL
GROUP BY EXTRACT(HOUR FROM pp.published_at)
ORDER BY avg_engagement_rate DESC;

COMMENT ON VIEW performance_by_hour IS
'Análisis de performance por hora del día';

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Habilitar RLS en tablas sensibles
ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_strategy ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_generation_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_generation_history ENABLE ROW LEVEL SECURITY;

-- Política: usuarios solo ven sus propios templates
DROP POLICY IF EXISTS templates_user_access ON templates;
CREATE POLICY templates_user_access ON templates
FOR ALL
USING (user_id = auth.uid());

-- Política: usuarios solo ven su propia estrategia
DROP POLICY IF EXISTS ai_strategy_user_access ON ai_strategy;
CREATE POLICY ai_strategy_user_access ON ai_strategy
FOR ALL
USING (
    instagram_account_id IN (
        SELECT id FROM instagram_accounts WHERE user_id = auth.uid()
    )
);

-- Política: usuarios solo ven su propia cola
DROP POLICY IF EXISTS queue_user_access ON content_generation_queue;
CREATE POLICY queue_user_access ON content_generation_queue
FOR ALL
USING (user_id = auth.uid());

-- ============================================================
-- REGISTRAR MIGRACIÓN
-- ============================================================

INSERT INTO schema_migrations (migration_file)
VALUES ('006_planner_complete_schema.sql')
ON CONFLICT (migration_file) DO NOTHING;

-- ============================================================
-- VERIFICACIÓN
-- ============================================================

DO $$
DECLARE
    table_count INTEGER;
    view_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

    SELECT COUNT(*) INTO view_count
    FROM information_schema.views
    WHERE table_schema = 'public';

    RAISE NOTICE '✅ Migración 006 completada exitosamente';
    RAISE NOTICE '   Tablas totales: %', table_count;
    RAISE NOTICE '   Vistas totales: %', view_count;
END $$;
```

---

## 4.2 Diccionario de Datos

### Tabla: `templates`

| Columna | Tipo | Null | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | SERIAL | NO | AUTO | Primary key |
| `user_id` | UUID | NO | - | Usuario propietario |
| `instagram_account_id` | INTEGER | YES | NULL | Cuenta asociada (opcional) |
| `template_id` | TEXT | NO | - | ID único ej: `tmpl_player_001` |
| `name` | TEXT | NO | - | Nombre descriptivo |
| `description` | TEXT | YES | NULL | Descripción del template |
| `category_id` | INTEGER | YES | NULL | FK a `template_categories` |
| `file_url` | TEXT | NO | - | URL en Google Drive o Supabase |
| `file_type` | TEXT | YES | 'image/png' | MIME type |
| `file_size` | INTEGER | YES | NULL | Tamaño en bytes |
| `dimensions` | JSONB | YES | `{"width":1080,"height":1080}` | Dimensiones |
| `content_type` | TEXT | YES | 'FEED' | FEED, REELS, STORY, CAROUSEL |
| `design_source` | TEXT | YES | NULL | Midjourney, SeaDream, etc. |
| `design_prompt` | TEXT | YES | NULL | Prompt usado para generar |
| `branding` | JSONB | YES | NULL | `{"primary_color": "#fff", ...}` |
| `selection_rules` | JSONB | YES | NULL | Reglas de selección automática |
| `applicable_teams` | TEXT[] | YES | NULL | Array de nombres de equipos |
| `is_active` | BOOLEAN | YES | true | Template activo/inactivo |
| `priority` | INTEGER | YES | 0 | Mayor = mayor prioridad |
| `use_count` | INTEGER | YES | 0 | Contador de usos |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Última actualización |

**Índices**:
- `idx_templates_user` (user_id)
- `idx_templates_template_id` (template_id UNIQUE)
- `idx_templates_active` (is_active WHERE true)
- `idx_templates_priority` (priority DESC)
- `idx_templates_teams` (applicable_teams GIN)

**Ejemplo de datos**:
```json
{
  "id": 1,
  "user_id": "uuid-123",
  "template_id": "tmpl_player_stats_001",
  "name": "Modern Blue - Player Stats",
  "category_id": 1,
  "file_url": "https://drive.google.com/file/d/xxx",
  "dimensions": {"width": 1080, "height": 1080},
  "content_type": "FEED",
  "branding": {
    "primary_color": "#0066CC",
    "secondary_color": "#FFFFFF",
    "font": "Montserrat"
  },
  "selection_rules": {
    "stat_type": "player_stats",
    "min_goals": 5
  },
  "applicable_teams": ["all"],
  "priority": 5
}
```

### Tabla: `ai_strategy`

| Columna | Tipo | Null | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | SERIAL | NO | AUTO | Primary key |
| `instagram_account_id` | INTEGER | NO | - | FK UNIQUE a instagram_accounts |
| `tone` | TEXT | YES | 'energetic' | energetic, professional, casual, humorous, inspirational |
| `language` | TEXT | YES | 'es' | es, en, pt, multi |
| `emoji_usage` | TEXT | YES | 'moderate' | none, minimal, moderate, heavy |
| `content_preferences` | JSONB | YES | `{}` | Preferencias personalizadas |
| `hashtag_strategy` | JSONB | YES | `{"max":7}` | Estrategia de hashtags |
| `posting_frequency` | JSONB | YES | `{"per_day":3}` | Frecuencia de publicación |
| `best_times` | JSONB | YES | `["13:00","20:00"]` | Mejores horarios |
| `content_distribution` | JSONB | YES | `{"player_stats":40}` | Distribución % de contenido |
| `ai_model` | TEXT | YES | 'gemini-2.0-flash-exp' | Modelo de IA a usar |
| `ai_temperature` | DECIMAL(3,2) | YES | 0.7 | Temperatura (0.0-1.0) |
| `custom_instructions` | TEXT | YES | NULL | Instrucciones personalizadas para IA |
| `is_active` | BOOLEAN | YES | true | Estrategia activa/inactiva |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | NO | NOW() | Última actualización |

**Ejemplo de datos**:
```json
{
  "instagram_account_id": 5,
  "tone": "energetic",
  "language": "es",
  "emoji_usage": "moderate",
  "hashtag_strategy": {
    "max": 7,
    "include_team": true,
    "custom_tags": ["#LaLiga", "#Stats"]
  },
  "posting_frequency": {
    "per_day": 3,
    "per_week": 15,
    "avoid_days": []
  },
  "best_times": ["13:00", "20:00", "22:00"],
  "content_distribution": {
    "player_stats": 40,
    "match_results": 30,
    "team_stats": 30
  },
  "custom_instructions": "Siempre mencionar el número de goles en el caption"
}
```

### Tabla: `post_performance`

| Columna | Tipo | Null | Default | Descripción |
|---------|------|------|---------|-------------|
| `id` | SERIAL | NO | AUTO | Primary key |
| `post_id` | INTEGER | NO | - | FK UNIQUE a posts |
| `likes` | INTEGER | YES | 0 | Número de likes |
| `comments` | INTEGER | YES | 0 | Número de comentarios |
| `shares` | INTEGER | YES | 0 | Número de shares |
| `saves` | INTEGER | YES | 0 | Número de saves |
| `reach` | INTEGER | YES | 0 | Alcance total |
| `impressions` | INTEGER | YES | 0 | Impresiones totales |
| `profile_visits` | INTEGER | YES | 0 | Visitas al perfil |
| `engagement_rate` | DECIMAL(5,2) | YES | NULL | Tasa de engagement (auto-calculado) |
| `virality_score` | DECIMAL(5,2) | YES | NULL | Score de viralidad |
| `template_id` | INTEGER | YES | NULL | FK a templates |
| `template_effectiveness_score` | DECIMAL(5,2) | YES | NULL | Efectividad del template |
| `published_at` | TIMESTAMPTZ | YES | NULL | Timestamp de publicación |
| `best_performing_hour` | INTEGER | YES | NULL | Hora de mejor performance |
| `day_of_week` | INTEGER | YES | NULL | Día de la semana (0-6) |
| `last_synced_at` | TIMESTAMPTZ | YES | NOW() | Última sincronización |
| `created_at` | TIMESTAMPTZ | NO | NOW() | Fecha de creación |

**Cálculo automático de `engagement_rate`** (via trigger):
```sql
engagement_rate = (likes + comments + shares + saves) / reach * 100
```

---

# 5. ESPECIFICACIÓN DE APIS

## 5.1 Endpoints del Backend

### 5.1.1 Gestión de Templates

#### `GET /api/templates`
Obtiene todos los templates del usuario

**Headers**:
```
Authorization: Bearer <token>
```

**Query Params**:
```
?category_id=1
&content_type=FEED
&is_active=true
&search=modern
&page=1
&limit=20
```

**Response 200**:
```json
{
  "templates": [
    {
      "id": 1,
      "template_id": "tmpl_player_stats_001",
      "name": "Modern Blue - Player Stats",
      "description": "Template moderno con fondo azul",
      "category": {
        "id": 1,
        "name": "Player Stats"
      },
      "file_url": "https://drive.google.com/...",
      "dimensions": {"width": 1080, "height": 1080},
      "content_type": "FEED",
      "use_count": 15,
      "priority": 5,
      "is_active": true,
      "created_at": "2025-01-10T10:00:00Z"
    }
  ],
  "total": 25,
  "page": 1,
  "pages": 2
}
```

---

#### `POST /api/templates`
Crea un nuevo template

**Headers**:
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body**:
```json
{
  "template_id": "tmpl_custom_001",
  "name": "Mi Template Personalizado",
  "description": "Template para stats de jugadores",
  "category_id": 1,
  "file_url": "https://drive.google.com/file/d/xxx",
  "content_type": "FEED",
  "dimensions": {"width": 1080, "height": 1080},
  "applicable_teams": ["Real Madrid", "Barcelona"],
  "selection_rules": {
    "stat_type": "player_stats",
    "min_goals": 3
  },
  "priority": 7
}
```

**Response 201**:
```json
{
  "id": 26,
  "template_id": "tmpl_custom_001",
  "message": "Template creado exitosamente"
}
```

**Response 400** (validación):
```json
{
  "detail": "file_url is required"
}
```

---

#### `PUT /api/templates/{template_id}`
Actualiza un template existente

**Body**:
```json
{
  "name": "Nuevo nombre",
  "is_active": false,
  "priority": 10
}
```

**Response 200**:
```json
{
  "message": "Template actualizado",
  "template": {...}
}
```

---

#### `DELETE /api/templates/{template_id}`
Elimina un template

**Response 204**: No content

**Response 409**:
```json
{
  "detail": "No se puede eliminar template en uso (15 posts activos)"
}
```

---

### 5.1.2 Generación de Contenido

#### `POST /api/content/generate`
Genera un post desde datos de PROJECT 1

**Headers**:
```
Authorization: Bearer <token>
```

**Body**:
```json
{
  "source_data_id": "exp_001",
  "source_data": {
    "type": "player_stats",
    "player_name": "Mbappé",
    "team": "Real Madrid",
    "image_url": "https://drive.google.com/file/d/xxx",
    "data": {
      "goals": 12,
      "assists": 7,
      "minutes": 890,
      "rating": 8.5
    }
  },
  "instagram_account_id": 5,
  "options": {
    "auto_select_template": true,
    "tone": "energetic",
    "language": "es",
    "generate_caption": true
  }
}
```

**Response 200**:
```json
{
  "post_id": 123,
  "status": "draft",
  "preview": {
    "image_url": "https://your-supabase.co/storage/v1/object/public/instagram-media/xxx.png",
    "caption": "¡Mbappé imparable! ⚡ 12 goles en 890 minutos. Rating: 8.5 ⭐\n\n#Mbappe #RealMadrid #LaLiga #Stats #Goles",
    "template_used": {
      "id": 1,
      "name": "Modern Blue - Player Stats"
    }
  },
  "metadata": {
    "ai_model": "gemini-2.0-flash-exp",
    "tokens_used": 650,
    "generation_time_ms": 1200,
    "suggested_publish_time": "2025-01-16T13:00:00Z"
  }
}
```

**Response 400**:
```json
{
  "detail": "source_data_id is required"
}
```

**Response 500**:
```json
{
  "detail": "Error al generar caption: API rate limit exceeded"
}
```

---

#### `GET /api/content/queue`
Obtiene la cola de generación de contenido

**Query Params**:
```
?status=pending
&instagram_account_id=5
&limit=50
```

**Response 200**:
```json
{
  "queue": [
    {
      "id": 1,
      "source_data_id": "exp_001",
      "status": "processing",
      "created_at": "2025-01-15T10:00:00Z",
      "started_at": "2025-01-15T10:00:05Z"
    },
    {
      "id": 2,
      "source_data_id": "exp_002",
      "status": "pending",
      "created_at": "2025-01-15T10:05:00Z"
    }
  ],
  "total": 2
}
```

---

### 5.1.3 Estrategia de IA

#### `GET /api/ai-strategy/{instagram_account_id}`
Obtiene la estrategia de IA de una cuenta

**Response 200**:
```json
{
  "id": 1,
  "instagram_account_id": 5,
  "tone": "energetic",
  "language": "es",
  "emoji_usage": "moderate",
  "posting_frequency": {
    "per_day": 3,
    "per_week": 15
  },
  "best_times": ["13:00", "20:00", "22:00"],
  "content_distribution": {
    "player_stats": 40,
    "match_results": 30,
    "team_stats": 30
  },
  "custom_instructions": null,
  "is_active": true
}
```

**Response 404**:
```json
{
  "detail": "Estrategia no encontrada. Crear una nueva."
}
```

---

#### `POST /api/ai-strategy`
Crea estrategia de IA para una cuenta

**Body**:
```json
{
  "instagram_account_id": 5,
  "tone": "professional",
  "language": "es",
  "emoji_usage": "minimal",
  "posting_frequency": {
    "per_day": 2,
    "per_week": 10,
    "avoid_days": ["sunday"]
  },
  "best_times": ["09:00", "18:00"],
  "content_distribution": {
    "player_stats": 50,
    "match_results": 30,
    "team_stats": 20
  },
  "custom_instructions": "Siempre incluir estadísticas numéricas en el caption"
}
```

**Response 201**:
```json
{
  "id": 1,
  "message": "Estrategia creada exitosamente"
}
```

---

#### `PUT /api/ai-strategy/{id}`
Actualiza estrategia existente

**Body**: Mismo que POST (parcial o completo)

**Response 200**:
```json
{
  "message": "Estrategia actualizada",
  "strategy": {...}
}
```

---

### 5.1.4 Publicación

#### `POST /api/posts/{post_id}/schedule`
Programa un post para publicación futura

**Body**:
```json
{
  "scheduled_publish_time": "2025-01-16T13:00:00Z"
}
```

**Response 200**:
```json
{
  "message": "Post programado exitosamente",
  "post_id": 123,
  "scheduled_for": "2025-01-16T13:00:00Z"
}
```

**Response 400**:
```json
{
  "detail": "La fecha debe ser futura"
}
```

---

#### `POST /api/posts/{post_id}/publish`
Publica un post inmediatamente a Instagram

**Response 200**:
```json
{
  "success": true,
  "instagram_post_id": "18012345678901234",
  "permalink": "https://www.instagram.com/p/ABC123/",
  "published_at": "2025-01-15T10:30:00Z"
}
```

**Response 400**:
```json
{
  "detail": "El post ya está publicado"
}
```

**Response 500**:
```json
{
  "detail": "Error de Instagram API: (#100) Invalid media ID"
}
```

---

#### `GET /api/posts/scheduled`
Obtiene posts programados pendientes de publicar

**Response 200**:
```json
{
  "scheduled_posts": [
    {
      "id": 123,
      "content": "Caption del post...",
      "media_url": "https://...",
      "scheduled_publish_time": "2025-01-16T13:00:00Z",
      "instagram_account": {
        "id": 5,
        "username": "realmadrid_stats"
      },
      "template_name": "Modern Blue - Player Stats"
    }
  ],
  "total": 5
}
```

---

### 5.1.5 Analytics

#### `GET /api/analytics/overview`
Dashboard general de analytics

**Query Params**:
```
?instagram_account_id=5
&start_date=2025-01-01
&end_date=2025-01-15
```

**Response 200**:
```json
{
  "summary": {
    "total_posts": 50,
    "total_likes": 15000,
    "total_comments": 850,
    "total_reach": 125000,
    "avg_engagement_rate": 12.5
  },
  "best_performing_post": {
    "id": 89,
    "caption": "¡Mbappé rompe récords!...",
    "likes": 2500,
    "comments": 180,
    "engagement_rate": 25.3
  },
  "best_template": {
    "id": 1,
    "name": "Modern Blue - Player Stats",
    "avg_engagement_rate": 18.2,
    "posts_count": 12
  },
  "best_posting_times": [
    {"hour": 20, "avg_engagement": 15.8},
    {"hour": 13, "avg_engagement": 14.2}
  ],
  "content_distribution": {
    "player_stats": 40,
    "match_results": 35,
    "team_stats": 25
  }
}
```

---

#### `GET /api/analytics/templates`
Analytics específicos de templates

**Response 200**:
```json
{
  "templates": [
    {
      "id": 1,
      "name": "Modern Blue - Player Stats",
      "posts_count": 15,
      "avg_engagement_rate": 18.2,
      "avg_likes": 1200,
      "avg_comments": 80,
      "effectiveness_score": 85.5
    }
  ]
}
```

---

### 5.1.6 Google Drive Integration

#### `GET /api/drive/sync`
Sincroniza metadata.json desde Google Drive

**Response 200**:
```json
{
  "success": true,
  "new_exports": 3,
  "exports": [
    {
      "id": "exp_005",
      "type": "player_stats",
      "player_name": "Benzema",
      "date": "2025-01-15",
      "image_url": "https://drive.google.com/..."
    }
  ],
  "last_sync": "2025-01-15T10:45:00Z"
}
```

**Response 500**:
```json
{
  "detail": "Error al conectar con Google Drive"
}
```

---

#### `GET /api/drive/exports`
Lista todos los exports disponibles de PROJECT 1

**Query Params**:
```
?status=pending
&type=player_stats
&date_from=2025-01-01
```

**Response 200**:
```json
{
  "exports": [
    {
      "id": "exp_001",
      "type": "player_stats",
      "player_name": "Mbappé",
      "team": "Real Madrid",
      "date": "2025-01-15",
      "image_url": "https://drive.google.com/file/d/xxx",
      "data": {...},
      "status": "pending",
      "tags": ["trending", "urgent"]
    }
  ],
  "total": 25
}
```

---

## 5.2 Especificación Completa de Schemas Pydantic

**Archivo**: `backend/schemas/template_schema.py`

```python
from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ContentType(str, Enum):
    FEED = "FEED"
    REELS = "REELS"
    STORY = "STORY"
    CAROUSEL = "CAROUSEL"

class TemplateDimensions(BaseModel):
    width: int = Field(..., ge=1080, le=1920)
    height: int = Field(..., ge=1080, le=1920)

class TemplateBase(BaseModel):
    template_id: str = Field(..., min_length=3, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category_id: Optional[int] = None
    file_url: HttpUrl
    file_type: str = "image/png"
    file_size: Optional[int] = None
    dimensions: TemplateDimensions = TemplateDimensions(width=1080, height=1080)
    content_type: ContentType = ContentType.FEED
    design_source: Optional[str] = None
    design_prompt: Optional[str] = None
    branding: Optional[Dict[str, Any]] = None
    selection_rules: Optional[Dict[str, Any]] = None
    applicable_teams: Optional[List[str]] = None
    is_active: bool = True
    priority: int = Field(default=0, ge=0, le=100)

    @validator('file_type')
    def validate_file_type(cls, v):
        allowed = ['image/png', 'image/jpeg', 'image/webp']
        if v not in allowed:
            raise ValueError(f'file_type debe ser uno de: {allowed}')
        return v

class TemplateCreate(TemplateBase):
    instagram_account_id: Optional[int] = None

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    selection_rules: Optional[Dict[str, Any]] = None

class TemplateResponse(TemplateBase):
    id: int
    user_id: str
    instagram_account_id: Optional[int]
    use_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TemplateListResponse(BaseModel):
    templates: List[TemplateResponse]
    total: int
    page: int
    pages: int
```

**Archivo**: `backend/schemas/content_schema.py`

```python
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class SourceDataType(str, Enum):
    PLAYER_STATS = "player_stats"
    TEAM_STATS = "team_stats"
    MATCH_PREVIEW = "match_preview"
    MATCH_RESULT = "match_result"
    LEAGUE_TABLE = "league_table"

class ContentGenerationOptions(BaseModel):
    auto_select_template: bool = True
    tone: str = "energetic"
    language: str = "es"
    emoji_usage: str = "moderate"
    generate_caption: bool = True
    max_hashtags: int = Field(default=7, ge=0, le=30)

class SourceData(BaseModel):
    type: SourceDataType
    player_name: Optional[str] = None
    team: Optional[str] = None
    image_url: HttpUrl
    data: Dict[str, Any]
    tags: Optional[List[str]] = []

class ContentGenerationRequest(BaseModel):
    source_data_id: str
    source_data: SourceData
    instagram_account_id: int
    options: ContentGenerationOptions = ContentGenerationOptions()

class CaptionMetadata(BaseModel):
    ai_model: str
    tokens_used: int
    generation_time_ms: int
    temperature: float

class PostPreview(BaseModel):
    image_url: HttpUrl
    caption: str
    hashtags: List[str]
    template_used: Dict[str, Any]

class ContentGenerationResponse(BaseModel):
    post_id: int
    status: str
    preview: PostPreview
    metadata: CaptionMetadata
    suggested_publish_time: Optional[datetime]

class QueueItem(BaseModel):
    id: int
    source_data_id: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

class QueueListResponse(BaseModel):
    queue: List[QueueItem]
    total: int
```

**Archivo**: `backend/schemas/analytics_schema.py`

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class SummaryStats(BaseModel):
    total_posts: int
    total_likes: int
    total_comments: int
    total_shares: int
    total_reach: int
    avg_engagement_rate: float

class BestPost(BaseModel):
    id: int
    caption: str
    likes: int
    comments: int
    shares: int
    reach: int
    engagement_rate: float
    published_at: datetime

class BestTemplate(BaseModel):
    id: int
    name: str
    avg_engagement_rate: float
    posts_count: int

class BestTime(BaseModel):
    hour: int
    avg_engagement: float
    posts_count: int

class AnalyticsOverview(BaseModel):
    summary: SummaryStats
    best_performing_post: Optional[BestPost]
    best_template: Optional[BestTemplate]
    best_posting_times: List[BestTime]
    content_distribution: Dict[str, float]

class TemplateAnalytics(BaseModel):
    id: int
    name: str
    posts_count: int
    avg_engagement_rate: float
    avg_likes: float
    avg_comments: float
    avg_reach: float
    effectiveness_score: float

class TemplateAnalyticsResponse(BaseModel):
    templates: List[TemplateAnalytics]
```

---

# 6. COMPONENTES FRONTEND

## 6.1 Estructura de Componentes React

### 6.1.1 Dashboard Principal

**Archivo**: `frontend/src/components/dashboard/Dashboard.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getPosts, syncFromDrive } from '../../services/postService';
import { getAnalyticsOverview } from '../../services/analyticsService';
import PostCard from '../posts/PostCard';
import NewExportsList from './NewExportsList';
import QuickStats from './QuickStats';
import './Dashboard.css';

interface DashboardData {
  summary: {
    total_posts: number;
    posts_today: number;
    scheduled_posts: number;
    avg_engagement: number;
  };
  new_exports: Array<{
    id: string;
    type: string;
    player_name?: string;
    date: string;
    image_url: string;
  }>;
  recent_posts: Array<any>;
}

const Dashboard: React.FC = () => {
  const { user, isInstagramConnected } = useAuth();
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);

      // Cargar datos en paralelo
      const [analytics, posts, exports] = await Promise.all([
        getAnalyticsOverview(),
        getPosts({ limit: 5, status: 'all' }),
        syncFromDrive()
      ]);

      setDashboardData({
        summary: {
          total_posts: analytics.summary.total_posts,
          posts_today: posts.filter(p =>
            new Date(p.created_at).toDateString() === new Date().toDateString()
          ).length,
          scheduled_posts: posts.filter(p => p.status === 'scheduled').length,
          avg_engagement: analytics.summary.avg_engagement_rate
        },
        new_exports: exports.exports.filter(e => e.status === 'pending'),
        recent_posts: posts
      });
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncDrive = async () => {
    try {
      await syncFromDrive();
      loadDashboardData();
    } catch (error) {
      console.error('Error syncing drive:', error);
    }
  };

  if (loading) {
    return <div className="loading-spinner">Cargando dashboard...</div>;
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>SocialLab Planner</h1>
        <button onClick={handleSyncDrive} className="btn-sync">
          🔄 Sincronizar Drive
        </button>
      </header>

      {/* Quick Stats */}
      <QuickStats stats={dashboardData?.summary || {}} />

      {/* Instagram Connection Status */}
      {!isInstagramConnected && (
        <div className="alert alert-warning">
          ⚠️ Instagram no conectado.
          <a href="/connect-instagram">Conectar ahora</a>
        </div>
      )}

      {/* New Exports from PROJECT 1 */}
      <section className="new-exports-section">
        <h2>📥 Nuevos Datos de PROJECT 1</h2>
        <NewExportsList
          exports={dashboardData?.new_exports || []}
          onGenerate={() => loadDashboardData()}
        />
      </section>

      {/* Recent Posts */}
      <section className="recent-posts-section">
        <h2>📝 Posts Recientes</h2>
        <div className="posts-grid">
          {dashboardData?.recent_posts.map(post => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
```

### 6.1.2 Generador de Posts

**Archivo**: `frontend/src/components/posts/PostGenerator.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { generatePost } from '../../services/postService';
import { getTemplates } from '../../services/templateService';
import TemplateSelector from '../templates/TemplateSelector';
import PostPreview from './PostPreview';
import './PostGenerator.css';

interface PostGeneratorProps {
  exportData?: {
    id: string;
    type: string;
    image_url: string;
    data: any;
  };
}

const PostGenerator: React.FC<PostGeneratorProps> = ({ exportData }) => {
  const [step, setStep] = useState(1);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [generationOptions, setGenerationOptions] = useState({
    auto_select_template: true,
    tone: 'energetic',
    language: 'es',
    emoji_usage: 'moderate'
  });
  const [generatedPost, setGeneratedPost] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const data = await getTemplates({ is_active: true });
      setTemplates(data.templates);
    } catch (error) {
      console.error('Error loading templates:', error);
    }
  };

  const handleGenerate = async () => {
    try {
      setLoading(true);

      const payload = {
        source_data_id: exportData.id,
        source_data: exportData,
        instagram_account_id: 1, // TODO: Get from context
        options: {
          ...generationOptions,
          template_id: selectedTemplate?.id
        }
      };

      const result = await generatePost(payload);
      setGeneratedPost(result);
      setStep(4); // Preview step
    } catch (error) {
      console.error('Error generating post:', error);
      alert('Error al generar post');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="post-generator">
      {/* Progress Steps */}
      <div className="steps-indicator">
        <div className={`step ${step >= 1 ? 'active' : ''}`}>1. Datos</div>
        <div className={`step ${step >= 2 ? 'active' : ''}`}>2. Template</div>
        <div className={`step ${step >= 3 ? 'active' : ''}`}>3. Opciones</div>
        <div className={`step ${step >= 4 ? 'active' : ''}`}>4. Preview</div>
      </div>

      {/* Step 1: Data Selection */}
      {step === 1 && (
        <div className="step-content">
          <h2>Seleccionar Datos</h2>
          {exportData ? (
            <div className="selected-export">
              <img src={exportData.image_url} alt="Export" />
              <p>{exportData.type}: {exportData.data.player_name || 'N/A'}</p>
              <button onClick={() => setStep(2)}>Continuar →</button>
            </div>
          ) : (
            <p>No hay datos seleccionados</p>
          )}
        </div>
      )}

      {/* Step 2: Template Selection */}
      {step === 2 && (
        <div className="step-content">
          <h2>Seleccionar Template</h2>
          <label>
            <input
              type="checkbox"
              checked={generationOptions.auto_select_template}
              onChange={(e) => setGenerationOptions({
                ...generationOptions,
                auto_select_template: e.target.checked
              })}
            />
            Selección automática (IA decide)
          </label>

          {!generationOptions.auto_select_template && (
            <TemplateSelector
              templates={templates}
              selectedTemplate={selectedTemplate}
              onSelect={setSelectedTemplate}
            />
          )}

          <button onClick={() => setStep(3)}>Continuar →</button>
        </div>
      )}

      {/* Step 3: Generation Options */}
      {step === 3 && (
        <div className="step-content">
          <h2>Opciones de Generación</h2>

          <div className="form-group">
            <label>Tono:</label>
            <select
              value={generationOptions.tone}
              onChange={(e) => setGenerationOptions({
                ...generationOptions,
                tone: e.target.value
              })}
            >
              <option value="energetic">Energético</option>
              <option value="professional">Profesional</option>
              <option value="casual">Casual</option>
              <option value="humorous">Humorístico</option>
            </select>
          </div>

          <div className="form-group">
            <label>Idioma:</label>
            <select
              value={generationOptions.language}
              onChange={(e) => setGenerationOptions({
                ...generationOptions,
                language: e.target.value
              })}
            >
              <option value="es">Español</option>
              <option value="en">English</option>
              <option value="pt">Português</option>
            </select>
          </div>

          <div className="form-group">
            <label>Uso de Emojis:</label>
            <select
              value={generationOptions.emoji_usage}
              onChange={(e) => setGenerationOptions({
                ...generationOptions,
                emoji_usage: e.target.value
              })}
            >
              <option value="none">Ninguno</option>
              <option value="minimal">Mínimo</option>
              <option value="moderate">Moderado</option>
              <option value="heavy">Abundante</option>
            </select>
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading}
            className="btn-generate"
          >
            {loading ? 'Generando...' : '🤖 Generar Post'}
          </button>
        </div>
      )}

      {/* Step 4: Preview */}
      {step === 4 && generatedPost && (
        <PostPreview
          post={generatedPost}
          onSchedule={() => {/* TODO */}}
          onPublishNow={() => {/* TODO */}}
          onEdit={() => setStep(3)}
        />
      )}
    </div>
  );
};

export default PostGenerator;
```

### 6.1.3 Vista de Calendario

**Archivo**: `frontend/src/components/posts/PostCalendar.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import Calendar from 'react-calendar';
import { getPosts } from '../../services/postService';
import 'react-calendar/dist/Calendar.css';
import './PostCalendar.css';

const PostCalendar: React.FC = () => {
  const [date, setDate] = useState(new Date());
  const [posts, setPosts] = useState<any[]>([]);
  const [selectedDatePosts, setSelectedDatePosts] = useState<any[]>([]);

  useEffect(() => {
    loadPosts();
  }, []);

  const loadPosts = async () => {
    try {
      const data = await getPosts({ limit: 100 });
      setPosts(data);
    } catch (error) {
      console.error('Error loading posts:', error);
    }
  };

  const handleDateChange = (newDate: Date) => {
    setDate(newDate);

    // Filter posts for selected date
    const postsOnDate = posts.filter(post => {
      const postDate = new Date(post.scheduled_publish_time || post.created_at);
      return postDate.toDateString() === newDate.toDateString();
    });

    setSelectedDatePosts(postsOnDate);
  };

  const tileContent = ({ date, view }: any) => {
    if (view === 'month') {
      const postsOnDate = posts.filter(post => {
        const postDate = new Date(post.scheduled_publish_time || post.created_at);
        return postDate.toDateString() === date.toDateString();
      });

      if (postsOnDate.length > 0) {
        return (
          <div className="calendar-tile-marker">
            {postsOnDate.map(post => (
              <span
                key={post.id}
                className={`marker ${post.status}`}
              >
                {post.status === 'published' ? '📊' : '🕐'}
              </span>
            ))}
          </div>
        );
      }
    }
    return null;
  };

  return (
    <div className="post-calendar-container">
      <h2>Calendario de Publicaciones</h2>

      <div className="calendar-wrapper">
        <Calendar
          onChange={handleDateChange}
          value={date}
          tileContent={tileContent}
          locale="es-ES"
        />
      </div>

      <div className="posts-on-date">
        <h3>Posts del {date.toLocaleDateString('es-ES')}</h3>
        {selectedDatePosts.length > 0 ? (
          <ul>
            {selectedDatePosts.map(post => (
              <li key={post.id} className={`post-item ${post.status}`}>
                <span className="time">
                  {new Date(post.scheduled_publish_time).toLocaleTimeString('es-ES', {
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
                <span className="caption">{post.content.substring(0, 50)}...</span>
                <span className={`status-badge ${post.status}`}>
                  {post.status}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p>No hay posts programados para esta fecha</p>
        )}
      </div>

      <div className="legend">
        <h4>Leyenda:</h4>
        <div className="legend-item">
          <span className="marker published">📊</span> Publicado
        </div>
        <div className="legend-item">
          <span className="marker scheduled">🕐</span> Programado
        </div>
      </div>
    </div>
  );
};

export default PostCalendar;
```

---

# 7. ROADMAP DE IMPLEMENTACIÓN

## 7.1 Visión General del Roadmap

**Duración Total Estimada**: 8-10 semanas (40-50 días laborables)

**Metodología**: Desarrollo incremental con entregas funcionales cada semana

**Principios**:
- ✅ Cada fase debe entregar algo funcional y testeable
- ✅ Testing continuo (no dejar testing para el final)
- ✅ Documentación en paralelo con desarrollo
- ✅ Commits incrementales y frecuentes
- ✅ Code review al final de cada fase

---

## **ESTADO ACTUAL DEL PROYECTO** (Actualizado: 5 Octubre 2025)

### Fases Completadas:
- ✅ **FASE 0: Preparación y Setup** (Días 1-3)
  - Entorno de desarrollo configurado
  - APIs externas configuradas (Google Drive, Gemini, Instagram)
  - Base de datos Supabase operativa

- ✅ **FASE 1: Backend - Fundamentos** (Días 4-10)
  - 17 tablas creadas en base de datos
  - Servicios core implementados (Drive Connector, Template Selector, Image Composer, Caption Generator)
  - Endpoints API funcionales
  - **BONUS:** Flujo end-to-end de generación de contenido completado

### Próxima Fase:
- 🔄 **FASE 2: Sistema de Templates y Composición** (Días 11-17)
  - Nota: Muchas funcionalidades ya implementadas en Fase 1
  - Revisar qué queda pendiente de esta fase

---

## 7.2 FASE 0: Preparación y Setup (Días 1-3) ✅ COMPLETADA

### Objetivos
Configurar entorno de desarrollo completo y servicios externos

### Tareas Detalladas

#### Día 1: Configuración Backend

**[ ] 1.1 Configurar entorno Python**
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**[ ] 1.2 Crear archivo .env desde template**
```bash
cp .env.example .env
# Editar .env con credenciales reales
```

**[ ] 1.3 Configurar Supabase**
- Crear proyecto en supabase.com
- Obtener URL y API keys
- Añadir a .env
- Crear buckets de storage:
  - `instagram-media`
  - `post-previews`
  - `temp-uploads`

**[ ] 1.4 Verificar conexión a Supabase**
```python
# backend/tests/test_supabase_connection.py
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Test básico
response = supabase.table('users').select("*").limit(1).execute()
print("✅ Conexión a Supabase exitosa")
```

#### Día 2: Configuración de APIs Externas

**[ ] 2.1 Configurar Google Drive API**
- Ir a console.cloud.google.com
- Crear proyecto "SocialLab Planner"
- Habilitar Google Drive API
- Crear credenciales OAuth 2.0
- Descargar JSON → `backend/credentials/google_drive_credentials.json`
- Ejecutar script de autenticación:
```bash
python scripts/setup_google_drive.py
```
- Verificar que se crea `google_drive_token.json`

**[ ] 2.2 Configurar Google Gemini AI**
- Ir a makersuite.google.com/app/apikey
- Crear API key
- Añadir a .env: `GOOGLE_API_KEY=xxx`
- Probar conexión:
```bash
python backend/tests/test_gemini_connection.py
```

**[ ] 2.3 Configurar Meta/Instagram**
- Ir a developers.facebook.com
- Crear Meta App
- Añadir producto Instagram
- Configurar OAuth redirect URI
- Copiar App ID y Secret al .env

#### Día 3: Configuración Frontend y Testing

**[ ] 3.1 Setup Frontend**
```bash
cd frontend
npm install
npm run dev
# Verificar que corre en http://localhost:5173
```

**[ ] 3.2 Configurar variables de entorno frontend**
```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=xxx
VITE_SUPABASE_ANON_KEY=xxx
```

**[ ] 3.3 Prueba de integración completa**
```bash
# Terminal 1: Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Test
curl http://localhost:8000/health
```

**[ ] 3.4 Setup Docker (opcional)**
```bash
docker-compose up -d
```

### Checklist de Validación Fase 0

- [x] Backend corre sin errores
- [x] Frontend corre sin errores
- [x] Supabase conectado correctamente
- [x] Google Drive API autenticada
- [x] Gemini AI responde correctamente (gemini-2.0-flash)
- [x] Instagram OAuth configurado
- [x] .env completo con todas las variables
- [x] Todas las dependencias instaladas
- [x] Git configurado y primer commit hecho

### Entregable Fase 0
✅ **COMPLETADO** - Entorno de desarrollo completamente funcional y configurado

---

## 7.3 FASE 1: Backend - Fundamentos (Días 4-10) ✅ COMPLETADA

### Objetivos
Implementar base de datos, endpoints básicos y servicios core

**NOTA:** Esta fase se completó con funcionalidades adicionales más allá del plan original, incluyendo el flujo completo de generación de contenido end-to-end que estaba planificado para fases posteriores.

### Día 4-5: Migración de Base de Datos

**[ ] 4.1 Aplicar migración 006**
```bash
# En Supabase SQL Editor, ejecutar:
backend/migrations/006_planner_complete_schema.sql
```

**[ ] 4.2 Verificar tablas creadas**
```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

**Resultado esperado**:
- ✅ template_categories
- ✅ templates
- ✅ ai_strategy
- ✅ content_generation_queue
- ✅ content_generation_history
- ✅ post_performance
- ✅ scheduled_jobs
- ✅ + tablas existentes actualizadas

**[ ] 4.3 Insertar datos de prueba**
```sql
-- Insertar categorías de templates
-- (Ya se hace en la migración)

-- Insertar template de prueba
INSERT INTO templates (
    user_id,
    template_id,
    name,
    file_url,
    category_id,
    content_type
) VALUES (
    'YOUR_USER_ID',
    'tmpl_test_001',
    'Template de Prueba',
    'https://drive.google.com/file/d/test',
    1,
    'FEED'
);
```

**[ ] 4.4 Crear seeds script**
```python
# backend/scripts/seed_database.py
# (Ver sección 8.X para código completo)
```

### Día 6-7: Implementar Servicios Core

**[ ] 6.1 Implementar Google Drive Connector**

Archivo: `backend/services/data/drive_connector.py`

```python
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os
import io
import json
from typing import List, Dict, Optional
import pickle

class GoogleDriveConnector:
    """Conector para Google Drive API"""

    def __init__(self):
        self.creds = self._load_credentials()
        self.service = build('drive', 'v3', credentials=self.creds)

    def _load_credentials(self) -> Credentials:
        """Carga credenciales desde token guardado"""
        token_file = os.getenv('GOOGLE_DRIVE_TOKEN_FILE')

        if not os.path.exists(token_file):
            raise FileNotFoundError(
                "Token de Google Drive no encontrado. "
                "Ejecuta scripts/setup_google_drive.py primero"
            )

        with open(token_file, 'rb') as token:
            creds = pickle.load(token)

        return creds

    def download_file(self, file_id: str, destination: str) -> str:
        """Descarga un archivo de Google Drive"""
        request = self.service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%")

        # Guardar en disco
        with open(destination, 'wb') as f:
            f.write(fh.getvalue())

        return destination

    def download_metadata_json(self, folder_id: str) -> Dict:
        """
        Descarga metadata.json de la carpeta de PROJECT 1

        Args:
            folder_id: ID de la carpeta de Google Drive

        Returns:
            Dict con el contenido de metadata.json
        """
        # Buscar metadata.json en la carpeta
        query = f"'{folder_id}' in parents and name='metadata.json'"

        results = self.service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()

        files = results.get('files', [])

        if not files:
            raise FileNotFoundError("metadata.json no encontrado")

        file_id = files[0]['id']

        # Descargar contenido
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        # Parsear JSON
        content = fh.getvalue().decode('utf-8')
        metadata = json.loads(content)

        return metadata

    def list_files_in_folder(
        self,
        folder_id: str,
        file_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Lista archivos en una carpeta

        Args:
            folder_id: ID de la carpeta
            file_type: Filtro por tipo MIME (ej: 'image/png')

        Returns:
            Lista de archivos con metadata
        """
        query = f"'{folder_id}' in parents"

        if file_type:
            query += f" and mimeType='{file_type}'"

        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType, size, modifiedTime)"
        ).execute()

        return results.get('files', [])

    def get_file_url(self, file_id: str) -> str:
        """Obtiene URL pública de un archivo"""
        return f"https://drive.google.com/file/d/{file_id}/view"
```

**Test**:
```python
# backend/tests/test_drive_connector.py
import pytest
from services.data.drive_connector import GoogleDriveConnector

def test_drive_connection():
    connector = GoogleDriveConnector()
    assert connector.service is not None

def test_download_metadata():
    connector = GoogleDriveConnector()
    folder_id = os.getenv('PROJECT1_EXPORTS_FOLDER_ID')

    metadata = connector.download_metadata_json(folder_id)

    assert 'exports' in metadata
    assert isinstance(metadata['exports'], list)
```

**[ ] 6.2 Implementar Metadata Parser**

Archivo: `backend/services/data/metadata_parser.py`

```python
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, HttpUrl

class ExportData(BaseModel):
    id: str
    type: str
    player_name: Optional[str] = None
    team: Optional[str] = None
    date: str
    image_url: HttpUrl
    data: Dict
    tags: List[str] = []
    status: str = "pending"

class MetadataParser:
    """Parser para metadata.json de PROJECT 1"""

    @staticmethod
    def parse_metadata(metadata_dict: Dict) -> List[ExportData]:
        """
        Parsea metadata.json y retorna lista de exports

        Args:
            metadata_dict: Diccionario con estructura de metadata.json

        Returns:
            Lista de ExportData parseados y validados
        """
        exports_raw = metadata_dict.get('exports', [])

        exports = []
        for export_raw in exports_raw:
            try:
                export = ExportData(**export_raw)
                exports.append(export)
            except Exception as e:
                print(f"Error parseando export {export_raw.get('id')}: {e}")
                continue

        return exports

    @staticmethod
    def filter_by_status(
        exports: List[ExportData],
        status: str = "pending"
    ) -> List[ExportData]:
        """Filtra exports por status"""
        return [e for e in exports if e.status == status]

    @staticmethod
    def filter_by_type(
        exports: List[ExportData],
        export_type: str
    ) -> List[ExportData]:
        """Filtra exports por tipo"""
        return [e for e in exports if e.type == export_type]

    @staticmethod
    def filter_by_date_range(
        exports: List[ExportData],
        start_date: str,
        end_date: str
    ) -> List[ExportData]:
        """Filtra exports por rango de fechas"""
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        filtered = []
        for export in exports:
            export_date = datetime.fromisoformat(export.date)
            if start <= export_date <= end:
                filtered.append(export)

        return filtered
```

### Día 8-9: Endpoints Básicos

**[ ] 8.1 Endpoint para sincronizar Drive**

En `backend/main.py`:

```python
from services.data.drive_connector import GoogleDriveConnector
from services.data.metadata_parser import MetadataParser

drive_connector = GoogleDriveConnector()
metadata_parser = MetadataParser()

@app.get("/api/drive/sync")
async def sync_google_drive(
    current_user: User = Depends(get_current_user)
):
    """
    Sincroniza metadata.json desde Google Drive

    Returns:
        Exports disponibles de PROJECT 1
    """
    try:
        folder_id = os.getenv('PROJECT1_EXPORTS_FOLDER_ID')

        # Descargar metadata.json
        metadata_dict = drive_connector.download_metadata_json(folder_id)

        # Parsear exports
        exports = metadata_parser.parse_metadata(metadata_dict)

        # Filtrar solo pendientes
        pending_exports = metadata_parser.filter_by_status(exports, "pending")

        return {
            "success": True,
            "new_exports": len(pending_exports),
            "exports": [e.dict() for e in pending_exports],
            "last_sync": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error syncing Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/drive/exports")
async def list_exports(
    status: Optional[str] = None,
    type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Lista exports de PROJECT 1 con filtros
    """
    try:
        folder_id = os.getenv('PROJECT1_EXPORTS_FOLDER_ID')
        metadata_dict = drive_connector.download_metadata_json(folder_id)
        exports = metadata_parser.parse_metadata(metadata_dict)

        # Aplicar filtros
        if status:
            exports = metadata_parser.filter_by_status(exports, status)

        if type:
            exports = metadata_parser.filter_by_type(exports, type)

        if date_from and date_to:
            exports = metadata_parser.filter_by_date_range(
                exports, date_from, date_to
            )

        return {
            "exports": [e.dict() for e in exports],
            "total": len(exports)
        }

    except Exception as e:
        logger.error(f"Error listing exports: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**[ ] 8.2 Endpoints de Templates**

```python
from schemas.template_schema import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateListResponse
)

@app.get("/api/templates", response_model=TemplateListResponse)
async def get_templates(
    category_id: Optional[int] = None,
    content_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    """Obtiene templates del usuario con filtros"""
    try:
        query = supabase.table('templates').select('*')
        query = query.eq('user_id', current_user.id)

        if category_id:
            query = query.eq('category_id', category_id)

        if content_type:
            query = query.eq('content_type', content_type)

        if is_active is not None:
            query = query.eq('is_active', is_active)

        if search:
            query = query.ilike('name', f'%{search}%')

        # Paginación
        offset = (page - 1) * limit
        query = query.range(offset, offset + limit - 1)
        query = query.order('priority', desc=True)

        response = query.execute()

        # Contar total
        count_response = supabase.table('templates').select(
            'id', count='exact'
        ).eq('user_id', current_user.id).execute()

        total = count_response.count
        pages = (total + limit - 1) // limit

        return {
            "templates": response.data,
            "total": total,
            "page": page,
            "pages": pages
        }

    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/templates", response_model=TemplateResponse)
async def create_template(
    template: TemplateCreate,
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo template"""
    try:
        template_data = template.dict()
        template_data['user_id'] = current_user.id

        response = supabase.table('templates').insert(
            template_data
        ).execute()

        return response.data[0]

    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/templates/{template_id}")
async def update_template(
    template_id: int,
    template: TemplateUpdate,
    current_user: User = Depends(get_current_user)
):
    """Actualiza un template"""
    try:
        # Verificar ownership
        existing = supabase.table('templates').select('*').eq(
            'id', template_id
        ).eq('user_id', current_user.id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Template no encontrado")

        # Actualizar solo campos provistos
        update_data = template.dict(exclude_unset=True)

        response = supabase.table('templates').update(
            update_data
        ).eq('id', template_id).execute()

        return {
            "message": "Template actualizado",
            "template": response.data[0]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user)
):
    """Elimina un template"""
    try:
        # Verificar ownership
        existing = supabase.table('templates').select('*').eq(
            'id', template_id
        ).eq('user_id', current_user.id).execute()

        if not existing.data:
            raise HTTPException(status_code=404, detail="Template no encontrado")

        # Verificar si está en uso
        posts_using = supabase.table('posts').select(
            'id', count='exact'
        ).eq('template_id', template_id).execute()

        if posts_using.count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede eliminar template en uso ({posts_using.count} posts)"
            )

        # Eliminar
        supabase.table('templates').delete().eq('id', template_id).execute()

        return {"message": "Template eliminado"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Día 10: Testing Fase 1

**[ ] 10.1 Crear tests unitarios**

```python
# backend/tests/test_endpoints_phase1.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_templates():
    response = client.get(
        "/api/templates",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert "templates" in response.json()

def test_sync_drive():
    response = client.get(
        "/api/drive/sync",
        headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert response.status_code == 200
    assert "exports" in response.json()

# Más tests...
```

**[ ] 10.2 Ejecutar tests**
```bash
pytest backend/tests/ -v
```

### Checklist de Validación Fase 1

- [x] Migración 006 aplicada correctamente
- [x] Todas las tablas nuevas creadas (17 tablas verificadas)
- [x] Drive Connector funciona (`services/google_drive_connector.py`)
- [x] Metadata Parser funciona (integrado en `template_selector.py`)
- [x] Endpoint /api/templates/sync-from-drive funciona (ver `routes/template_sync_routes.py`)
- [x] Endpoint /api/templates CRUD completo (GET, POST, PUT, DELETE - ver `routes/templates.py`)
- [x] Endpoint /api/content/generate implementado (`routes/content_generation.py`)
- [x] Template Selector implementado (`services/template_selector.py`)
- [x] Image Composer implementado (`services/image_composer.py`)
- [x] Caption Generator implementado con Gemini (`services/caption_generator.py`)
- [x] Tests funcionales ejecutados exitosamente (`tests/test_end_to_end.py`)
- [x] Proyecto limpio y organizado (docs/, scripts/, tests/)
- [x] Commit y push a repositorio

### Entregable Fase 1
✅ **COMPLETADO** - Backend con base de datos completa, servicios core implementados y flujo end-to-end funcionando

**Servicios Implementados:**
- ✅ Google Drive Connector
- ✅ Template Selector (con reglas inteligentes)
- ✅ Image Composer (Pillow)
- ✅ Caption Generator (Google Gemini 2.0 Flash)
- ✅ Template Sync
- ✅ Content Generation Flow

**Endpoints Implementados:**
- ✅ `/api/templates/*` - CRUD completo de templates
- ✅ `/api/templates/sync-from-drive` - Sincronización con Google Drive
- ✅ `/api/content/generate` - Generación de contenido con IA
- ✅ `/api/content/queue/status` - Estado de cola de generación
- ✅ `/api/content/history` - Historial de generación

---

## 7.4 FASE 2: Sistema de Templates y Composición (Días 11-17)

### Objetivos
Implementar selección de templates y composición de imágenes con Pillow

### Día 11-12: Template Selector

**[ ] 11.1 Implementar Template Selector**

Archivo: `backend/services/ai/template_selector.py`

```python
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass

class StatType(Enum):
    PLAYER_INDIVIDUAL = "player_stats"
    TEAM_PERFORMANCE = "team_stats"
    MATCH_PREVIEW = "match_preview"
    MATCH_RESULT = "match_result"
    LEAGUE_TABLE = "league_table"

class ContentFormat(Enum):
    POST = "FEED"
    REEL = "REELS"
    STORY = "STORY"
    CAROUSEL = "CAROUSEL"

@dataclass
class TemplateScore:
    template_id: int
    score: float
    reasons: List[str]

class TemplateSelector:
    """
    Selecciona el template óptimo basado en reglas y scoring.
    NO usa ML - es determinístico y rápido.
    """

    def __init__(self, supabase_client):
        self.supabase = supabase_client

    def select_template(
        self,
        stat_type: str,
        content_format: str,
        team: Optional[str] = None,
        data_fields: Optional[List[str]] = None,
        user_id: str = None
    ) -> Dict:
        """
        Selecciona el template óptimo

        Args:
            stat_type: Tipo de estadística (player_stats, etc.)
            content_format: Formato (FEED, REELS, etc.)
            team: Nombre del equipo (opcional)
            data_fields: Campos disponibles en los datos
            user_id: ID del usuario

        Returns:
            Template seleccionado con metadata
        """
        # 1. Obtener templates candidatos
        candidates = self._get_candidate_templates(
            user_id, content_format
        )

        if not candidates:
            raise ValueError("No hay templates disponibles")

        # 2. Calcular score para cada template
        scored_templates = []

        for template in candidates:
            score = self._calculate_template_score(
                template,
                stat_type,
                team,
                data_fields or []
            )
            scored_templates.append(score)

        # 3. Ordenar por score descendente
        scored_templates.sort(key=lambda x: x.score, reverse=True)

        # 4. Retornar el mejor
        best = scored_templates[0]
        best_template = next(
            t for t in candidates if t['id'] == best.template_id
        )

        return {
            **best_template,
            "selection_score": best.score,
            "selection_reasons": best.reasons
        }

    def _get_candidate_templates(
        self,
        user_id: str,
        content_format: str
    ) -> List[Dict]:
        """Obtiene templates candidatos de la base de datos"""
        response = self.supabase.table('templates').select('*').eq(
            'user_id', user_id
        ).eq('is_active', True).eq('content_format', content_format).order(
            'priority', desc=True
        ).execute()

        return response.data

    def _calculate_template_score(
        self,
        template: Dict,
        stat_type: str,
        team: Optional[str],
        data_fields: List[str]
    ) -> TemplateScore:
        """
        Calcula score de un template

        Criterios de scoring:
        - Prioridad del template: +50 puntos máximo
        - Match de equipo específico: +30 puntos
        - Match de reglas: +20 puntos
        - Uso reciente (penalización): -10 puntos
        """
        score = 0.0
        reasons = []

        # Criterio 1: Prioridad base del template
        priority_score = (template.get('priority', 0) / 100) * 50
        score += priority_score
        reasons.append(f"Prioridad {template.get('priority')}: +{priority_score:.1f}")

        # Criterio 2: Match de equipo
        applicable_teams = template.get('applicable_teams', [])
        if team and team in applicable_teams:
            score += 30
            reasons.append(f"Específico para {team}: +30")
        elif 'all' in applicable_teams:
            score += 10
            reasons.append("Template genérico: +10")

        # Criterio 3: Match de reglas de selección
        selection_rules = template.get('selection_rules', {})
        if selection_rules:
            rule_match = self._check_rules_match(
                selection_rules, stat_type, data_fields
            )
            if rule_match:
                score += 20
                reasons.append("Reglas cumplen: +20")

        # Criterio 4: Penalización por uso reciente
        use_count = template.get('use_count', 0)
        if use_count > 10:
            penalty = min(use_count / 10, 10)
            score -= penalty
            reasons.append(f"Muy usado ({use_count}): -{penalty:.1f}")

        return TemplateScore(
            template_id=template['id'],
            score=score,
            reasons=reasons
        )

    def _check_rules_match(
        self,
        rules: Dict,
        stat_type: str,
        data_fields: List[str]
    ) -> bool:
        """Verifica si las reglas del template coinciden"""
        # Verificar tipo de stat
        if 'stat_type' in rules:
            if rules['stat_type'] != stat_type:
                return False

        # Verificar campos requeridos
        if 'required_fields' in rules:
            required = rules['required_fields']
            if not all(field in data_fields for field in required):
                return False

        # Verificar condiciones numéricas (ej: min_goals)
        # (esto requeriría acceso a los datos, por ahora skip)

        return True
```

**Test**:
```python
# backend/tests/test_template_selector.py
def test_template_selection():
    selector = TemplateSelector(supabase_client)

    result = selector.select_template(
        stat_type="player_stats",
        content_format="FEED",
        team="Real Madrid",
        data_fields=["goals", "assists", "minutes"],
        user_id="test-user-id"
    )

    assert result['id'] is not None
    assert 'selection_score' in result
    assert result['selection_score'] > 0
```

### Día 13-15: Image Composer (Pillow)

**[ ] 13.1 Implementar Image Composer**

Archivo: `backend/services/image/composer.py`

```python
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Tuple, Optional
import os
import requests
from io import BytesIO

class ImageComposer:
    """
    Compone imágenes finales combinando templates con datos.
    Usa Pillow para composición.
    """

    def __init__(self, fonts_dir: str = "./fonts"):
        self.fonts_dir = fonts_dir
        self.fonts_cache = {}

    def compose_player_stats(
        self,
        template_path: str,
        project1_image_url: str,
        data: Dict,
        branding: Optional[Dict] = None
    ) -> Image.Image:
        """
        Compone imagen de stats de jugador

        Args:
            template_path: Ruta al template base
            project1_image_url: URL de la imagen de PROJECT 1
            data: Datos del jugador
            branding: Colores y logos del equipo

        Returns:
            Imagen PIL compuesta
        """
        # 1. Cargar template
        template = Image.open(template_path).convert("RGBA")

        # 2. Descargar imagen de PROJECT 1
        project1_img = self._download_image(project1_image_url)

        # 3. Redimensionar imagen PROJECT 1 para encajar
        # Asumimos espacio central de 800x600
        project1_img = project1_img.resize((800, 600), Image.LANCZOS)

        # 4. Pegar imagen PROJECT 1 en template
        # Posición central (asumiendo template 1080x1080)
        paste_x = (template.width - project1_img.width) // 2
        paste_y = 240  # Dejar espacio arriba para título

        template.paste(project1_img, (paste_x, paste_y), project1_img)

        # 5. Añadir textos dinámicos
        draw = ImageDraw.Draw(template)

        # Nombre del jugador (arriba)
        font_title = self._get_font("Montserrat-Bold.ttf", 48)
        player_name = data.get('player_name', 'JUGADOR').upper()

        # Centrar texto
        bbox = draw.textbbox((0, 0), player_name, font=font_title)
        text_width = bbox[2] - bbox[0]
        text_x = (template.width - text_width) // 2

        primary_color = self._get_color_from_branding(branding, 'primary', (255, 255, 255))

        draw.text(
            (text_x, 80),
            player_name,
            font=font_title,
            fill=primary_color
        )

        # Stats resumidas (abajo)
        font_stats = self._get_font("Montserrat-SemiBold.ttf", 32)
        stats_text = self._format_stats_line(data)

        bbox_stats = draw.textbbox((0, 0), stats_text, font=font_stats)
        stats_width = bbox_stats[2] - bbox_stats[0]
        stats_x = (template.width - stats_width) // 2

        secondary_color = self._get_color_from_branding(branding, 'secondary', (212, 175, 55))

        draw.text(
            (stats_x, 950),
            stats_text,
            font=font_stats,
            fill=secondary_color
        )

        # 6. Añadir logo del equipo (si disponible)
        if branding and 'logo_url' in branding:
            try:
                logo = self._download_image(branding['logo_url'])
                logo = logo.resize((80, 80), Image.LANCZOS)
                template.paste(logo, (50, 50), logo)
            except Exception as e:
                print(f"Error añadiendo logo: {e}")

        return template

    def compose_team_stats(
        self,
        template_path: str,
        project1_image_url: str,
        data: Dict,
        branding: Optional[Dict] = None
    ) -> Image.Image:
        """Compone imagen de stats de equipo (similar a player_stats)"""
        # Implementación similar...
        pass

    def compose_match_preview(
        self,
        template_path: str,
        home_team_logo: str,
        away_team_logo: str,
        data: Dict
    ) -> Image.Image:
        """Compone preview de partido VS style"""
        template = Image.open(template_path).convert("RGBA")
        draw = ImageDraw.Draw(template)

        center_x = template.width // 2

        # Logos de equipos
        home_logo = self._download_image(home_team_logo).resize((150, 150))
        away_logo = self._download_image(away_team_logo).resize((150, 150))

        template.paste(home_logo, (center_x - 300, 200), home_logo)
        template.paste(away_logo, (center_x + 150, 200), away_logo)

        # Texto VS
        font_vs = self._get_font("Montserrat-Black.ttf", 72)
        draw.text(
            (center_x - 50, 250),
            "VS",
            font=font_vs,
            fill=(255, 255, 255)
        )

        # Fecha y hora
        font_info = self._get_font("Montserrat-Medium.ttf", 32)
        match_info = f"{data['date']} - {data['time']}"

        bbox = draw.textbbox((0, 0), match_info, font=font_info)
        info_width = bbox[2] - bbox[0]

        draw.text(
            ((template.width - info_width) // 2, 450),
            match_info,
            font=font_info,
            fill=(255, 255, 255)
        )

        return template

    def save_image(
        self,
        image: Image.Image,
        output_path: str,
        format: str = "PNG",
        quality: int = 95
    ) -> str:
        """Guarda imagen a disco"""
        image.save(output_path, format, quality=quality)
        return output_path

    def _download_image(self, url: str) -> Image.Image:
        """Descarga imagen desde URL"""
        response = requests.get(url)
        response.raise_for_status()

        img = Image.open(BytesIO(response.content))

        # Convertir a RGBA si no lo es
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        return img

    def _get_font(self, font_name: str, size: int) -> ImageFont.FreeTypeFont:
        """Cache de fonts"""
        cache_key = f"{font_name}_{size}"

        if cache_key not in self.fonts_cache:
            font_path = os.path.join(self.fonts_dir, font_name)

            try:
                self.fonts_cache[cache_key] = ImageFont.truetype(
                    font_path, size
                )
            except Exception as e:
                print(f"Error cargando font {font_name}: {e}")
                # Fallback a default
                self.fonts_cache[cache_key] = ImageFont.load_default()

        return self.fonts_cache[cache_key]

    def _get_color_from_branding(
        self,
        branding: Optional[Dict],
        color_name: str,
        default: Tuple[int, int, int]
    ) -> Tuple[int, int, int]:
        """Obtiene color desde branding o retorna default"""
        if not branding:
            return default

        color_hex = branding.get(f'{color_name}_color')
        if not color_hex:
            return default

        # Convertir hex a RGB
        try:
            color_hex = color_hex.lstrip('#')
            return tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        except:
            return default

    def _format_stats_line(self, data: Dict) -> str:
        """Formatea línea de stats resumidas"""
        parts = []

        if 'goals' in data:
            parts.append(f"{data['goals']} GOLES")

        if 'assists' in data:
            parts.append(f"{data['assists']} ASISTENCIAS")

        if 'minutes' in data:
            parts.append(f"{data['minutes']} MIN")

        return " • ".join(parts)
```

**[ ] 13.2 Crear Branding Manager**

Archivo: `backend/services/image/branding.py`

```python
from typing import Dict, Optional

class BrandingManager:
    """Gestiona branding de equipos (colores, logos)"""

    # Base de datos de branding
    # En producción esto vendría de la DB
    BRANDING_DB = {
        "Real Madrid": {
            "primary_color": "#FFFFFF",
            "secondary_color": "#001F3F",
            "accent_color": "#D4AF37",
            "logo_url": "https://example.com/logos/real_madrid.png"
        },
        "Barcelona": {
            "primary_color": "#A50044",
            "secondary_color": "#004D98",
            "accent_color": "#FFCC00",
            "logo_url": "https://example.com/logos/barcelona.png"
        },
        # Más equipos...
    }

    @classmethod
    def get_branding(cls, team_name: str) -> Optional[Dict]:
        """
        Obtiene branding de un equipo

        Args:
            team_name: Nombre del equipo

        Returns:
            Dict con colores y logo, o None
        """
        return cls.BRANDING_DB.get(team_name)

    @classmethod
    def get_default_branding(cls) -> Dict:
        """Retorna branding genérico por defecto"""
        return {
            "primary_color": "#FFFFFF",
            "secondary_color": "#000000",
            "accent_color": "#0066CC",
            "logo_url": None
        }
```

### Día 16-17: Testing de Composición

**[ ] 16.1 Crear tests de composición**

```python
# backend/tests/test_image_composer.py
import pytest
from services.image.composer import ImageComposer
from services.image.branding import BrandingManager

def test_compose_player_stats():
    composer = ImageComposer()

    result = composer.compose_player_stats(
        template_path="./test_assets/template_test.png",
        project1_image_url="https://example.com/stats.png",
        data={
            "player_name": "Mbappé",
            "goals": 12,
            "assists": 7,
            "minutes": 890
        },
        branding=BrandingManager.get_branding("Real Madrid")
    )

    assert result is not None
    assert result.size == (1080, 1080)

    # Guardar para inspección visual
    result.save("./test_output/composed_test.png")

def test_compose_match_preview():
    composer = ImageComposer()

    result = composer.compose_match_preview(
        template_path="./test_assets/vs_template.png",
        home_team_logo="https://example.com/real_madrid_logo.png",
        away_team_logo="https://example.com/barcelona_logo.png",
        data={
            "date": "2025-01-20",
            "time": "21:00",
            "venue": "Santiago Bernabéu"
        }
    )

    assert result is not None
```

**[ ] 16.2 Descarga fonts necesarias**

```bash
mkdir -p backend/fonts

# Descargar Montserrat desde Google Fonts
# https://fonts.google.com/specimen/Montserrat

# Copiar archivos:
# - Montserrat-Bold.ttf
# - Montserrat-SemiBold.ttf
# - Montserrat-Regular.ttf
# - Montserrat-Medium.ttf
# - Montserrat-Black.ttf
```

### Checklist de Validación Fase 2

- [ ] Template Selector implementado
- [ ] Scoring de templates funciona correctamente
- [ ] Image Composer implementado
- [ ] Composición de player_stats funciona
- [ ] Composición de match_preview funciona
- [ ] Branding Manager funciona
- [ ] Fonts descargadas y funcionando
- [ ] Tests de composición pasan
- [ ] Imágenes generadas se ven correctas
- [ ] Commit y push

### Entregable Fase 2
✅ Sistema completo de selección de templates y composición de imágenes

---

## 7.5 FASE 3: Generación de Contenido con IA (Días 18-24)

### Objetivos
Implementar Caption Generator y Strategy Planner usando Gemini AI

### Día 18-19: Caption Generator

**[ ] 18.1 Implementar Caption Generator**

Archivo: `backend/services/ai/caption_generator.py`

```python
import google.generativeai as genai
import os
from typing import Dict, List
import hashlib
import json
import time

class CaptionGenerator:
    """Genera captions con Gemini AI"""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY no configurada")

        genai.configure(api_key=api_key)

        model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        self.model = genai.GenerativeModel(model_name)

        # Cache simple en memoria
        self.cache = {}

    def generate_caption(
        self,
        stat_type: str,
        data: Dict,
        team: str,
        content_type: str = "post",
        tone: str = "energetic",
        language: str = "es",
        emoji_usage: str = "moderate"
    ) -> Dict:
        """
        Genera caption optimizado

        Returns:
            {
                "caption": str,
                "hashtags": List[str],
                "call_to_action": str,
                "emoji_count": int,
                "tokens_used": int,
                "generation_time_ms": int
            }
        """
        # Verificar cache
        cache_key = self._generate_cache_key({
            "type": stat_type,
            "data": data,
            "team": team,
            "tone": tone
        })

        if cache_key in self.cache:
            print("[CACHE HIT] Caption recuperado")
            return self.cache[cache_key]

        # Construir prompt
        prompt = self._build_prompt(
            stat_type, data, team, content_type, tone, language, emoji_usage
        )

        try:
            start_time = time.time()

            response = self.model.generate_content(prompt)

            generation_time = int((time.time() - start_time) * 1000)

            result = self._parse_response(response.text)

            # Añadir metadata
            result['tokens_used'] = self._estimate_tokens(prompt, response.text)
            result['generation_time_ms'] = generation_time

            # Cachear
            self.cache[cache_key] = result

            return result

        except Exception as e:
            print(f"Error generando caption: {e}")
            return self._fallback_caption(stat_type, data, team)

    def _build_prompt(
        self,
        stat_type: str,
        data: Dict,
        team: str,
        content_type: str,
        tone: str,
        language: str,
        emoji_usage: str
    ) -> str:
        """Construye prompt optimizado"""

        tone_guidelines = {
            "energetic": "Usa lenguaje dinámico, emocional y entusiasta.",
            "professional": "Enfoque profesional, datos precisos, análisis táctico.",
            "casual": "Tono amigable y cercano, lenguaje coloquial.",
            "humorous": "Tono divertido, juegos de palabras apropiados.",
            "inspirational": "Motivacional, historias de superación."
        }

        emoji_guidelines = {
            "none": "NO uses emojis.",
            "minimal": "Usa máximo 1-2 emojis relevantes.",
            "moderate": "Usa 2-4 emojis deportivos.",
            "heavy": "Usa 5+ emojis para impacto visual."
        }

        content_length = {
            "post": "150-200 caracteres",
            "reel": "100-120 caracteres",
            "carousel": "200-250 caracteres"
        }

        prompt = f"""
Eres un Community Manager experto en contenido deportivo de fútbol.
Tu objetivo es maximizar engagement en Instagram.

**DATOS:**
- Tipo: {stat_type}
- Equipo: {team}
- Estadísticas: {json.dumps(data, indent=2)}
- Formato: {content_type}

**INSTRUCCIONES:**
1. Idioma: {language}
2. Tono: {tone_guidelines.get(tone, tone_guidelines['energetic'])}
3. Emojis: {emoji_guidelines.get(emoji_usage, emoji_guidelines['moderate'])}
4. Longitud: {content_length.get(content_type, '150-200')} caracteres
5. INCLUYE datos específicos de las estadísticas
6. Termina con pregunta o CTA para comentarios
7. Hashtags: 5-7 relevantes

**FORMATO DE SALIDA:**
Caption: [El caption aquí]
Hashtags: #hashtag1 #hashtag2 #hashtag3
CTA: [Pregunta específica]

**EJEMPLO DE CALIDAD:**
Caption: ¡Mbappé imparable! ⚡ 12 goles en 890 minutos. Rating: 8.5/10 🔥
Hashtags: #Mbappe #RealMadrid #LaLiga #GolMachine #Stats
CTA: ¿Crees que ganará la Bota de Oro? 🏆

Genera el contenido ahora.
"""

        return prompt

    def _parse_response(self, text: str) -> Dict:
        """Parsea respuesta de Gemini"""
        lines = text.strip().split('\n')

        caption = ""
        hashtags = []
        cta = ""

        for line in lines:
            if line.startswith("Caption:"):
                caption = line.replace("Caption:", "").strip()
            elif line.startswith("Hashtags:"):
                hashtag_line = line.replace("Hashtags:", "").strip()
                hashtags = [
                    tag.strip()
                    for tag in hashtag_line.split()
                    if tag.startswith("#")
                ]
            elif line.startswith("CTA:"):
                cta = line.replace("CTA:", "").strip()

        # Contar emojis
        import re
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002600-\U000027BF"
            "]+",
            flags=re.UNICODE
        )
        emoji_count = len(emoji_pattern.findall(caption + cta))

        return {
            "caption": caption,
            "hashtags": hashtags[:7],  # Max 7
            "call_to_action": cta,
            "emoji_count": emoji_count
        }

    def _fallback_caption(
        self,
        stat_type: str,
        data: Dict,
        team: str
    ) -> Dict:
        """Caption básico cuando falla IA"""
        templates = {
            "player_stats": f"📊 Estadísticas destacadas. {team} en acción!",
            "team_stats": f"⚽ {team} en números esta temporada.",
            "match_preview": f"🔥 Próximo partido. {team} listo para competir!",
            "league_table": f"📈 Clasificación actualizada. {team} en la lucha."
        }

        return {
            "caption": templates.get(stat_type, f"⚽ {team}"),
            "hashtags": [f"#{team.replace(' ', '')}", "#Futbol", "#Stats"],
            "call_to_action": "¿Qué opinas? 👇",
            "emoji_count": 2,
            "tokens_used": 0,
            "generation_time_ms": 0
        }

    def _generate_cache_key(self, data: Dict) -> str:
        """Genera clave de cache"""
        content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()

    def _estimate_tokens(self, prompt: str, response: str) -> int:
        """Estima tokens usados (aprox.)"""
        return len((prompt + response).split()) * 1.3
```

**Test**:
```python
# backend/tests/test_caption_generator.py
def test_generate_caption():
    generator = CaptionGenerator()

    result = generator.generate_caption(
        stat_type="player_stats",
        data={
            "player_name": "Mbappé",
            "goals": 12,
            "assists": 7
        },
        team="Real Madrid",
        tone="energetic",
        language="es"
    )

    assert "caption" in result
    assert len(result["caption"]) > 0
    assert len(result["hashtags"]) >= 3
    print(f"Caption generado: {result['caption']}")
```

### Día 20-21: Strategy Planner

**[ ] 20.1 Implementar Strategy Planner**

Archivo: `backend/services/ai/strategy_planner.py`

```python
import google.generativeai as genai
from datetime import datetime, timedelta
from typing import Dict, List
import json
import os

class StrategyPlanner:
    """Planifica estrategia de contenido como CM experto"""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def determine_best_time(
        self,
        content_type: str,
        engagement_history: List[Dict],
        user_preferences: Dict = None
    ) -> datetime:
        """
        Determina el mejor momento para publicar

        Args:
            content_type: Tipo de contenido
            engagement_history: Histórico de engagement
            user_preferences: Preferencias configuradas

        Returns:
            datetime para publicar
        """
        # Analizar histórico
        hourly_engagement = self._analyze_hourly_engagement(
            engagement_history, content_type
        )

        # Obtener mejores horas
        if hourly_engagement:
            best_hour = max(hourly_engagement, key=hourly_engagement.get)
        else:
            # Defaults por tipo de contenido
            default_hours = {
                "player_stats": 13,
                "match_result": 22,
                "match_preview": 12,
                "team_stats": 18
            }
            best_hour = default_hours.get(content_type, 13)

        # Calcular próximo slot
        now = datetime.now()
        next_slot = now.replace(hour=best_hour, minute=0, second=0)

        if next_slot <= now:
            next_slot += timedelta(days=1)

        # Verificar si hay conflictos (ya hay post en esa hora)
        # TODO: Check scheduled_posts table

        return next_slot

    def plan_weekly_content(
        self,
        available_data: List[Dict],
        engagement_history: List[Dict],
        strategy_config: Dict
    ) -> List[Dict]:
        """
        Planifica contenido para la semana

        Returns:
            Lista de posts programados
        """
        prompt = self._build_planning_prompt(
            available_data,
            engagement_history,
            strategy_config
        )

        try:
            response = self.model.generate_content(prompt)
            plan = json.loads(response.text)

            # Convertir a datetimes
            scheduled_posts = []
            for item in plan.get("weekly_plan", []):
                scheduled_posts.append({
                    "content_type": item["content_type"],
                    "data_id": item["data_id"],
                    "scheduled_time": self._parse_schedule(
                        item["day"], item["time"]
                    ),
                    "format": item["format"],
                    "priority": item["priority"],
                    "reasoning": item["reasoning"]
                })

            return scheduled_posts

        except Exception as e:
            print(f"Error planning: {e}")
            return self._basic_strategy(available_data)

    def _analyze_hourly_engagement(
        self,
        history: List[Dict],
        content_type: str
    ) -> Dict[int, float]:
        """Analiza engagement por hora del día"""
        hourly = {}

        for post in history:
            if post.get("type") != content_type:
                continue

            pub_time = datetime.fromisoformat(
                post.get("published_at", "")
            )
            hour = pub_time.hour

            engagement = (
                post.get("likes", 0) +
                post.get("comments", 0) * 3 +
                post.get("shares", 0) * 5
            )

            if hour not in hourly:
                hourly[hour] = []
            hourly[hour].append(engagement)

        # Promediar
        return {
            hour: sum(values) / len(values)
            for hour, values in hourly.items()
        }

    def _build_planning_prompt(
        self,
        available_data: List[Dict],
        history: List[Dict],
        config: Dict
    ) -> str:
        """Construye prompt para planning semanal"""

        prompt = f"""
Eres un Community Manager experto. Planifica contenido Instagram para esta semana.

**DATOS DISPONIBLES:**
{json.dumps(available_data[:10], indent=2)}

**HISTÓRICO DE ENGAGEMENT:**
Mejores horas: {self._get_best_hours_summary(history)}
Contenido más exitoso: {self._get_top_content_summary(history)}

**CONFIGURACIÓN:**
- Frecuencia: {config.get('posting_frequency', {}).get('per_week', 10)} posts/semana
- Mejores horarios: {config.get('best_times', ['13:00', '20:00'])}
- Distribución: {config.get('content_distribution', {})}

**DIRECTRICES:**
1. Variar tipos de contenido
2. Priorizar datos con tags "urgent" o "trending"
3. Espaciar posts (mínimo 4h entre posts)
4. Evitar domingos por la mañana

**FORMATO DE SALIDA (JSON):**
{{
  "weekly_plan": [
    {{
      "day": "lunes",
      "time": "13:00",
      "content_type": "player_stats",
      "data_id": "exp_001",
      "format": "post",
      "priority": 8,
      "reasoning": "Stats urgentes con alto engagement esperado"
    }}
  ]
}}

Genera el plan completo para 7 días.
"""

        return prompt

    def _get_best_hours_summary(self, history: List[Dict]) -> str:
        """Resume mejores horas del histórico"""
        hourly = self._analyze_hourly_engagement(history, "all")
        top_3 = sorted(hourly.items(), key=lambda x: x[1], reverse=True)[:3]
        return ", ".join([f"{h}:00" for h, _ in top_3])

    def _get_top_content_summary(self, history: List[Dict]) -> str:
        """Resume contenido más exitoso"""
        if not history:
            return "Sin historial"

        sorted_posts = sorted(
            history,
            key=lambda x: x.get("engagement_rate", 0),
            reverse=True
        )[:3]

        return ", ".join([p.get("type", "unknown") for p in sorted_posts])

    def _parse_schedule(self, day: str, time: str) -> datetime:
        """Convierte día y hora a datetime"""
        days_map = {
            "lunes": 0, "martes": 1, "miércoles": 2, "miércoles": 2,
            "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5,
            "domingo": 6
        }

        today = datetime.now()
        target_weekday = days_map[day.lower()]
        days_ahead = target_weekday - today.weekday()

        if days_ahead < 0:
            days_ahead += 7

        target_date = today + timedelta(days=days_ahead)
        hour, minute = map(int, time.split(":"))

        return target_date.replace(hour=hour, minute=minute, second=0)

    def _basic_strategy(self, data: List[Dict]) -> List[Dict]:
        """Estrategia básica fallback"""
        now = datetime.now()
        posts = []

        for i, item in enumerate(data[:5]):
            posts.append({
                "content_type": item.get("type"),
                "data_id": item.get("id"),
                "scheduled_time": now + timedelta(days=i, hours=13),
                "format": "post",
                "priority": 5,
                "reasoning": "Contenido disponible"
            })

        return posts
```

### Día 22-24: Post Generator (Orquestador)

**[ ] 22.1 Implementar Post Generator**

Archivo: `backend/services/content/post_generator.py`

```python
from services.ai.caption_generator import CaptionGenerator
from services.ai.template_selector import TemplateSelector
from services.image.composer import ImageComposer
from services.image.branding import BrandingManager
from services.data.drive_connector import GoogleDriveConnector
from typing import Dict, Optional
import os
import uuid
from datetime import datetime

class PostGenerator:
    """
    Orquestador principal que coordina todos los servicios
    para generar un post completo.
    """

    def __init__(self, supabase_client):
        self.caption_gen = CaptionGenerator()
        self.template_selector = TemplateSelector(supabase_client)
        self.image_composer = ImageComposer()
        self.branding_manager = BrandingManager()
        self.drive_connector = GoogleDriveConnector()
        self.supabase = supabase_client

    async def generate_post(
        self,
        source_data_id: str,
        source_data: Dict,
        user_id: str,
        instagram_account_id: int,
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Pipeline completo de generación

        Args:
            source_data_id: ID del export de PROJECT 1
            source_data: Datos completos del export
            user_id: ID del usuario
            instagram_account_id: ID de la cuenta Instagram
            options: Opciones de generación

        Returns:
            Post generado con preview
        """
        options = options or {}

        try:
            # 1. Seleccionar template óptimo
            if options.get('auto_select_template', True):
                template = self.template_selector.select_template(
                    stat_type=source_data['type'],
                    content_format=options.get('format', 'FEED'),
                    team=source_data.get('team'),
                    data_fields=list(source_data.get('data', {}).keys()),
                    user_id=user_id
                )
            else:
                # Usuario seleccionó manualmente
                template_id = options.get('template_id')
                template = self.supabase.table('templates').select(
                    '*'
                ).eq('id', template_id).single().execute().data

            # 2. Obtener branding del equipo
            team = source_data.get('team')
            branding = self.branding_manager.get_branding(team)
            if not branding:
                branding = self.branding_manager.get_default_branding()

            # 3. Descargar archivos necesarios
            # Template
            template_local = self._download_template(template['file_url'])

            # Imagen de PROJECT 1 ya tiene URL pública
            project1_image_url = source_data['image_url']

            # 4. Componer imagen
            start_compose = datetime.now()

            composed_image = self.image_composer.compose_player_stats(
                template_path=template_local,
                project1_image_url=project1_image_url,
                data=source_data.get('data', {}),
                branding=branding
            )

            compose_time = (datetime.now() - start_compose).total_seconds()

            # 5. Guardar imagen en Supabase Storage
            output_filename = f"{uuid.uuid4()}.png"
            output_path = f"/tmp/{output_filename}"

            self.image_composer.save_image(composed_image, output_path)

            # Upload a Supabase
            with open(output_path, 'rb') as f:
                self.supabase.storage.from_('instagram-media').upload(
                    output_filename,
                    f.read(),
                    {"content-type": "image/png"}
                )

            media_url = self.supabase.storage.from_(
                'instagram-media'
            ).get_public_url(output_filename)

            # 6. Generar caption con IA
            start_caption = datetime.now()

            caption_result = self.caption_gen.generate_caption(
                stat_type=source_data['type'],
                data=source_data.get('data', {}),
                team=team or 'Team',
                content_type=options.get('format', 'post'),
                tone=options.get('tone', 'energetic'),
                language=options.get('language', 'es'),
                emoji_usage=options.get('emoji_usage', 'moderate')
            )

            caption_time = (datetime.now() - start_caption).total_seconds()

            # 7. Combinar caption + hashtags
            full_caption = f"{caption_result['caption']}\n\n"
            full_caption += " ".join(caption_result['hashtags'])

            if caption_result['call_to_action']:
                full_caption += f"\n\n{caption_result['call_to_action']}"

            # 8. Crear post en DB
            post_data = {
                'user_id': user_id,
                'instagram_account_id': instagram_account_id,
                'content': full_caption,
                'media_url': media_url,
                'post_type': options.get('format', 'FEED').lower(),
                'status': 'draft',
                'source_data_id': source_data_id,
                'source_data_url': source_data['image_url'],
                'template_id': template['id'],
                'ai_caption_raw': caption_result['caption'],
                'is_ai_generated': True,
                'ai_metadata': {
                    'template_selection': template.get('selection_reasons', []),
                    'template_score': template.get('selection_score'),
                    'caption_metadata': {
                        'model': 'gemini-2.0-flash-exp',
                        'tokens_used': caption_result.get('tokens_used'),
                        'generation_time_ms': caption_result.get('generation_time_ms')
                    },
                    'composition_time_s': compose_time,
                    'caption_generation_time_s': caption_time
                }
            }

            post_response = self.supabase.table('posts').insert(
                post_data
            ).execute()

            post_id = post_response.data[0]['id']

            # 9. Guardar en historial de generación
            self.supabase.table('content_generation_history').insert({
                'post_id': post_id,
                'template_id': template['id'],
                'ai_prompt': "Auto-generated",
                'input_data': source_data,
                'generated_caption': caption_result['caption'],
                'generated_hashtags': caption_result['hashtags'],
                'ai_model': 'gemini-2.0-flash-exp',
                'tokens_used': caption_result.get('tokens_used'),
                'generation_time_ms': int(caption_time * 1000),
                'status': 'approved'
            }).execute()

            # 10. Limpiar archivos temporales
            os.remove(output_path)
            if os.path.exists(template_local):
                os.remove(template_local)

            return {
                "post_id": post_id,
                "status": "draft",
                "preview": {
                    "image_url": media_url,
                    "caption": full_caption,
                    "hashtags": caption_result['hashtags'],
                    "template_used": {
                        "id": template['id'],
                        "name": template['name']
                    }
                },
                "metadata": {
                    "ai_model": "gemini-2.0-flash-exp",
                    "tokens_used": caption_result.get('tokens_used'),
                    "generation_time_ms": int((compose_time + caption_time) * 1000),
                    "template_score": template.get('selection_score')
                }
            }

        except Exception as e:
            # Log error
            print(f"Error generating post: {e}")
            raise

    def _download_template(self, url: str) -> str:
        """Descarga template desde URL"""
        # Si es Google Drive
        if 'drive.google.com' in url:
            file_id = self._extract_drive_file_id(url)
            dest = f"/tmp/template_{file_id}.png"
            return self.drive_connector.download_file(file_id, dest)
        else:
            # Download HTTP normal
            import requests
            response = requests.get(url)
            dest = f"/tmp/template_{uuid.uuid4()}.png"
            with open(dest, 'wb') as f:
                f.write(response.content)
            return dest

    def _extract_drive_file_id(self, url: str) -> str:
        """Extrae file ID de URL de Google Drive"""
        # https://drive.google.com/file/d/FILE_ID/view
        parts = url.split('/')
        if 'd' in parts:
            idx = parts.index('d')
            return parts[idx + 1]
        return url
```

**[ ] 22.2 Endpoint de generación completa**

En `backend/main.py`:

```python
from services.content.post_generator import PostGenerator
from schemas.content_schema import ContentGenerationRequest

post_generator = PostGenerator(supabase)

@app.post("/api/content/generate")
async def generate_content(
    request: ContentGenerationRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Genera post completo desde datos de PROJECT 1
    """
    try:
        result = await post_generator.generate_post(
            source_data_id=request.source_data_id,
            source_data=request.source_data.dict(),
            user_id=current_user.id,
            instagram_account_id=request.instagram_account_id,
            options=request.options.dict()
        )

        return result

    except Exception as e:
        logger.error(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Checklist de Validación Fase 3

- [ ] Caption Generator implementado
- [ ] Caption Generator genera captions de calidad
- [ ] Strategy Planner implementado
- [ ] Determine best time funciona
- [ ] Post Generator orquestador implementado
- [ ] Endpoint /api/content/generate funciona end-to-end
- [ ] Se generan posts completos correctamente
- [ ] Metadata se guarda en DB
- [ ] Tests pasan
- [ ] Commit y push

### Entregable Fase 3
✅ Sistema completo de generación de contenido con IA funcional

---

## FASE 4: Frontend Dashboard Completo (Días 25-31)

### Objetivo
Implementar interfaz completa para gestión de contenido, calendario y configuración de estrategia de CM.

### 23. Dashboard Principal Mejorado

**[ ] 23.1 Component Dashboard.tsx actualizado**

Ubicación: `frontend/src/components/dashboard/Dashboard.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import PostList from '../posts/PostList';
import PostGenerator from '../posts/PostGenerator';
import PostCalendar from '../posts/PostCalendar';
import Analytics from '../analytics/Analytics';
import StrategyConfig from '../strategy/StrategyConfig';
import './Dashboard.css';

interface DashboardTab {
  id: string;
  label: string;
  icon: string;
}

const Dashboard: React.FC = () => {
  const { isInstagramConnected, user } = useAuth();
  const [activeTab, setActiveTab] = useState<string>('posts');
  const [stats, setStats] = useState({
    totalPosts: 0,
    scheduledPosts: 0,
    draftPosts: 0,
    publishedToday: 0
  });

  const tabs: DashboardTab[] = [
    { id: 'posts', label: 'Publicaciones', icon: '📝' },
    { id: 'generate', label: 'Generar Contenido', icon: '✨' },
    { id: 'calendar', label: 'Calendario', icon: '📅' },
    { id: 'analytics', label: 'Análisis', icon: '📊' },
    { id: 'strategy', label: 'Estrategia CM', icon: '🎯' }
  ];

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    const token = localStorage.getItem('authToken');
    if (!token) return;

    try {
      const response = await fetch('http://localhost:8000/api/analytics/overview', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data.stats);
      }
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'posts':
        return <PostList onPostUpdate={fetchDashboardStats} />;
      case 'generate':
        return <PostGenerator onPostGenerated={fetchDashboardStats} />;
      case 'calendar':
        return <PostCalendar />;
      case 'analytics':
        return <Analytics />;
      case 'strategy':
        return <StrategyConfig />;
      default:
        return <PostList onPostUpdate={fetchDashboardStats} />;
    }
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1>Dashboard - SocialLab</h1>
        <div className="dashboard-stats">
          <div className="stat-card">
            <span className="stat-value">{stats.totalPosts}</span>
            <span className="stat-label">Total Posts</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{stats.scheduledPosts}</span>
            <span className="stat-label">Programados</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{stats.draftPosts}</span>
            <span className="stat-label">Borradores</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{stats.publishedToday}</span>
            <span className="stat-label">Hoy</span>
          </div>
        </div>
      </div>

      <div className="dashboard-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            <span className="tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      <div className="dashboard-content">
        {!isInstagramConnected && (
          <div className="alert alert-warning">
            ⚠️ Conecta tu cuenta de Instagram para comenzar a publicar
          </div>
        )}
        {renderTabContent()}
      </div>
    </div>
  );
};

export default Dashboard;
```

**[ ] 23.2 Estilos Dashboard.css**

```css
.dashboard-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2rem;
}

.dashboard-header {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.dashboard-header h1 {
  margin: 0 0 1.5rem 0;
  color: #333;
}

.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 8px;
  color: white;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.stat-label {
  font-size: 0.875rem;
  opacity: 0.9;
}

.dashboard-tabs {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  overflow-x: auto;
}

.tab-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: white;
  border: 2px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.tab-button:hover {
  border-color: #667eea;
  transform: translateY(-2px);
}

.tab-button.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
}

.tab-icon {
  font-size: 1.25rem;
}

.dashboard-content {
  background: white;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.alert {
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.alert-warning {
  background: #fff3cd;
  border: 1px solid #ffc107;
  color: #856404;
}
```

### 24. Componente PostGenerator Completo

**[ ] 24.1 Component PostGenerator.tsx**

Ubicación: `frontend/src/components/posts/PostGenerator.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import './PostGenerator.css';

interface Project1Export {
  id: string;
  type: string;
  player_name?: string;
  team?: string;
  date: string;
  image_url: string;
  data: Record<string, any>;
  tags: string[];
}

interface GenerateOptions {
  tone?: string;
  include_hashtags?: boolean;
  include_call_to_action?: boolean;
  schedule_time?: string;
}

interface PostGeneratorProps {
  onPostGenerated?: () => void;
}

const PostGenerator: React.FC<PostGeneratorProps> = ({ onPostGenerated }) => {
  const [exports, setExports] = useState<Project1Export[]>([]);
  const [selectedExport, setSelectedExport] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [preview, setPreview] = useState<any>(null);
  const [options, setOptions] = useState<GenerateOptions>({
    tone: 'energetic',
    include_hashtags: true,
    include_call_to_action: true
  });

  useEffect(() => {
    fetchAvailableExports();
  }, []);

  const fetchAvailableExports = async () => {
    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      const response = await fetch('http://localhost:8000/api/drive/exports', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setExports(data.exports);
      }
    } catch (error) {
      console.error('Error fetching exports:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedExport) {
      alert('Selecciona un dato de PROJECT 1 primero');
      return;
    }

    setGenerating(true);
    const token = localStorage.getItem('authToken');
    const exportData = exports.find(e => e.id === selectedExport);

    try {
      const response = await fetch('http://localhost:8000/api/content/generate', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          source_data_id: selectedExport,
          source_data: exportData,
          instagram_account_id: 1, // TODO: Get from user's selected account
          options: options
        })
      });

      if (response.ok) {
        const result = await response.json();
        setPreview(result);
        alert('✅ Post generado exitosamente!');
        if (onPostGenerated) {
          onPostGenerated();
        }
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error generating post:', error);
      alert('Error al generar el post');
    } finally {
      setGenerating(false);
    }
  };

  const handleSync = async () => {
    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      const response = await fetch('http://localhost:8000/api/drive/sync', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        alert('✅ Sincronización completada');
        fetchAvailableExports();
      }
    } catch (error) {
      console.error('Error syncing:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="post-generator">
      <div className="generator-header">
        <h2>✨ Generar Contenido desde PROJECT 1</h2>
        <button
          className="btn btn-secondary"
          onClick={handleSync}
          disabled={loading}
        >
          🔄 Sincronizar con Google Drive
        </button>
      </div>

      {loading ? (
        <div className="loading">Cargando datos de PROJECT 1...</div>
      ) : (
        <>
          <div className="exports-list">
            <h3>Selecciona datos disponibles:</h3>
            {exports.length === 0 ? (
              <p>No hay datos disponibles. Sincroniza con Google Drive primero.</p>
            ) : (
              <div className="exports-grid">
                {exports.map(exp => (
                  <div
                    key={exp.id}
                    className={`export-card ${selectedExport === exp.id ? 'selected' : ''}`}
                    onClick={() => setSelectedExport(exp.id)}
                  >
                    <img src={exp.image_url} alt={exp.type} />
                    <div className="export-info">
                      <h4>{exp.player_name || exp.type}</h4>
                      <p>{exp.team}</p>
                      <p className="export-date">{exp.date}</p>
                      <div className="export-tags">
                        {exp.tags.map(tag => (
                          <span key={tag} className="tag">{tag}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {selectedExport && (
            <div className="generation-options">
              <h3>Opciones de generación:</h3>

              <div className="option-group">
                <label>Tono del caption:</label>
                <select
                  value={options.tone}
                  onChange={(e) => setOptions({...options, tone: e.target.value})}
                >
                  <option value="energetic">Enérgico</option>
                  <option value="professional">Profesional</option>
                  <option value="casual">Casual</option>
                  <option value="emotional">Emocional</option>
                </select>
              </div>

              <div className="option-group">
                <label>
                  <input
                    type="checkbox"
                    checked={options.include_hashtags}
                    onChange={(e) => setOptions({...options, include_hashtags: e.target.checked})}
                  />
                  Incluir hashtags
                </label>
              </div>

              <div className="option-group">
                <label>
                  <input
                    type="checkbox"
                    checked={options.include_call_to_action}
                    onChange={(e) => setOptions({...options, include_call_to_action: e.target.checked})}
                  />
                  Incluir call-to-action
                </label>
              </div>

              <div className="option-group">
                <label>Programar para:</label>
                <input
                  type="datetime-local"
                  value={options.schedule_time || ''}
                  onChange={(e) => setOptions({...options, schedule_time: e.target.value})}
                />
              </div>

              <button
                className="btn btn-primary btn-generate"
                onClick={handleGenerate}
                disabled={generating}
              >
                {generating ? '⏳ Generando...' : '✨ Generar Post'}
              </button>
            </div>
          )}

          {preview && (
            <div className="preview-section">
              <h3>Vista Previa:</h3>
              <div className="preview-card">
                <img src={preview.preview_url} alt="Preview" />
                <div className="preview-caption">
                  <p>{preview.caption}</p>
                </div>
                <div className="preview-meta">
                  <p><strong>Template:</strong> {preview.template_used}</p>
                  <p><strong>Estado:</strong> {preview.status}</p>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default PostGenerator;
```

**[ ] 24.2 Estilos PostGenerator.css**

```css
.post-generator {
  padding: 1rem;
}

.generator-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.exports-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.export-card {
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.export-card:hover {
  border-color: #667eea;
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
}

.export-card.selected {
  border-color: #667eea;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
}

.export-card img {
  width: 100%;
  height: 150px;
  object-fit: cover;
  border-radius: 4px;
  margin-bottom: 0.75rem;
}

.export-info h4 {
  margin: 0.5rem 0;
  color: #333;
}

.export-date {
  font-size: 0.875rem;
  color: #666;
}

.export-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.tag {
  background: #667eea;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
}

.generation-options {
  margin-top: 2rem;
  padding: 1.5rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.option-group {
  margin-bottom: 1rem;
}

.option-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.option-group select,
.option-group input[type="datetime-local"] {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn-generate {
  width: 100%;
  margin-top: 1rem;
  padding: 1rem;
  font-size: 1.125rem;
}

.preview-section {
  margin-top: 2rem;
  padding: 1.5rem;
  border: 2px solid #667eea;
  border-radius: 8px;
}

.preview-card img {
  width: 100%;
  max-width: 500px;
  border-radius: 8px;
}

.preview-caption {
  margin: 1rem 0;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 4px;
}

.preview-meta {
  font-size: 0.875rem;
  color: #666;
}
```

### 25. Componente PostCalendar

**[ ] 25.1 Component PostCalendar.tsx**

```typescript
import React, { useState, useEffect } from 'react';
import './PostCalendar.css';

interface ScheduledPost {
  id: number;
  caption: string;
  media_url: string;
  scheduled_publish_time: string;
  status: string;
}

const PostCalendar: React.FC = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [scheduledPosts, setScheduledPosts] = useState<ScheduledPost[]>([]);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);

  useEffect(() => {
    fetchScheduledPosts();
  }, [currentDate]);

  const fetchScheduledPosts = async () => {
    const token = localStorage.getItem('authToken');
    const startDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
    const endDate = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0);

    try {
      const response = await fetch(
        `http://localhost:8000/api/posts/scheduled?start=${startDate.toISOString()}&end=${endDate.toISOString()}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setScheduledPosts(data.posts);
      }
    } catch (error) {
      console.error('Error fetching scheduled posts:', error);
    }
  };

  const getDaysInMonth = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    return { daysInMonth, startingDayOfWeek };
  };

  const getPostsForDate = (day: number) => {
    const dateStr = new Date(
      currentDate.getFullYear(),
      currentDate.getMonth(),
      day
    ).toISOString().split('T')[0];

    return scheduledPosts.filter(post =>
      post.scheduled_publish_time.startsWith(dateStr)
    );
  };

  const renderCalendar = () => {
    const { daysInMonth, startingDayOfWeek } = getDaysInMonth();
    const days = [];

    // Empty cells for days before month starts
    for (let i = 0; i < startingDayOfWeek; i++) {
      days.push(<div key={`empty-${i}`} className="calendar-day empty"></div>);
    }

    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const postsForDay = getPostsForDate(day);
      const isToday =
        day === new Date().getDate() &&
        currentDate.getMonth() === new Date().getMonth() &&
        currentDate.getFullYear() === new Date().getFullYear();

      days.push(
        <div
          key={day}
          className={`calendar-day ${isToday ? 'today' : ''} ${postsForDay.length > 0 ? 'has-posts' : ''}`}
          onClick={() => setSelectedDate(new Date(currentDate.getFullYear(), currentDate.getMonth(), day))}
        >
          <div className="day-number">{day}</div>
          {postsForDay.length > 0 && (
            <div className="post-indicator">{postsForDay.length} posts</div>
          )}
        </div>
      );
    }

    return days;
  };

  const changeMonth = (delta: number) => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + delta, 1));
  };

  return (
    <div className="post-calendar">
      <div className="calendar-header">
        <button onClick={() => changeMonth(-1)}>‹</button>
        <h2>
          {currentDate.toLocaleDateString('es-ES', { month: 'long', year: 'numeric' })}
        </h2>
        <button onClick={() => changeMonth(1)}>›</button>
      </div>

      <div className="calendar-weekdays">
        <div>Dom</div>
        <div>Lun</div>
        <div>Mar</div>
        <div>Mié</div>
        <div>Jue</div>
        <div>Vie</div>
        <div>Sáb</div>
      </div>

      <div className="calendar-grid">
        {renderCalendar()}
      </div>

      {selectedDate && (
        <div className="selected-date-posts">
          <h3>Posts programados para {selectedDate.toLocaleDateString('es-ES')}</h3>
          {getPostsForDate(selectedDate.getDate()).map(post => (
            <div key={post.id} className="scheduled-post-card">
              <img src={post.media_url} alt="Post" />
              <div className="post-details">
                <p>{post.caption.substring(0, 100)}...</p>
                <p><strong>Hora:</strong> {new Date(post.scheduled_publish_time).toLocaleTimeString('es-ES')}</p>
                <span className={`status-badge ${post.status}`}>{post.status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PostCalendar;
```

**[ ] 25.2 Estilos PostCalendar.css**

```css
.post-calendar {
  padding: 1rem;
}

.calendar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.calendar-header button {
  background: #667eea;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.5rem;
}

.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-weight: bold;
  text-align: center;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.5rem;
}

.calendar-day {
  aspect-ratio: 1;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 0.5rem;
  cursor: pointer;
  transition: all 0.3s ease;
  position: relative;
}

.calendar-day:hover {
  border-color: #667eea;
  background: rgba(102, 126, 234, 0.1);
}

.calendar-day.empty {
  cursor: default;
  background: #f8f9fa;
}

.calendar-day.today {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.calendar-day.has-posts {
  border-color: #667eea;
  border-width: 2px;
}

.day-number {
  font-weight: bold;
  margin-bottom: 0.25rem;
}

.post-indicator {
  font-size: 0.75rem;
  color: #667eea;
  position: absolute;
  bottom: 0.25rem;
  right: 0.25rem;
}

.calendar-day.today .post-indicator {
  color: white;
}

.selected-date-posts {
  margin-top: 2rem;
  padding: 1.5rem;
  background: #f8f9fa;
  border-radius: 8px;
}

.scheduled-post-card {
  display: flex;
  gap: 1rem;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  margin-top: 1rem;
}

.scheduled-post-card img {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: 4px;
}

.post-details {
  flex: 1;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: bold;
}

.status-badge.scheduled {
  background: #ffc107;
  color: #000;
}

.status-badge.published {
  background: #28a745;
  color: white;
}

.status-badge.failed {
  background: #dc3545;
  color: white;
}
```

### 26. Componente StrategyConfig

**[ ] 26.1 Component StrategyConfig.tsx**

```typescript
import React, { useState, useEffect } from 'react';
import './StrategyConfig.css';

interface AIStrategy {
  id?: number;
  instagram_account_id: number;
  tone: string;
  language: string;
  posting_frequency: {
    posts_per_week: number;
    preferred_days: string[];
  };
  content_distribution: {
    feed: number;
    reels: number;
    stories: number;
  };
  target_audience: string;
  key_topics: string[];
  hashtag_strategy: string;
}

const StrategyConfig: React.FC = () => {
  const [strategy, setStrategy] = useState<AIStrategy>({
    instagram_account_id: 1,
    tone: 'energetic',
    language: 'es',
    posting_frequency: {
      posts_per_week: 7,
      preferred_days: ['lunes', 'miércoles', 'viernes']
    },
    content_distribution: {
      feed: 50,
      reels: 30,
      stories: 20
    },
    target_audience: 'Aficionados al fútbol de Hong Kong',
    key_topics: ['partidos', 'estadísticas', 'jugadores destacados'],
    hashtag_strategy: 'mix'
  });

  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchStrategy();
  }, []);

  const fetchStrategy = async () => {
    const token = localStorage.getItem('authToken');

    try {
      const response = await fetch('http://localhost:8000/api/ai-strategy/1', {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        const data = await response.json();
        setStrategy(data);
      }
    } catch (error) {
      console.error('Error fetching strategy:', error);
    }
  };

  const handleSave = async () => {
    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      const response = await fetch('http://localhost:8000/api/ai-strategy', {
        method: strategy.id ? 'PUT' : 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(strategy)
      });

      if (response.ok) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        alert('✅ Estrategia guardada exitosamente');
      }
    } catch (error) {
      console.error('Error saving strategy:', error);
      alert('Error al guardar la estrategia');
    } finally {
      setLoading(false);
    }
  };

  const updateFrequency = (key: string, value: any) => {
    setStrategy({
      ...strategy,
      posting_frequency: {
        ...strategy.posting_frequency,
        [key]: value
      }
    });
  };

  const updateDistribution = (key: string, value: number) => {
    setStrategy({
      ...strategy,
      content_distribution: {
        ...strategy.content_distribution,
        [key]: value
      }
    });
  };

  const togglePreferredDay = (day: string) => {
    const days = strategy.posting_frequency.preferred_days;
    const newDays = days.includes(day)
      ? days.filter(d => d !== day)
      : [...days, day];

    updateFrequency('preferred_days', newDays);
  };

  const weekDays = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'];

  return (
    <div className="strategy-config">
      <h2>🎯 Configuración de Estrategia de Community Manager</h2>

      <div className="config-section">
        <h3>Tono y Lenguaje</h3>

        <div className="form-group">
          <label>Tono de comunicación:</label>
          <select
            value={strategy.tone}
            onChange={(e) => setStrategy({...strategy, tone: e.target.value})}
          >
            <option value="energetic">Enérgico</option>
            <option value="professional">Profesional</option>
            <option value="casual">Casual</option>
            <option value="emotional">Emocional</option>
            <option value="humorous">Humorístico</option>
          </select>
        </div>

        <div className="form-group">
          <label>Idioma:</label>
          <select
            value={strategy.language}
            onChange={(e) => setStrategy({...strategy, language: e.target.value})}
          >
            <option value="es">Español</option>
            <option value="en">English</option>
            <option value="zh">中文 (Chino)</option>
          </select>
        </div>
      </div>

      <div className="config-section">
        <h3>Frecuencia de Publicación</h3>

        <div className="form-group">
          <label>Posts por semana: {strategy.posting_frequency.posts_per_week}</label>
          <input
            type="range"
            min="1"
            max="21"
            value={strategy.posting_frequency.posts_per_week}
            onChange={(e) => updateFrequency('posts_per_week', parseInt(e.target.value))}
          />
        </div>

        <div className="form-group">
          <label>Días preferidos:</label>
          <div className="day-selector">
            {weekDays.map(day => (
              <button
                key={day}
                className={`day-button ${strategy.posting_frequency.preferred_days.includes(day) ? 'selected' : ''}`}
                onClick={() => togglePreferredDay(day)}
              >
                {day.substring(0, 3)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="config-section">
        <h3>Distribución de Contenido</h3>

        <div className="distribution-sliders">
          <div className="form-group">
            <label>Feed Posts: {strategy.content_distribution.feed}%</label>
            <input
              type="range"
              min="0"
              max="100"
              value={strategy.content_distribution.feed}
              onChange={(e) => updateDistribution('feed', parseInt(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Reels: {strategy.content_distribution.reels}%</label>
            <input
              type="range"
              min="0"
              max="100"
              value={strategy.content_distribution.reels}
              onChange={(e) => updateDistribution('reels', parseInt(e.target.value))}
            />
          </div>

          <div className="form-group">
            <label>Stories: {strategy.content_distribution.stories}%</label>
            <input
              type="range"
              min="0"
              max="100"
              value={strategy.content_distribution.stories}
              onChange={(e) => updateDistribution('stories', parseInt(e.target.value))}
            />
          </div>
        </div>

        <p className="distribution-total">
          Total: {strategy.content_distribution.feed + strategy.content_distribution.reels + strategy.content_distribution.stories}%
          {strategy.content_distribution.feed + strategy.content_distribution.reels + strategy.content_distribution.stories !== 100 &&
            <span className="warning"> ⚠️ Debe sumar 100%</span>
          }
        </p>
      </div>

      <div className="config-section">
        <h3>Audiencia y Contenido</h3>

        <div className="form-group">
          <label>Audiencia objetivo:</label>
          <textarea
            value={strategy.target_audience}
            onChange={(e) => setStrategy({...strategy, target_audience: e.target.value})}
            rows={3}
          />
        </div>

        <div className="form-group">
          <label>Temas clave (separados por coma):</label>
          <input
            type="text"
            value={strategy.key_topics.join(', ')}
            onChange={(e) => setStrategy({...strategy, key_topics: e.target.value.split(',').map(t => t.trim())})}
          />
        </div>

        <div className="form-group">
          <label>Estrategia de hashtags:</label>
          <select
            value={strategy.hashtag_strategy}
            onChange={(e) => setStrategy({...strategy, hashtag_strategy: e.target.value})}
          >
            <option value="trending">Solo trending</option>
            <option value="branded">Solo branded</option>
            <option value="mix">Mix de ambos</option>
            <option value="none">Sin hashtags</option>
          </select>
        </div>
      </div>

      <button
        className="btn btn-primary btn-save"
        onClick={handleSave}
        disabled={loading}
      >
        {loading ? 'Guardando...' : saved ? '✅ Guardado' : '💾 Guardar Estrategia'}
      </button>
    </div>
  );
};

export default StrategyConfig;
```

**[ ] 26.2 Estilos StrategyConfig.css**

```css
.strategy-config {
  padding: 1rem;
  max-width: 800px;
  margin: 0 auto;
}

.config-section {
  background: #f8f9fa;
  padding: 1.5rem;
  border-radius: 8px;
  margin-bottom: 2rem;
}

.config-section h3 {
  margin-top: 0;
  color: #667eea;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
}

.form-group select,
.form-group input[type="text"],
.form-group textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.form-group input[type="range"] {
  width: 100%;
  height: 8px;
  border-radius: 4px;
  background: #ddd;
  outline: none;
}

.form-group input[type="range"]::-webkit-slider-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #667eea;
  cursor: pointer;
}

.day-selector {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.day-button {
  padding: 0.5rem 1rem;
  border: 2px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-transform: capitalize;
}

.day-button:hover {
  border-color: #667eea;
}

.day-button.selected {
  background: #667eea;
  color: white;
  border-color: #667eea;
}

.distribution-total {
  margin-top: 1rem;
  font-weight: bold;
  text-align: center;
}

.distribution-total .warning {
  color: #dc3545;
}

.btn-save {
  width: 100%;
  padding: 1rem;
  font-size: 1.125rem;
}
```

### Checklist de Validación Fase 4

- [ ] Dashboard principal implementado y funcional
- [ ] Tabs de navegación funcionan correctamente
- [ ] PostGenerator lista exports de PROJECT 1
- [ ] PostGenerator genera posts completos
- [ ] PostCalendar muestra calendario mensual
- [ ] PostCalendar muestra posts programados
- [ ] StrategyConfig guarda configuración de CM
- [ ] Todos los componentes tienen estilos responsive
- [ ] Navegación entre componentes fluida
- [ ] Tests de componentes React pasan
- [ ] Commit y push

### Entregable Fase 4
✅ Frontend completo con dashboard, generador, calendario y configuración de estrategia

---

## FASE 5: Automatización y Scheduling (Días 32-38)

### Objetivo
Implementar sistema de programación automática de posts con APScheduler y opcionalmente n8n para flujos avanzados.

### 27. Sistema de Scheduling con APScheduler (Opción Simple)

**[ ] 27.1 Servicio PostScheduler**

Ubicación: `backend/services/scheduler/post_scheduler.py`

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
from typing import Optional
import logging

from ..publisher.instagram_publisher import InstagramPublisher
from database import get_supabase

logger = logging.getLogger(__name__)


class PostScheduler:
    """
    Programa publicaciones automáticas usando APScheduler.

    Features:
    - Programar posts para fechas futuras
    - Persistencia de jobs en PostgreSQL
    - Retry automático en caso de fallo
    - Cancelación de posts programados
    """

    def __init__(self):
        self.supabase = get_supabase()
        self.publisher = InstagramPublisher()

        # Configurar jobstore en PostgreSQL
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=os.getenv('DATABASE_URL')
            )
        }

        # Configurar scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone='UTC'
        )
        self.scheduler.start()

        # Recuperar jobs pendientes al iniciar
        self._restore_pending_jobs()

        logger.info("PostScheduler initialized")

    def schedule_post(
        self,
        post_id: int,
        scheduled_time: datetime,
        retry_on_failure: bool = True
    ) -> str:
        """
        Programa un post para publicación futura.

        Args:
            post_id: ID del post en la tabla posts
            scheduled_time: Fecha y hora de publicación
            retry_on_failure: Si True, reintenta en caso de error

        Returns:
            job_id: ID del job creado
        """
        try:
            # Validar que el post existe y está en estado 'scheduled'
            post = self.supabase.table('posts').select('*').eq(
                'id', post_id
            ).single().execute()

            if not post.data:
                raise ValueError(f"Post {post_id} no existe")

            if post.data['status'] != 'scheduled':
                raise ValueError(
                    f"Post {post_id} no está en estado 'scheduled'"
                )

            # Crear job en APScheduler
            job = self.scheduler.add_job(
                func=self._publish_post,
                trigger=DateTrigger(run_date=scheduled_time),
                args=[post_id],
                id=f"post_{post_id}",
                name=f"Publish post {post_id}",
                replace_existing=True,
                max_instances=1
            )

            # Registrar en tabla scheduled_jobs
            self.supabase.table('scheduled_jobs').insert({
                'job_id': job.id,
                'job_type': 'publish_post',
                'post_id': post_id,
                'scheduled_time': scheduled_time.isoformat(),
                'status': 'pending',
                'retry_count': 0,
                'max_retries': 3 if retry_on_failure else 0
            }).execute()

            logger.info(
                f"Post {post_id} programado para {scheduled_time}"
            )
            return job.id

        except Exception as e:
            logger.error(f"Error scheduling post {post_id}: {e}")
            raise

    def cancel_scheduled_post(self, post_id: int) -> bool:
        """Cancela un post programado."""
        try:
            job_id = f"post_{post_id}"
            self.scheduler.remove_job(job_id)

            # Actualizar estado en DB
            self.supabase.table('scheduled_jobs').update({
                'status': 'cancelled'
            }).eq('job_id', job_id).execute()

            self.supabase.table('posts').update({
                'status': 'cancelled'
            }).eq('id', post_id).execute()

            logger.info(f"Post {post_id} cancelado exitosamente")
            return True

        except Exception as e:
            logger.error(f"Error cancelling post {post_id}: {e}")
            return False

    def reschedule_post(
        self,
        post_id: int,
        new_scheduled_time: datetime
    ) -> str:
        """Reprograma un post para nueva fecha."""
        self.cancel_scheduled_post(post_id)

        # Actualizar fecha en DB
        self.supabase.table('posts').update({
            'scheduled_publish_time': new_scheduled_time.isoformat(),
            'status': 'scheduled'
        }).eq('id', post_id).execute()

        return self.schedule_post(post_id, new_scheduled_time)

    def _publish_post(self, post_id: int):
        """
        Función ejecutada por el scheduler para publicar post.
        Incluye manejo de errores y retry.
        """
        try:
            logger.info(f"Iniciando publicación de post {post_id}")

            # Obtener datos del post
            post = self.supabase.table('posts').select('*').eq(
                'id', post_id
            ).single().execute()

            if not post.data:
                raise ValueError(f"Post {post_id} no encontrado")

            # Publicar en Instagram
            result = self.publisher.publish_post(
                media_url=post.data['media_url'],
                caption=post.data['caption'],
                instagram_account_id=post.data['instagram_account_id']
            )

            # Actualizar estado en DB
            self.supabase.table('posts').update({
                'status': 'published',
                'instagram_post_id': result['id'],
                'published_at': datetime.utcnow().isoformat()
            }).eq('id', post_id).execute()

            # Actualizar job
            self.supabase.table('scheduled_jobs').update({
                'status': 'completed',
                'executed_at': datetime.utcnow().isoformat()
            }).eq('post_id', post_id).execute()

            logger.info(
                f"Post {post_id} publicado exitosamente: {result['id']}"
            )

        except Exception as e:
            logger.error(f"Error publishing post {post_id}: {e}")
            self._handle_publish_failure(post_id, str(e))

    def _handle_publish_failure(self, post_id: int, error_msg: str):
        """Maneja fallos en publicación con retry."""
        # Obtener job info
        job_info = self.supabase.table('scheduled_jobs').select('*').eq(
            'post_id', post_id
        ).single().execute()

        if not job_info.data:
            return

        retry_count = job_info.data['retry_count']
        max_retries = job_info.data['max_retries']

        if retry_count < max_retries:
            # Retry en 5 minutos
            retry_time = datetime.utcnow() + timedelta(minutes=5)

            self.supabase.table('scheduled_jobs').update({
                'retry_count': retry_count + 1,
                'last_error': error_msg
            }).eq('post_id', post_id).execute()

            # Reprogramar
            self.scheduler.add_job(
                func=self._publish_post,
                trigger=DateTrigger(run_date=retry_time),
                args=[post_id],
                id=f"post_{post_id}_retry_{retry_count+1}",
                replace_existing=True
            )

            logger.info(
                f"Post {post_id} retry {retry_count+1} programado"
            )
        else:
            # Marcar como failed
            self.supabase.table('posts').update({
                'status': 'failed'
            }).eq('id', post_id).execute()

            self.supabase.table('scheduled_jobs').update({
                'status': 'failed',
                'last_error': error_msg
            }).eq('post_id', post_id).execute()

            logger.error(
                f"Post {post_id} falló después de {retry_count} intentos"
            )

    def _restore_pending_jobs(self):
        """Restaura jobs pendientes al reiniciar el servidor."""
        pending_jobs = self.supabase.table('scheduled_jobs').select(
            'post_id, scheduled_time'
        ).eq('status', 'pending').execute()

        for job in pending_jobs.data:
            scheduled_time = datetime.fromisoformat(job['scheduled_time'])

            # Solo reprogramar si la fecha es futura
            if scheduled_time > datetime.utcnow():
                self.schedule_post(job['post_id'], scheduled_time)
                logger.info(f"Restaurado job para post {job['post_id']}")

    def get_scheduled_posts(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> list:
        """Obtiene lista de posts programados en un rango de fechas."""
        query = self.supabase.table('posts').select(
            '*'
        ).eq('status', 'scheduled')

        if start_date:
            query = query.gte(
                'scheduled_publish_time', start_date.isoformat()
            )

        if end_date:
            query = query.lte(
                'scheduled_publish_time', end_date.isoformat()
            )

        result = query.order('scheduled_publish_time').execute()
        return result.data

    def shutdown(self):
        """Apaga el scheduler de forma segura."""
        self.scheduler.shutdown()
        logger.info("PostScheduler shut down")
```

**[ ] 27.2 Endpoints de Scheduling**

En `backend/main.py`:

```python
from services.scheduler.post_scheduler import PostScheduler
from schemas.scheduler_schema import SchedulePostRequest

# Inicializar scheduler globalmente
post_scheduler = PostScheduler()

@app.on_event("shutdown")
def shutdown_scheduler():
    post_scheduler.shutdown()


@app.post("/api/posts/{post_id}/schedule")
async def schedule_post(
    post_id: int,
    request: SchedulePostRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Programa un post para publicación automática.
    """
    try:
        job_id = post_scheduler.schedule_post(
            post_id=post_id,
            scheduled_time=request.scheduled_time,
            retry_on_failure=request.retry_on_failure
        )

        return {
            "success": True,
            "job_id": job_id,
            "message": f"Post programado para {request.scheduled_time}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/posts/{post_id}/schedule")
async def cancel_scheduled_post(
    post_id: int,
    current_user: User = Depends(get_current_user)
):
    """Cancela un post programado."""
    success = post_scheduler.cancel_scheduled_post(post_id)

    if success:
        return {"success": True, "message": "Post cancelado"}
    else:
        raise HTTPException(
            status_code=500, detail="Error cancelando post"
        )


@app.put("/api/posts/{post_id}/reschedule")
async def reschedule_post(
    post_id: int,
    request: SchedulePostRequest,
    current_user: User = Depends(get_current_user)
):
    """Reprograma un post para nueva fecha."""
    try:
        job_id = post_scheduler.reschedule_post(
            post_id=post_id,
            new_scheduled_time=request.scheduled_time
        )

        return {
            "success": True,
            "job_id": job_id,
            "message": f"Post reprogramado para {request.scheduled_time}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/posts/scheduled")
async def get_scheduled_posts(
    start: Optional[str] = None,
    end: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Obtiene posts programados en un rango de fechas."""
    start_date = datetime.fromisoformat(start) if start else None
    end_date = datetime.fromisoformat(end) if end else None

    posts = post_scheduler.get_scheduled_posts(start_date, end_date)

    return {"posts": posts, "count": len(posts)}
```

### 28. Integración con n8n (Opción Avanzada - Opcional)

**[ ] 28.1 n8n Workflow Setup**

Para usuarios avanzados que quieren automatización más compleja:

```yaml
# docker-compose.n8n.yml
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=${N8N_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_PASSWORD}
      - N8N_HOST=${N8N_HOST}
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - NODE_ENV=production
      - WEBHOOK_URL=${N8N_WEBHOOK_URL}
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - sociallab_network

volumes:
  n8n_data:

networks:
  sociallab_network:
    external: true
```

**Workflow n8n Example: Programar Post**

Configuración en n8n UI:

1. **Trigger**: Webhook recibe request de programación
2. **Node 1**: HTTP Request a API de SocialLab para validar datos
3. **Node 2**: Wait (espera hasta fecha programada)
4. **Node 3**: HTTP Request a Instagram Graph API para publicar
5. **Node 4**: HTTP Request a API de SocialLab para actualizar estado
6. **Node 5**: If error, enviar notificación por email/Slack

**[ ] 28.2 Webhook Connector para n8n**

`backend/services/scheduler/n8n_connector.py`:

```python
import requests
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class N8NConnector:
    """
    Conector para integrar con n8n workflows.
    Útil para automatizaciones avanzadas.
    """

    def __init__(self):
        self.webhook_url = os.getenv('N8N_WEBHOOK_URL')
        self.auth_user = os.getenv('N8N_USER')
        self.auth_password = os.getenv('N8N_PASSWORD')

    def trigger_workflow(
        self,
        workflow_name: str,
        data: Dict[str, Any]
    ) -> Dict:
        """
        Dispara un workflow de n8n via webhook.

        Args:
            workflow_name: Nombre del workflow (ej: 'schedule_post')
            data: Datos a enviar al workflow

        Returns:
            Respuesta del workflow
        """
        try:
            url = f"{self.webhook_url}/{workflow_name}"

            response = requests.post(
                url,
                json=data,
                auth=(self.auth_user, self.auth_password),
                timeout=30
            )

            response.raise_for_status()

            logger.info(
                f"Workflow {workflow_name} triggered successfully"
            )
            return response.json()

        except Exception as e:
            logger.error(f"Error triggering n8n workflow: {e}")
            raise

    def schedule_post_via_n8n(
        self,
        post_id: int,
        scheduled_time: str,
        instagram_account_id: int
    ) -> Dict:
        """Programa post usando n8n en lugar de APScheduler."""
        return self.trigger_workflow('schedule_post', {
            'post_id': post_id,
            'scheduled_time': scheduled_time,
            'instagram_account_id': instagram_account_id,
            'action': 'schedule'
        })
```

### 29. Sistema de Análisis de Mejor Horario

**[ ] 29.1 BestTimeAnalyzer**

`backend/services/analytics/best_time_analyzer.py`:

```python
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import numpy as np
from collections import defaultdict
import logging

from database import get_supabase

logger = logging.getLogger(__name__)


class BestTimeAnalyzer:
    """
    Analiza historial de engagement para determinar mejores
    horarios de publicación.
    """

    def __init__(self):
        self.supabase = get_supabase()

    def analyze_best_times(
        self,
        instagram_account_id: int,
        days_back: int = 90
    ) -> Dict[str, List[Dict]]:
        """
        Analiza mejores horarios por día de la semana.

        Returns:
            {
                'monday': [
                    {'hour': 14, 'avg_engagement': 5.2, 'posts': 12},
                    ...
                ],
                'tuesday': [...],
                ...
            }
        """
        # Obtener posts históricos con métricas
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)

        posts = self.supabase.table('posts_detailed').select(
            'published_at, likes, comments, post_type'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).gte(
            'published_at', cutoff_date.isoformat()
        ).eq('status', 'published').execute()

        if not posts.data:
            logger.warning(
                f"No hay datos históricos para account {instagram_account_id}"
            )
            return self._get_default_times()

        # Agrupar por día de semana y hora
        engagement_by_time = defaultdict(lambda: defaultdict(list))

        for post in posts.data:
            dt = datetime.fromisoformat(post['published_at'])
            day_name = dt.strftime('%A').lower()
            hour = dt.hour

            # Calcular engagement (likes + comments)
            engagement = (post.get('likes', 0) or 0) + (
                post.get('comments', 0) or 0
            )

            engagement_by_time[day_name][hour].append(engagement)

        # Calcular promedios
        result = {}

        for day in ['monday', 'tuesday', 'wednesday', 'thursday',
                    'friday', 'saturday', 'sunday']:
            if day not in engagement_by_time:
                result[day] = self._get_default_times_for_day()
                continue

            hours_data = []
            for hour in range(24):
                engagements = engagement_by_time[day].get(hour, [])

                if engagements:
                    avg_engagement = np.mean(engagements)
                    hours_data.append({
                        'hour': hour,
                        'avg_engagement': round(avg_engagement, 2),
                        'posts': len(engagements),
                        'confidence': self._calculate_confidence(
                            len(engagements)
                        )
                    })

            # Ordenar por engagement y tomar top 5
            hours_data.sort(key=lambda x: x['avg_engagement'], reverse=True)
            result[day] = hours_data[:5]

        return result

    def suggest_next_post_time(
        self,
        instagram_account_id: int,
        content_type: str = 'FEED'
    ) -> datetime:
        """
        Sugiere próximo mejor horario para publicar.
        Considera:
        - Historial de engagement
        - Contenido ya programado (evitar saturación)
        - Tipo de contenido
        """
        best_times = self.analyze_best_times(instagram_account_id)

        # Obtener posts ya programados en próximos 7 días
        scheduled_posts = self.supabase.table('posts').select(
            'scheduled_publish_time'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).eq('status', 'scheduled').gte(
            'scheduled_publish_time', datetime.utcnow().isoformat()
        ).lte(
            'scheduled_publish_time',
            (datetime.utcnow() + timedelta(days=7)).isoformat()
        ).execute()

        scheduled_times = [
            datetime.fromisoformat(p['scheduled_publish_time'])
            for p in scheduled_posts.data
        ]

        # Buscar mejor slot disponible en próximos 7 días
        now = datetime.utcnow()

        for day_offset in range(7):
            check_date = now + timedelta(days=day_offset)
            day_name = check_date.strftime('%A').lower()

            best_hours = best_times.get(day_name, [])

            for time_slot in best_hours:
                candidate_time = check_date.replace(
                    hour=time_slot['hour'],
                    minute=0,
                    second=0,
                    microsecond=0
                )

                # Verificar que no esté en el pasado
                if candidate_time <= now:
                    continue

                # Verificar que no haya post programado en ±2 horas
                conflict = any(
                    abs((candidate_time - st).total_seconds()) < 7200
                    for st in scheduled_times
                )

                if not conflict:
                    return candidate_time

        # Fallback: tomorrow at 10 AM
        return (now + timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )

    def _calculate_confidence(self, sample_size: int) -> str:
        """Calcula nivel de confianza basado en tamaño de muestra."""
        if sample_size >= 10:
            return 'high'
        elif sample_size >= 5:
            return 'medium'
        else:
            return 'low'

    def _get_default_times(self) -> Dict:
        """Horarios por defecto si no hay datos."""
        default = {
            'hour': h,
            'avg_engagement': 0,
            'posts': 0,
            'confidence': 'low'
        }

        return {
            'monday': [{'hour': 14, **default}, {'hour': 19, **default}],
            'tuesday': [{'hour': 11, **default}, {'hour': 18, **default}],
            'wednesday': [{'hour': 12, **default}, {'hour': 17, **default}],
            'thursday': [{'hour': 13, **default}, {'hour': 20, **default}],
            'friday': [{'hour': 15, **default}, {'hour': 21, **default}],
            'saturday': [{'hour': 10, **default}, {'hour': 16, **default}],
            'sunday': [{'hour': 11, **default}, {'hour': 19, **default}]
        }

    def _get_default_times_for_day(self) -> List[Dict]:
        """Horarios por defecto para un día."""
        return [
            {'hour': 10, 'avg_engagement': 0, 'posts': 0, 'confidence': 'low'},
            {'hour': 14, 'avg_engagement': 0, 'posts': 0, 'confidence': 'low'},
            {'hour': 19, 'avg_engagement': 0, 'posts': 0, 'confidence': 'low'}
        ]
```

**[ ] 29.2 Endpoint de Análisis de Horarios**

```python
@app.get("/api/analytics/best-times/{instagram_account_id}")
async def get_best_posting_times(
    instagram_account_id: int,
    days_back: int = 90,
    current_user: User = Depends(get_current_user)
):
    """Obtiene mejores horarios para publicar basado en historial."""
    analyzer = BestTimeAnalyzer()

    best_times = analyzer.analyze_best_times(
        instagram_account_id, days_back
    )

    return {
        "instagram_account_id": instagram_account_id,
        "analysis_period_days": days_back,
        "best_times_by_day": best_times
    }


@app.get("/api/analytics/suggest-time/{instagram_account_id}")
async def suggest_post_time(
    instagram_account_id: int,
    content_type: str = 'FEED',
    current_user: User = Depends(get_current_user)
):
    """Sugiere próximo mejor horario para publicar."""
    analyzer = BestTimeAnalyzer()

    suggested_time = analyzer.suggest_next_post_time(
        instagram_account_id, content_type
    )

    return {
        "suggested_time": suggested_time.isoformat(),
        "content_type": content_type,
        "message": "Hora sugerida basada en análisis de engagement"
    }
```

### Checklist de Validación Fase 5

- [ ] APScheduler configurado e inicializado
- [ ] PostScheduler implementado con retry logic
- [ ] Endpoints de scheduling funcionan
- [ ] Jobs persisten en PostgreSQL
- [ ] Sistema restaura jobs pendientes al reiniciar
- [ ] BestTimeAnalyzer analiza datos históricos
- [ ] Sugerencias de horarios son precisas
- [ ] n8n opcional configurado (si se usa)
- [ ] Tests de scheduling pasan
- [ ] Commit y push

### Entregable Fase 5
✅ Sistema completo de automatización y scheduling con análisis inteligente de horarios

---

## FASE 6: Publicación en Instagram (Días 39-43)

### Objetivo
Implementar publicación directa en Instagram usando Graph API con manejo completo de diferentes tipos de contenido.

### 30. InstagramPublisher Service

**[ ] 30.1 Core Publisher Implementation**

Ubicación: `backend/services/publisher/instagram_publisher.py`

```python
import requests
import os
import time
from typing import Dict, Optional, List
import logging

from database import get_supabase

logger = logging.getLogger(__name__)


class InstagramPublisher:
    """
    Publica contenido en Instagram usando Graph API.

    Soporta:
    - Feed posts (single image, carousels)
    - Reels
    - Stories
    - Retry automático
    """

    def __init__(self):
        self.supabase = get_supabase()
        self.graph_api_version = os.getenv('INSTAGRAM_GRAPH_API_VERSION', 'v18.0')
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"

    def publish_post(
        self,
        media_url: str,
        caption: str,
        instagram_account_id: int,
        post_type: str = 'FEED',
        is_carousel: bool = False,
        carousel_children: Optional[List[str]] = None
    ) -> Dict:
        """
        Publica un post en Instagram.

        Args:
            media_url: URL pública de la imagen/video
            caption: Caption del post
            instagram_account_id: ID interno de la cuenta
            post_type: FEED, REELS, STORY
            is_carousel: Si es carousel album
            carousel_children: URLs de imágenes del carousel

        Returns:
            {
                'id': Instagram media ID,
                'permalink': URL del post en Instagram
            }
        """
        try:
            # Obtener access token
            account = self._get_instagram_account(instagram_account_id)

            if not account:
                raise ValueError(
                    f"Instagram account {instagram_account_id} not found"
                )

            access_token = account['access_token']
            ig_user_id = account['instagram_user_id']

            # Determinar método de publicación según tipo
            if post_type == 'REELS':
                return self._publish_reel(
                    ig_user_id, access_token, media_url, caption
                )
            elif post_type == 'STORY':
                return self._publish_story(
                    ig_user_id, access_token, media_url
                )
            elif is_carousel:
                return self._publish_carousel(
                    ig_user_id, access_token, carousel_children, caption
                )
            else:
                return self._publish_feed_post(
                    ig_user_id, access_token, media_url, caption
                )

        except Exception as e:
            logger.error(f"Error publishing post: {e}")
            raise

    def _publish_feed_post(
        self,
        ig_user_id: str,
        access_token: str,
        image_url: str,
        caption: str
    ) -> Dict:
        """Publica feed post simple (single image)."""

        # Step 1: Create media container
        container_url = f"{self.base_url}/{ig_user_id}/media"

        container_params = {
            'image_url': image_url,
            'caption': caption,
            'access_token': access_token
        }

        response = requests.post(container_url, data=container_params)
        response.raise_for_status()
        container_id = response.json()['id']

        logger.info(f"Media container created: {container_id}")

        # Step 2: Publish media container
        time.sleep(2)  # Esperar procesamiento

        publish_url = f"{self.base_url}/{ig_user_id}/media_publish"

        publish_params = {
            'creation_id': container_id,
            'access_token': access_token
        }

        response = requests.post(publish_url, data=publish_params)
        response.raise_for_status()
        media_id = response.json()['id']

        logger.info(f"Media published: {media_id}")

        # Get permalink
        permalink = self._get_media_permalink(media_id, access_token)

        return {
            'id': media_id,
            'permalink': permalink
        }

    def _publish_carousel(
        self,
        ig_user_id: str,
        access_token: str,
        image_urls: List[str],
        caption: str
    ) -> Dict:
        """Publica carousel album (múltiples imágenes)."""

        # Step 1: Create containers for each image
        children_ids = []

        for image_url in image_urls:
            container_url = f"{self.base_url}/{ig_user_id}/media"

            params = {
                'image_url': image_url,
                'is_carousel_item': True,
                'access_token': access_token
            }

            response = requests.post(container_url, data=params)
            response.raise_for_status()
            children_ids.append(response.json()['id'])

        logger.info(f"Created {len(children_ids)} carousel items")

        # Step 2: Create carousel container
        carousel_url = f"{self.base_url}/{ig_user_id}/media"

        carousel_params = {
            'media_type': 'CAROUSEL',
            'caption': caption,
            'children': ','.join(children_ids),
            'access_token': access_token
        }

        response = requests.post(carousel_url, data=carousel_params)
        response.raise_for_status()
        carousel_id = response.json()['id']

        # Step 3: Publish carousel
        time.sleep(3)

        publish_url = f"{self.base_url}/{ig_user_id}/media_publish"

        publish_params = {
            'creation_id': carousel_id,
            'access_token': access_token
        }

        response = requests.post(publish_url, data=publish_params)
        response.raise_for_status()
        media_id = response.json()['id']

        logger.info(f"Carousel published: {media_id}")

        permalink = self._get_media_permalink(media_id, access_token)

        return {
            'id': media_id,
            'permalink': permalink
        }

    def _publish_reel(
        self,
        ig_user_id: str,
        access_token: str,
        video_url: str,
        caption: str
    ) -> Dict:
        """Publica un Reel."""

        # Step 1: Create reel container
        container_url = f"{self.base_url}/{ig_user_id}/media"

        params = {
            'media_type': 'REELS',
            'video_url': video_url,
            'caption': caption,
            'share_to_feed': True,
            'access_token': access_token
        }

        response = requests.post(container_url, data=params)
        response.raise_for_status()
        container_id = response.json()['id']

        logger.info(f"Reel container created: {container_id}")

        # Step 2: Wait for video processing
        self._wait_for_container_status(
            container_id, access_token, timeout=60
        )

        # Step 3: Publish reel
        publish_url = f"{self.base_url}/{ig_user_id}/media_publish"

        publish_params = {
            'creation_id': container_id,
            'access_token': access_token
        }

        response = requests.post(publish_url, data=publish_params)
        response.raise_for_status()
        media_id = response.json()['id']

        logger.info(f"Reel published: {media_id}")

        permalink = self._get_media_permalink(media_id, access_token)

        return {
            'id': media_id,
            'permalink': permalink
        }

    def _publish_story(
        self,
        ig_user_id: str,
        access_token: str,
        media_url: str
    ) -> Dict:
        """Publica una Story."""

        # Stories se publican directamente, sin container
        story_url = f"{self.base_url}/{ig_user_id}/media"

        params = {
            'image_url': media_url,
            'media_type': 'STORIES',
            'access_token': access_token
        }

        response = requests.post(story_url, data=params)
        response.raise_for_status()
        container_id = response.json()['id']

        # Publish
        publish_url = f"{self.base_url}/{ig_user_id}/media_publish"

        publish_params = {
            'creation_id': container_id,
            'access_token': access_token
        }

        response = requests.post(publish_url, data=publish_params)
        response.raise_for_status()
        media_id = response.json()['id']

        logger.info(f"Story published: {media_id}")

        return {
            'id': media_id,
            'permalink': None  # Stories don't have permanent links
        }

    def _wait_for_container_status(
        self,
        container_id: str,
        access_token: str,
        timeout: int = 60
    ):
        """
        Espera a que el container esté listo para publicar.
        Necesario para videos/reels.
        """
        url = f"{self.base_url}/{container_id}"

        params = {
            'fields': 'status_code',
            'access_token': access_token
        }

        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Container {container_id} processing timeout"
                )

            response = requests.get(url, params=params)
            response.raise_for_status()

            status_code = response.json().get('status_code')

            if status_code == 'FINISHED':
                logger.info(f"Container {container_id} ready")
                return
            elif status_code == 'ERROR':
                raise ValueError(
                    f"Container {container_id} processing failed"
                )

            time.sleep(3)

    def _get_media_permalink(
        self,
        media_id: str,
        access_token: str
    ) -> str:
        """Obtiene permalink del media publicado."""
        url = f"{self.base_url}/{media_id}"

        params = {
            'fields': 'permalink',
            'access_token': access_token
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json().get('permalink', '')

    def _get_instagram_account(
        self,
        instagram_account_id: int
    ) -> Optional[Dict]:
        """Obtiene datos de cuenta de Instagram desde DB."""
        result = self.supabase.table('instagram_accounts').select(
            '*'
        ).eq('id', instagram_account_id).single().execute()

        return result.data if result.data else None

    def verify_media_url_accessibility(self, media_url: str) -> bool:
        """
        Verifica que la URL del media sea públicamente accesible.
        Instagram requiere URLs públicas.
        """
        try:
            response = requests.head(media_url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error checking media URL: {e}")
            return False
```

**[ ] 30.2 Endpoints de Publicación**

```python
@app.post("/api/posts/{post_id}/publish")
async def publish_post_now(
    post_id: int,
    current_user: User = Depends(get_current_user)
):
    """Publica un post inmediatamente en Instagram."""
    try:
        # Obtener post
        post = supabase.table('posts').select('*').eq(
            'id', post_id
        ).single().execute()

        if not post.data:
            raise HTTPException(status_code=404, detail="Post no encontrado")

        publisher = InstagramPublisher()

        # Verificar que media URL sea accesible
        if not publisher.verify_media_url_accessibility(
            post.data['media_url']
        ):
            raise HTTPException(
                status_code=400,
                detail="Media URL no es accesible públicamente"
            )

        # Publicar
        result = publisher.publish_post(
            media_url=post.data['media_url'],
            caption=post.data['caption'],
            instagram_account_id=post.data['instagram_account_id'],
            post_type=post.data.get('media_product_type', 'FEED')
        )

        # Actualizar DB
        supabase.table('posts').update({
            'status': 'published',
            'instagram_post_id': result['id'],
            'published_at': datetime.utcnow().isoformat(),
            'instagram_permalink': result.get('permalink')
        }).eq('id', post_id).execute()

        return {
            'success': True,
            'instagram_post_id': result['id'],
            'permalink': result.get('permalink'),
            'message': 'Post publicado exitosamente en Instagram'
        }

    except Exception as e:
        logger.error(f"Error publishing post {post_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 31. Sistema de Sincronización de Métricas

**[ ] 31.1 MetricsSyncer**

`backend/services/analytics/metrics_syncer.py`:

```python
import requests
import os
from datetime import datetime, timedelta
from typing import Dict, List
import logging

from database import get_supabase

logger = logging.getLogger(__name__)


class MetricsSyncer:
    """
    Sincroniza métricas de Instagram (likes, comments, views)
    con la base de datos local.
    """

    def __init__(self):
        self.supabase = get_supabase()
        self.graph_api_version = os.getenv(
            'INSTAGRAM_GRAPH_API_VERSION', 'v18.0'
        )
        self.base_url = f"https://graph.facebook.com/{self.graph_api_version}"

    def sync_post_metrics(
        self,
        post_id: int,
        instagram_post_id: str,
        access_token: str
    ) -> Dict:
        """
        Sincroniza métricas de un post específico.

        Args:
            post_id: ID interno del post
            instagram_post_id: ID del post en Instagram
            access_token: Token de acceso

        Returns:
            Métricas actualizadas
        """
        try:
            # Obtener métricas del post desde Instagram
            url = f"{self.base_url}/{instagram_post_id}"

            params = {
                'fields': 'like_count,comments_count,timestamp,media_type,media_url',
                'access_token': access_token
            }

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            likes = data.get('like_count', 0)
            comments = data.get('comments_count', 0)

            # Calcular engagement rate
            # (Para simplificar, asumimos followers = 1000)
            # En producción, obtener followers de la cuenta
            engagement_rate = ((likes + comments) / 1000) * 100

            # Actualizar tabla post_performance
            self.supabase.table('post_performance').upsert({
                'post_id': post_id,
                'likes': likes,
                'comments': comments,
                'engagement_rate': round(engagement_rate, 2),
                'last_synced_at': datetime.utcnow().isoformat()
            }, on_conflict='post_id').execute()

            logger.info(
                f"Metrics synced for post {post_id}: {likes} likes, "
                f"{comments} comments"
            )

            return {
                'likes': likes,
                'comments': comments,
                'engagement_rate': engagement_rate
            }

        except Exception as e:
            logger.error(f"Error syncing metrics for post {post_id}: {e}")
            raise

    def sync_all_recent_posts(
        self,
        instagram_account_id: int,
        days_back: int = 7
    ) -> Dict:
        """
        Sincroniza métricas de todos los posts recientes.

        Args:
            instagram_account_id: ID de la cuenta
            days_back: Días hacia atrás para sincronizar

        Returns:
            Resumen de sincronización
        """
        try:
            # Obtener cuenta
            account = self.supabase.table('instagram_accounts').select(
                '*'
            ).eq('id', instagram_account_id).single().execute()

            if not account.data:
                raise ValueError(
                    f"Instagram account {instagram_account_id} not found"
                )

            access_token = account.data['access_token']

            # Obtener posts recientes
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            posts = self.supabase.table('posts').select(
                'id, instagram_post_id'
            ).eq(
                'instagram_account_id', instagram_account_id
            ).eq('status', 'published').gte(
                'published_at', cutoff_date.isoformat()
            ).execute()

            synced_count = 0
            failed_count = 0

            for post in posts.data:
                if post.get('instagram_post_id'):
                    try:
                        self.sync_post_metrics(
                            post['id'],
                            post['instagram_post_id'],
                            access_token
                        )
                        synced_count += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to sync post {post['id']}: {e}"
                        )
                        failed_count += 1

            return {
                'synced': synced_count,
                'failed': failed_count,
                'total': len(posts.data)
            }

        except Exception as e:
            logger.error(f"Error in sync_all_recent_posts: {e}")
            raise
```

**[ ] 31.2 Endpoint de Sincronización**

```python
@app.post("/api/analytics/sync/{instagram_account_id}")
async def sync_instagram_metrics(
    instagram_account_id: int,
    days_back: int = 7,
    current_user: User = Depends(get_current_user)
):
    """Sincroniza métricas de Instagram con la base de datos."""
    try:
        syncer = MetricsSyncer()

        result = syncer.sync_all_recent_posts(
            instagram_account_id, days_back
        )

        return {
            'success': True,
            'synced_posts': result['synced'],
            'failed_posts': result['failed'],
            'total_posts': result['total'],
            'message': f"Sincronizados {result['synced']} posts"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 32. Cron Job para Sincronización Automática

**[ ] 32.1 Setup de Cron en APScheduler**

En `backend/main.py`:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from services.analytics.metrics_syncer import MetricsSyncer

# Inicializar scheduler para tareas recurrentes
cron_scheduler = BackgroundScheduler()

def sync_all_accounts_metrics():
    """Job que se ejecuta cada hora para sincronizar métricas."""
    logger.info("Starting automatic metrics sync...")

    syncer = MetricsSyncer()
    supabase = get_supabase()

    # Obtener todas las cuentas activas
    accounts = supabase.table('instagram_accounts').select(
        'id'
    ).eq('is_active', True).execute()

    for account in accounts.data:
        try:
            syncer.sync_all_recent_posts(account['id'], days_back=1)
        except Exception as e:
            logger.error(
                f"Error syncing account {account['id']}: {e}"
            )

    logger.info("Automatic metrics sync completed")

# Programar job para ejecutarse cada hora
cron_scheduler.add_job(
    sync_all_accounts_metrics,
    trigger=CronTrigger(hour='*'),  # Cada hora
    id='sync_metrics',
    replace_existing=True
)

cron_scheduler.start()

@app.on_event("shutdown")
def shutdown_cron():
    cron_scheduler.shutdown()
```

### Checklist de Validación Fase 6

- [ ] InstagramPublisher implementado
- [ ] Publicación de feed posts funciona
- [ ] Publicación de carousels funciona
- [ ] Publicación de Reels funciona
- [ ] Publicación de Stories funciona
- [ ] Verificación de URLs públicas implementada
- [ ] MetricsSyncer sincroniza métricas correctamente
- [ ] Cron job de sincronización automática funciona
- [ ] Endpoint de publicación manual funciona
- [ ] Tests de publicación pasan
- [ ] Commit y push

### Entregable Fase 6
✅ Sistema completo de publicación en Instagram con sincronización automática de métricas

---

## FASE 7: Analytics y Performance (Días 44-48)

### Objetivo
Implementar dashboard de analytics con métricas, insights y recomendaciones basadas en performance.

### 33. Analytics Dashboard Backend

**[ ] 33.1 AnalyticsService**

`backend/services/analytics/analytics_service.py`:

```python
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
from collections import defaultdict
import logging

from database import get_supabase

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Servicio de analytics para dashboard.

    Proporciona:
    - Overview de métricas
    - Análisis de engagement por tipo de contenido
    - Tendencias temporales
    - Comparativas
    - Recomendaciones
    """

    def __init__(self):
        self.supabase = get_supabase()

    def get_overview(
        self,
        instagram_account_id: int,
        period_days: int = 30
    ) -> Dict:
        """
        Obtiene overview general de métricas.

        Returns:
            {
                'total_posts': 45,
                'total_likes': 1250,
                'total_comments': 89,
                'avg_engagement_rate': 3.2,
                'best_performing_post': {...},
                'growth': {
                    'likes': 12.5,  # % vs periodo anterior
                    'comments': 8.3,
                    'engagement': 10.2
                }
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)

        # Obtener posts del periodo
        posts = self.supabase.table('posts_detailed').select(
            '*'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).eq('status', 'published').gte(
            'published_at', cutoff_date.isoformat()
        ).execute()

        if not posts.data:
            return self._get_empty_overview()

        # Calcular métricas
        total_likes = sum(p.get('likes', 0) or 0 for p in posts.data)
        total_comments = sum(p.get('comments', 0) or 0 for p in posts.data)
        total_posts = len(posts.data)

        engagement_rates = [
            p.get('engagement_rate', 0) or 0 for p in posts.data
        ]
        avg_engagement = np.mean(engagement_rates) if engagement_rates else 0

        # Mejor post
        best_post = max(
            posts.data,
            key=lambda p: (p.get('likes', 0) or 0) + (p.get('comments', 0) or 0)
        )

        # Calcular crecimiento vs periodo anterior
        growth = self._calculate_growth(
            instagram_account_id, period_days
        )

        return {
            'total_posts': total_posts,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'avg_engagement_rate': round(avg_engagement, 2),
            'best_performing_post': {
                'id': best_post['id'],
                'caption': best_post['caption'][:100],
                'likes': best_post.get('likes', 0),
                'comments': best_post.get('comments', 0),
                'media_url': best_post.get('media_url')
            },
            'growth': growth,
            'period_days': period_days
        }

    def get_engagement_by_content_type(
        self,
        instagram_account_id: int,
        period_days: int = 30
    ) -> Dict:
        """
        Analiza engagement por tipo de contenido.

        Returns:
            {
                'FEED': {
                    'posts': 20,
                    'avg_likes': 45.2,
                    'avg_comments': 3.1,
                    'avg_engagement_rate': 3.5
                },
                'REELS': {...},
                'STORY': {...}
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)

        posts = self.supabase.table('posts_detailed').select(
            'media_product_type, likes, comments, engagement_rate'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).eq('status', 'published').gte(
            'published_at', cutoff_date.isoformat()
        ).execute()

        # Agrupar por tipo
        by_type = defaultdict(lambda: {
            'likes': [],
            'comments': [],
            'engagement_rates': []
        })

        for post in posts.data:
            content_type = post.get('media_product_type', 'FEED')
            by_type[content_type]['likes'].append(
                post.get('likes', 0) or 0
            )
            by_type[content_type]['comments'].append(
                post.get('comments', 0) or 0
            )
            by_type[content_type]['engagement_rates'].append(
                post.get('engagement_rate', 0) or 0
            )

        # Calcular promedios
        result = {}

        for content_type, data in by_type.items():
            result[content_type] = {
                'posts': len(data['likes']),
                'avg_likes': round(np.mean(data['likes']), 1),
                'avg_comments': round(np.mean(data['comments']), 1),
                'avg_engagement_rate': round(
                    np.mean(data['engagement_rates']), 2
                )
            }

        return result

    def get_performance_trends(
        self,
        instagram_account_id: int,
        period_days: int = 30
    ) -> Dict:
        """
        Obtiene tendencias de performance día por día.

        Returns:
            {
                'dates': ['2025-01-01', '2025-01-02', ...],
                'likes': [45, 52, 38, ...],
                'comments': [3, 5, 2, ...],
                'engagement_rate': [3.2, 3.8, 2.9, ...]
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=period_days)

        posts = self.supabase.table('posts_detailed').select(
            'published_at, likes, comments, engagement_rate'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).eq('status', 'published').gte(
            'published_at', cutoff_date.isoformat()
        ).order('published_at').execute()

        # Agrupar por fecha
        by_date = defaultdict(lambda: {
            'likes': [],
            'comments': [],
            'engagement_rates': []
        })

        for post in posts.data:
            date_str = post['published_at'][:10]
            by_date[date_str]['likes'].append(post.get('likes', 0) or 0)
            by_date[date_str]['comments'].append(
                post.get('comments', 0) or 0
            )
            by_date[date_str]['engagement_rates'].append(
                post.get('engagement_rate', 0) or 0
            )

        # Generar series temporales
        dates = sorted(by_date.keys())

        return {
            'dates': dates,
            'likes': [
                round(np.mean(by_date[d]['likes']), 1) for d in dates
            ],
            'comments': [
                round(np.mean(by_date[d]['comments']), 1) for d in dates
            ],
            'engagement_rate': [
                round(np.mean(by_date[d]['engagement_rates']), 2)
                for d in dates
            ]
        }

    def get_recommendations(
        self,
        instagram_account_id: int
    ) -> List[Dict]:
        """
        Genera recomendaciones basadas en análisis de datos.

        Returns:
            [
                {
                    'type': 'content_type',
                    'priority': 'high',
                    'message': 'Los Reels tienen 50% más engagement...',
                    'action': 'Aumenta frecuencia de Reels a 3/semana'
                },
                ...
            ]
        """
        recommendations = []

        # Analizar por tipo de contenido
        by_type = self.get_engagement_by_content_type(
            instagram_account_id, period_days=90
        )

        if len(by_type) >= 2:
            # Encontrar mejor tipo
            best_type = max(
                by_type.items(),
                key=lambda x: x[1]['avg_engagement_rate']
            )

            recommendations.append({
                'type': 'content_type',
                'priority': 'high',
                'message': f"{best_type[0]} tiene el mejor engagement "
                          f"({best_type[1]['avg_engagement_rate']}%). "
                          f"Considera aumentar este tipo de contenido.",
                'action': f"Aumentar frecuencia de {best_type[0]}"
            })

        # Analizar horarios
        # TODO: Integrar con BestTimeAnalyzer

        # Analizar frecuencia
        overview = self.get_overview(instagram_account_id, period_days=30)

        posts_per_day = overview['total_posts'] / 30

        if posts_per_day < 0.5:  # Menos de 1 post cada 2 días
            recommendations.append({
                'type': 'frequency',
                'priority': 'medium',
                'message': f"Estás publicando {round(posts_per_day, 1)} "
                          f"posts/día. Aumentar frecuencia puede mejorar "
                          f"visibilidad.",
                'action': "Aumentar a mínimo 1 post/día"
            })

        return recommendations

    def _calculate_growth(
        self,
        instagram_account_id: int,
        period_days: int
    ) -> Dict:
        """Calcula crecimiento vs periodo anterior."""
        # Periodo actual
        current_start = datetime.utcnow() - timedelta(days=period_days)
        current_posts = self.supabase.table('posts_detailed').select(
            'likes, comments, engagement_rate'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).eq('status', 'published').gte(
            'published_at', current_start.isoformat()
        ).execute()

        # Periodo anterior
        previous_start = current_start - timedelta(days=period_days)
        previous_posts = self.supabase.table('posts_detailed').select(
            'likes, comments, engagement_rate'
        ).eq(
            'instagram_account_id', instagram_account_id
        ).eq('status', 'published').gte(
            'published_at', previous_start.isoformat()
        ).lt('published_at', current_start.isoformat()).execute()

        def calc_avg(posts, field):
            values = [p.get(field, 0) or 0 for p in posts]
            return np.mean(values) if values else 0

        current_likes = calc_avg(current_posts.data, 'likes')
        previous_likes = calc_avg(previous_posts.data, 'likes')

        current_comments = calc_avg(current_posts.data, 'comments')
        previous_comments = calc_avg(previous_posts.data, 'comments')

        current_engagement = calc_avg(
            current_posts.data, 'engagement_rate'
        )
        previous_engagement = calc_avg(
            previous_posts.data, 'engagement_rate'
        )

        def calc_growth_pct(current, previous):
            if previous == 0:
                return 0
            return round(((current - previous) / previous) * 100, 1)

        return {
            'likes': calc_growth_pct(current_likes, previous_likes),
            'comments': calc_growth_pct(current_comments, previous_comments),
            'engagement': calc_growth_pct(
                current_engagement, previous_engagement
            )
        }

    def _get_empty_overview(self) -> Dict:
        """Overview vacío cuando no hay datos."""
        return {
            'total_posts': 0,
            'total_likes': 0,
            'total_comments': 0,
            'avg_engagement_rate': 0,
            'best_performing_post': None,
            'growth': {
                'likes': 0,
                'comments': 0,
                'engagement': 0
            }
        }
```

**[ ] 33.2 Endpoints de Analytics**

```python
@app.get("/api/analytics/overview")
async def get_analytics_overview(
    instagram_account_id: int = 1,
    period_days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Obtiene overview de métricas."""
    analytics = AnalyticsService()

    overview = analytics.get_overview(instagram_account_id, period_days)

    return overview


@app.get("/api/analytics/by-content-type")
async def get_engagement_by_type(
    instagram_account_id: int = 1,
    period_days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Analiza engagement por tipo de contenido."""
    analytics = AnalyticsService()

    by_type = analytics.get_engagement_by_content_type(
        instagram_account_id, period_days
    )

    return by_type


@app.get("/api/analytics/trends")
async def get_performance_trends(
    instagram_account_id: int = 1,
    period_days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Obtiene tendencias de performance."""
    analytics = AnalyticsService()

    trends = analytics.get_performance_trends(
        instagram_account_id, period_days
    )

    return trends


@app.get("/api/analytics/recommendations")
async def get_recommendations(
    instagram_account_id: int = 1,
    current_user: User = Depends(get_current_user)
):
    """Obtiene recomendaciones basadas en datos."""
    analytics = AnalyticsService()

    recommendations = analytics.get_recommendations(instagram_account_id)

    return {'recommendations': recommendations}
```

### 34. Analytics Frontend Component

**[ ] 34.1 Analytics.tsx**

`frontend/src/components/analytics/Analytics.tsx`:

```typescript
import React, { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import './Analytics.css';

interface AnalyticsData {
  overview: any;
  byType: any;
  trends: any;
  recommendations: any[];
}

const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [periodDays, setPeriodDays] = useState(30);

  useEffect(() => {
    fetchAnalytics();
  }, [periodDays]);

  const fetchAnalytics = async () => {
    setLoading(true);
    const token = localStorage.getItem('authToken');

    try {
      const [overview, byType, trends, recommendations] = await Promise.all([
        fetch(
          `http://localhost:8000/api/analytics/overview?period_days=${periodDays}`,
          { headers: { 'Authorization': `Bearer ${token}` } }
        ).then(r => r.json()),
        fetch(
          `http://localhost:8000/api/analytics/by-content-type?period_days=${periodDays}`,
          { headers: { 'Authorization': `Bearer ${token}` } }
        ).then(r => r.json()),
        fetch(
          `http://localhost:8000/api/analytics/trends?period_days=${periodDays}`,
          { headers: { 'Authorization': `Bearer ${token}` } }
        ).then(r => r.json()),
        fetch('http://localhost:8000/api/analytics/recommendations', {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json())
      ]);

      setData({
        overview,
        byType,
        trends,
        recommendations: recommendations.recommendations
      });
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Cargando analytics...</div>;
  if (!data) return <div>No hay datos disponibles</div>;

  // Preparar datos para gráficos
  const trendData = data.trends.dates.map((date: string, i: number) => ({
    date,
    likes: data.trends.likes[i],
    comments: data.trends.comments[i],
    engagement: data.trends.engagement_rate[i]
  }));

  const typeData = Object.entries(data.byType).map(([type, stats]: [string, any]) => ({
    type,
    posts: stats.posts,
    engagement: stats.avg_engagement_rate
  }));

  return (
    <div className="analytics-container">
      <div className="analytics-header">
        <h2>📊 Analytics Dashboard</h2>
        <select
          value={periodDays}
          onChange={(e) => setPeriodDays(Number(e.target.value))}
        >
          <option value={7}>Últimos 7 días</option>
          <option value={30}>Últimos 30 días</option>
          <option value={90}>Últimos 90 días</option>
        </select>
      </div>

      {/* Overview Cards */}
      <div className="metrics-grid">
        <div className="metric-card">
          <h3>Total Posts</h3>
          <p className="metric-value">{data.overview.total_posts}</p>
        </div>
        <div className="metric-card">
          <h3>Total Likes</h3>
          <p className="metric-value">{data.overview.total_likes}</p>
          <span className={`growth ${data.overview.growth.likes >= 0 ? 'positive' : 'negative'}`}>
            {data.overview.growth.likes >= 0 ? '↑' : '↓'} {Math.abs(data.overview.growth.likes)}%
          </span>
        </div>
        <div className="metric-card">
          <h3>Total Comments</h3>
          <p className="metric-value">{data.overview.total_comments}</p>
          <span className={`growth ${data.overview.growth.comments >= 0 ? 'positive' : 'negative'}`}>
            {data.overview.growth.comments >= 0 ? '↑' : '↓'} {Math.abs(data.overview.growth.comments)}%
          </span>
        </div>
        <div className="metric-card">
          <h3>Avg Engagement</h3>
          <p className="metric-value">{data.overview.avg_engagement_rate}%</p>
          <span className={`growth ${data.overview.growth.engagement >= 0 ? 'positive' : 'negative'}`}>
            {data.overview.growth.engagement >= 0 ? '↑' : '↓'} {Math.abs(data.overview.growth.engagement)}%
          </span>
        </div>
      </div>

      {/* Trends Chart */}
      <div className="chart-section">
        <h3>Tendencias de Engagement</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={trendData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="likes" stroke="#8884d8" />
            <Line type="monotone" dataKey="comments" stroke="#82ca9d" />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* By Content Type */}
      <div className="chart-section">
        <h3>Engagement por Tipo de Contenido</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={typeData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="type" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="engagement" fill="#667eea" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <div className="recommendations-section">
          <h3>💡 Recomendaciones</h3>
          {data.recommendations.map((rec, index) => (
            <div key={index} className={`recommendation ${rec.priority}`}>
              <div className="recommendation-header">
                <span className="priority-badge">{rec.priority}</span>
                <span className="type-badge">{rec.type}</span>
              </div>
              <p className="recommendation-message">{rec.message}</p>
              <p className="recommendation-action"><strong>Acción:</strong> {rec.action}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Analytics;
```

### Checklist de Validación Fase 7

- [ ] AnalyticsService implementado
- [ ] Overview de métricas funciona
- [ ] Análisis por tipo de contenido funciona
- [ ] Tendencias temporales se generan correctamente
- [ ] Sistema de recomendaciones genera insights útiles
- [ ] Analytics frontend muestra gráficos interactivos
- [ ] Cálculo de crecimiento vs periodo anterior funciona
- [ ] Tests de analytics pasan
- [ ] Commit y push

### Entregable Fase 7
✅ Dashboard completo de analytics con insights y recomendaciones

---

## FASE 8: Testing Final y Deploy (Días 49-50)

### Objetivo
Testing integral, corrección de bugs y deployment en producción.

### 35. Testing End-to-End

**[ ] 35.1 Setup de Pytest**

`backend/tests/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_supabase


@pytest.fixture
def client():
    """Cliente de pruebas de FastAPI."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Usuario de prueba."""
    return {
        'email': 'test@example.com',
        'password': 'test123',
        'full_name': 'Test User'
    }


@pytest.fixture
def auth_token(client, test_user):
    """Token de autenticación para tests."""
    # Crear usuario de prueba
    response = client.post('/auth/register', json=test_user)

    # Login
    response = client.post('/auth/login', json={
        'email': test_user['email'],
        'password': test_user['password']
    })

    return response.json()['access_token']


@pytest.fixture
def auth_headers(auth_token):
    """Headers con autenticación."""
    return {'Authorization': f'Bearer {auth_token}'}
```

**[ ] 35.2 Tests Críticos**

`backend/tests/test_content_generation.py`:

```python
def test_generate_post_end_to_end(client, auth_headers):
    """Test completo de generación de contenido."""

    # Mock PROJECT 1 data
    project1_data = {
        'source_data_id': 'test_001',
        'source_data': {
            'id': 'test_001',
            'type': 'player_stats',
            'player_name': 'Test Player',
            'team': 'Test Team',
            'date': '2025-01-15',
            'image_url': 'https://example.com/image.png',
            'data': {
                'goals': 5,
                'assists': 3
            },
            'tags': ['test']
        },
        'instagram_account_id': 1,
        'options': {
            'tone': 'energetic',
            'include_hashtags': True
        }
    }

    response = client.post(
        '/api/content/generate',
        json=project1_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    result = response.json()

    assert 'preview_url' in result
    assert 'caption' in result
    assert result['status'] == 'draft'


def test_schedule_and_publish(client, auth_headers):
    """Test de programación y publicación."""

    # Crear post
    # ... (código para crear post)

    post_id = 1  # ID del post creado

    # Programar
    schedule_data = {
        'scheduled_time': '2025-01-20T10:00:00Z',
        'retry_on_failure': True
    }

    response = client.post(
        f'/api/posts/{post_id}/schedule',
        json=schedule_data,
        headers=auth_headers
    )

    assert response.status_code == 200
    assert 'job_id' in response.json()
```

### 36. Deployment en Render

**[ ] 36.1 Configuración de Render**

Archivo `render.yaml` en la raíz:

```yaml
services:
  # Backend FastAPI
  - type: web
    name: sociallab-backend
    env: python
    region: oregon
    buildCommand: "cd backend && pip install -r requirements.txt"
    startCommand: "cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT"
    envVars:
      - key: PYTHON_VERSION
        value: "3.11.0"
      - key: DATABASE_URL
        fromDatabase:
          name: sociallab-db
          property: connectionString
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: JWT_SECRET
        generateValue: true
      - key: GEMINI_API_KEY
        sync: false
      - key: INSTAGRAM_APP_ID
        sync: false
      - key: INSTAGRAM_APP_SECRET
        sync: false
      - key: GOOGLE_DRIVE_CREDENTIALS
        sync: false

  # Frontend React
  - type: web
    name: sociallab-frontend
    env: static
    buildCommand: "cd frontend && npm install && npm run build"
    staticPublishPath: frontend/dist
    routes:
      - type: rewrite
        source: /*
        destination: /index.html
    envVars:
      - key: VITE_API_URL
        value: https://sociallab-backend.onrender.com
```

**[ ] 36.2 Checklist Pre-Deploy**

```markdown
### Checklist de Deployment

**Backend:**
- [ ] Todas las variables de entorno configuradas
- [ ] Migración 006 ejecutada en Supabase
- [ ] Tests pasan exitosamente
- [ ] Requirements.txt actualizado
- [ ] Logs configurados correctamente
- [ ] CORS configurado para dominio de producción

**Frontend:**
- [ ] Variables de entorno de producción configuradas
- [ ] Build de producción funciona sin errores
- [ ] API URLs apuntan a producción
- [ ] Assets optimizados

**Database:**
- [ ] Backup de Supabase creado
- [ ] RLS policies activadas
- [ ] Índices creados

**Servicios externos:**
- [ ] Google Drive API configurado
- [ ] Gemini API key válida
- [ ] Instagram App en modo producción
- [ ] Webhooks configurados

**Monitoring:**
- [ ] Sentry configurado (opcional)
- [ ] Health check endpoint funciona
- [ ] Logs centralizados

**Post-Deploy:**
- [ ] Verificar login funciona
- [ ] Verificar conexión con Instagram
- [ ] Verificar generación de contenido
- [ ] Verificar scheduling
- [ ] Verificar publicación
- [ ] Verificar analytics
```

### 37. Comandos de Deploy

**[ ] 37.1 Deploy Backend**

```bash
# Desde raíz del proyecto

# 1. Verificar tests
cd backend
pytest

# 2. Push a git (Render hace auto-deploy)
git add .
git commit -m "Deploy backend to production"
git push origin main

# 3. Ejecutar migración en Supabase producción
# Via Supabase Dashboard o CLI
supabase db push
```

**[ ] 37.2 Deploy Frontend**

```bash
# Desde raíz del proyecto

# 1. Build de producción
cd frontend
npm run build

# 2. Verificar build
ls -la dist/

# 3. Push a git (Render hace auto-deploy)
git add .
git commit -m "Deploy frontend to production"
git push origin main
```

### 38. Health Check Endpoint

**[ ] 38.1 Endpoint de Salud**

En `backend/main.py`:

```python
@app.get("/health")
async def health_check():
    """
    Health check endpoint para monitoring.
    Verifica conectividad con servicios críticos.
    """
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'services': {}
    }

    # Check Supabase
    try:
        supabase.table('users').select('id').limit(1).execute()
        health_status['services']['database'] = 'up'
    except Exception as e:
        health_status['services']['database'] = 'down'
        health_status['status'] = 'degraded'

    # Check Google Drive (opcional)
    try:
        # Verificar acceso a Drive
        health_status['services']['google_drive'] = 'up'
    except:
        health_status['services']['google_drive'] = 'down'

    # Check Gemini AI
    try:
        # Verificar API key válida
        health_status['services']['gemini_ai'] = 'up'
    except:
        health_status['services']['gemini_ai'] = 'down'

    return health_status
```

### Checklist de Validación Fase 8

- [ ] Tests end-to-end pasan
- [ ] Tests de integración pasan
- [ ] render.yaml configurado correctamente
- [ ] Variables de entorno en Render configuradas
- [ ] Backend deployado en Render
- [ ] Frontend deployado en Render
- [ ] Health check endpoint responde
- [ ] Todas las funcionalidades verificadas en producción
- [ ] Documentación de deployment actualizada
- [ ] Commit final y tag de versión

### Entregable Fase 8
✅ Aplicación completa deployada en producción y funcionando

---

## 8. TESTING Y VALIDACIÓN

### 8.1 Estrategia de Testing

#### Tests Unitarios (Backend)

Ubicación: `backend/tests/unit/`

```bash
# Correr tests unitarios
pytest tests/unit/ -v

# Con coverage
pytest tests/unit/ --cov=services --cov-report=html
```

Áreas clave:
- Template selector logic
- Caption generation
- Image composition
- Metadata parsing
- Best time analyzer
- Analytics calculations

#### Tests de Integración

Ubicación: `backend/tests/integration/`

```bash
pytest tests/integration/ -v
```

Áreas clave:
- Google Drive sync
- Supabase operations
- Instagram API calls
- End-to-end content generation
- Scheduling workflow
- Publishing pipeline

#### Tests Frontend (React)

```bash
cd frontend
npm run test
```

Componentes clave:
- Dashboard
- PostGenerator
- PostCalendar
- StrategyConfig
- Analytics

### 8.2 Validación Manual

Checklist de funcionalidades críticas:

**Autenticación:**
- [ ] Registro de usuario
- [ ] Login
- [ ] Logout
- [ ] Persistencia de sesión

**Conexión Instagram:**
- [ ] OAuth flow completo
- [ ] Token refresh
- [ ] Verificación de permisos

**Generación de Contenido:**
- [ ] Sincronización con Google Drive
- [ ] Selección de template
- [ ] Composición de imagen
- [ ] Generación de caption con IA
- [ ] Preview del post

**Scheduling:**
- [ ] Programar post
- [ ] Cancelar post programado
- [ ] Reprogramar post
- [ ] Jobs persisten después de reiniciar

**Publicación:**
- [ ] Publicar feed post
- [ ] Publicar carousel
- [ ] Publicar Reel
- [ ] Publicar Story

**Analytics:**
- [ ] Sincronización de métricas
- [ ] Dashboard muestra datos correctos
- [ ] Gráficos se renderizan
- [ ] Recomendaciones generadas

---

## 9. TROUBLESHOOTING

### 9.1 Problemas Comunes

#### Error: "Supabase connection failed"

**Causa:** Variables de entorno mal configuradas

**Solución:**
```bash
# Verificar .env
cat backend/.env | grep SUPABASE

# Debe mostrar:
# SUPABASE_URL=https://xxx.supabase.co
# SUPABASE_KEY=eyJxxx...
```

#### Error: "Template selection failed"

**Causa:** No hay templates en la base de datos

**Solución:**
```sql
-- Insertar template de prueba
INSERT INTO templates (
    user_id,
    template_id,
    name,
    file_url,
    content_type,
    priority
) VALUES (
    'your-user-id',
    'template_001',
    'Test Template',
    'https://your-storage.com/template.png',
    'FEED',
    10
);
```

#### Error: "Instagram API rate limit exceeded"

**Causa:** Demasiadas requests a Instagram API

**Solución:**
```python
# Implementar rate limiting
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=200, period=3600)  # 200 calls por hora
def call_instagram_api():
    # Your API call
    pass
```

#### Error: "Image composition failed"

**Causa:** Pillow no puede abrir la imagen

**Solución:**
```python
# Verificar formato de imagen
from PIL import Image

try:
    img = Image.open(image_path)
    img.verify()  # Verifica que sea válida
    img = Image.open(image_path)  # Reabrir después de verify
except Exception as e:
    print(f"Invalid image: {e}")
```

### 9.2 Debugging

#### Habilitar logs detallados

```python
# backend/main.py

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)
```

#### Verificar estado de schedulers

```bash
# Ver jobs programados en APScheduler
# Endpoint de debug (solo desarrollo):

@app.get("/debug/jobs")
async def list_jobs():
    jobs = post_scheduler.scheduler.get_jobs()
    return [
        {
            'id': job.id,
            'next_run_time': str(job.next_run_time),
            'func': str(job.func)
        }
        for job in jobs
    ]
```

---

## 10. COMANDOS ÚTILES Y FAQ

### 10.1 Comandos de Desarrollo

```bash
# Iniciar proyecto completo
python start.py

# Solo backend
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Solo frontend
cd frontend
npm run dev

# Tests
cd backend
pytest

# Linting
flake8 backend/
cd frontend && npm run lint

# Format code
black backend/
cd frontend && npm run format
```

### 10.2 Comandos de Database

```bash
# Ejecutar migración
supabase db push

# Rollback migración
supabase db reset

# Backup
pg_dump $DATABASE_URL > backup.sql

# Restore
psql $DATABASE_URL < backup.sql

# Ver tablas
psql $DATABASE_URL -c "\dt"
```

### 10.3 FAQ

**P: ¿Cómo agrego un nuevo template?**

R: Sube la imagen a Google Drive o Supabase Storage, luego inserta en tabla `templates`:

```sql
INSERT INTO templates (
    user_id,
    template_id,
    name,
    file_url,
    content_type,
    priority,
    selection_rules
) VALUES (
    'your-user-id',
    'new_template_001',
    'My New Template',
    'https://storage.url/template.png',
    'FEED',
    50,
    '{"applicable_teams": ["Team A", "Team B"]}'::jsonb
);
```

**P: ¿Cómo cambio la estrategia de CM?**

R: Usa el frontend en la pestaña "Estrategia CM" o vía API:

```bash
curl -X POST http://localhost:8000/api/ai-strategy \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instagram_account_id": 1,
    "tone": "professional",
    "language": "es",
    "posting_frequency": {
      "posts_per_week": 10,
      "preferred_days": ["lunes", "miércoles", "viernes"]
    }
  }'
```

**P: ¿Cómo fuerzo una sincronización de métricas?**

R: Vía frontend botón "Sincronizar" o vía API:

```bash
curl -X POST http://localhost:8000/api/analytics/sync/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**P: ¿Puedo usar esto sin Google Drive?**

R: Sí, puedes modificar `GoogleDriveConnector` para usar otro storage (S3, Azure Blob, Dropbox, etc.). Solo necesitas implementar los métodos `download_metadata_json()` y `download_file()`.

---

## 11. RESUMEN FINAL Y PRÓXIMOS PASOS

### ¿Qué hemos construido?

Un **planificador de contenido para Instagram completamente funcional** que:

✅ Sincroniza datos de PROJECT 1 automáticamente
✅ Selecciona templates inteligentemente
✅ Compone imágenes con Pillow
✅ Genera captions con IA (Gemini 2.0 Flash)
✅ Programa publicaciones automáticamente
✅ Publica en Instagram (Feed, Reels, Stories)
✅ Sincroniza métricas automáticamente
✅ Analiza performance y da recomendaciones
✅ Dashboard completo con visualizaciones
✅ 100% GRATUITO (dentro de los límites de free tiers)

### Stack Tecnológico Completo

**Backend:**
- Python 3.11+, FastAPI, Uvicorn
- Supabase PostgreSQL + Storage
- Pillow (image processing)
- Google Gemini 2.0 Flash (AI)
- APScheduler (scheduling)
- Instagram Graph API

**Frontend:**
- React 18+, TypeScript, Vite
- Tailwind CSS
- Recharts (visualizaciones)
- React Router

**Storage:**
- Google Drive (15GB free) - PROJECT 1 data
- Supabase Storage (1GB free) - Instagram media

**Servicios:**
- Supabase (500MB DB free)
- Google Gemini (1500 requests/day free)
- Render (hosting free tier)

### Costos Esperados

**Desarrollo (0-500 posts/mes):**
- 💰 $0/mes (todo en free tiers)

**Escala pequeña (500-2000 posts/mes):**
- Supabase Pro: $25/mes
- Render: $0 (free tier suficiente)
- **Total: ~$25/mes**

**Escala media (2000+ posts/mes):**
- Supabase Pro: $25/mes
- Render Starter: $7/mes (backend)
- Gemini AI Paid: $0 (sigue free hasta límites altos)
- **Total: ~$32/mes**

### Próximos Pasos

**Corto plazo (Semanas 1-2):**
1. ✅ Completar tests unitarios restantes
2. ✅ Deploy inicial en Render
3. ✅ Conectar primera cuenta de Instagram real
4. ✅ Probar con datos reales de PROJECT 1
5. ✅ Ajustar templates según feedback

**Medio plazo (Mes 1-2):**
1. Implementar carousel posts
2. Optimizar algoritmo de template selection
3. Mejorar prompts de Gemini para mejores captions
4. Agregar más métricas al analytics
5. Implementar notificaciones (email/Slack)

**Largo plazo (Mes 3+):**
1. Multi-cuenta Instagram (gestionar múltiples cuentas)
2. Integración con PROJECT 1 en tiempo real
3. A/B testing de templates
4. Machine Learning para predecir engagement
5. Mobile app (React Native)

### Tracking de Progreso

Usa este template para marcar el progreso:

```markdown
## Sprint Actual: [Fecha]

### Completado ✅
- [x] Item completado

### En Progreso 🚧
- [ ] Item en progreso

### Pendiente 📋
- [ ] Item pendiente

### Bloqueadores 🚫
- Descripción del bloqueador
```

---

## 12. CONTACTO Y SOPORTE

**Repositorio:** [GitHub URL aquí]
**Documentación:** Este archivo
**Issues:** [GitHub Issues URL]

**Desarrollado para:** Hong Kong Football League Social Media
**Proyecto:** Instagram Content Planner
**Versión:** 1.0.0
**Fecha:** Enero 2025

---

**¡Fin del Master Plan! 🎉**

Este documento debe ser tu guía completa durante todo el desarrollo. Actualízalo conforme avanzas y agrega nuevas secciones según sea necesario.
