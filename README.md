# SocialLab - Instagram Content Planner 🚀

Planificador inteligente de contenido para Instagram con IA, diseñado específicamente para Hong Kong Football League.

## 📖 Descripción

SocialLab es un sistema completo que automatiza la creación, programación y publicación de contenido en Instagram, integrando:

- **Análisis de datos de PROJECT 1** (Wyscout CSV - estadísticas de fútbol)
- **Selección inteligente de templates** diseñados en Midjourney/SeaDream
- **Composición automática de imágenes** con Pillow
- **Generación de captions con IA** usando Google Gemini 2.0 Flash
- **Programación automática** con análisis de mejores horarios
- **Publicación directa en Instagram** (Feed, Reels, Stories)
- **Analytics y métricas** con insights y recomendaciones

## 🎯 Stack Tecnológico

**Backend:**
- Python 3.11+, FastAPI, Uvicorn
- Supabase PostgreSQL + Storage
- Pillow (procesamiento de imágenes)
- Google Gemini 2.0 Flash (IA gratuita)
- APScheduler (programación)
- Instagram Graph API

**Frontend:**
- React 18+, TypeScript, Vite
- Tailwind CSS
- Recharts (visualizaciones)

**Storage:**
- Google Drive (15GB free) - datos de PROJECT 1
- Supabase Storage (1GB free) - media de Instagram

## 🚀 Quick Start

### 1. Iniciar el proyecto completo

```bash
python start.py
```

Esto iniciará automáticamente:
- Backend FastAPI en `http://localhost:8000`
- Frontend React en `http://localhost:5173`

### 2. Solo Backend

```bash
cd backend
source venv/bin/activate  # En Windows: venv\Scripts\activate
uvicorn main:app --reload --port 8000
```

### 3. Solo Frontend

```bash
cd frontend
npm run dev
```

## 📚 Documentación Completa

**🎯 IMPORTANTE:** Toda la documentación exhaustiva del proyecto está en:

📄 **[MASTER_PLAN_INSTAGRAM_PLANNER.md](./MASTER_PLAN_INSTAGRAM_PLANNER.md)**

Este documento contiene:
- ✅ Roadmap completo (50 días, 8 fases)
- ✅ Arquitectura detallada del sistema
- ✅ Código completo de todos los servicios
- ✅ Schema de base de datos (17 tablas)
- ✅ Guía de deployment en Render
- ✅ Troubleshooting y FAQ
- ✅ Testing y validación

## 🔧 Configuración Inicial

### Backend

1. Crear entorno virtual:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus credenciales
```

3. Ejecutar migraciones:
```bash
# Las migraciones se ejecutan desde Supabase SQL Editor
# Ver: backend/migrations/*.sql
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 📦 Estructura del Proyecto

```
SocialLab/
├── README.md                        # Este archivo
├── MASTER_PLAN_INSTAGRAM_PLANNER.md # 📖 Documentación completa
├── start.py                         # Script para iniciar todo
│
├── docs/                            # 📚 Documentación
│   ├── METADATA_SCHEMA.md           # Schema de metadata PROJECT 1
│   ├── GOOGLE_DRIVE_SETUP.md        # Setup Google Drive OAuth
│   └── GUIA_USO.md                  # Guía de uso completa
│
├── backend/                         # Backend FastAPI
│   ├── main.py                      # Aplicación principal
│   ├── requirements.txt             # Dependencias Python
│   ├── .env                         # Variables de entorno (no commitear)
│   ├── .env.example                 # Template de variables
│   │
│   ├── database/                    # Conexión DB
│   │   └── supabase_client.py
│   │
│   ├── services/                    # Servicios core
│   │   ├── google_drive_connector.py
│   │   ├── template_selector.py
│   │   ├── template_sync.py
│   │   ├── image_composer.py
│   │   ├── caption_generator.py
│   │   └── project1_sync.py
│   │
│   ├── routes/                      # API endpoints
│   │   └── content_generation.py
│   │
│   ├── auth/                        # Autenticación
│   │   └── instagram_oauth.py
│   │
│   ├── migrations/                  # Migraciones SQL (001-006)
│   │   └── README.md                # Cómo ejecutar migraciones
│   │
│   ├── scripts/                     # Scripts utilitarios
│   │   ├── apply_migrations.py
│   │   ├── diagnostic.py
│   │   └── create_test_templates.py
│   │
│   └── tests/                       # Tests
│       ├── test_template_selector.py
│       ├── test_image_composer.py
│       └── test_end_to_end.py       # Test flujo completo
│
└── frontend/                        # Frontend React
    ├── src/
    │   ├── components/              # Componentes React
    │   └── context/                 # Context providers
    ├── package.json
    └── vite.config.ts
```

## 🔑 Variables de Entorno Requeridas

### Backend (.env)

Copia `backend/.env.example` a `backend/.env` y configura tus credenciales:

```bash
cp backend/.env.example backend/.env
```

Ver `backend/.env.example` para todas las variables requeridas.

Documentación completa de configuración:
- Google Drive: `docs/GOOGLE_DRIVE_SETUP.md`
- Guía completa: `docs/GUIA_USO.md`
- Plan maestro: `MASTER_PLAN_INSTAGRAM_PLANNER.md`

## 📊 Base de Datos

Ver `backend/migrations/README.md` para documentación completa de migraciones.

### Migraciones disponibles:

1. **001_add_instagram_post_id.sql** - Columna para IDs de Instagram
2. **002_ensure_instagram_columns.sql** - Columnas adicionales
3. **003_create_instagram_accounts_table.sql** - Tabla de cuentas Instagram
4. **004_add_media_product_type.sql** - Tipo de contenido (FEED, REELS, STORY)
5. **005_add_scheduled_publish_time.sql** - Programación de posts
6. **006_add_missing_ids_and_schema.sql** - Schema completo (17 tablas)

Ejecutar en Supabase SQL Editor en orden o usar `python scripts/apply_migrations.py`

## 🎨 Funcionalidades Principales

### ✅ Implementado (Fase 1)
- Autenticación de usuarios
- Conexión con Instagram Business
- Sincronización de posts existentes
- Dashboard básico
- Calendario de publicaciones
- **Sincronización con Google Drive** (templates y PROJECT 1)
- **Selección inteligente de templates** (basado en metadata)
- **Composición de imágenes con Pillow** (template + gráfico)
- **Generación de captions con IA** (Google Gemini 2.0 Flash)

### 🚧 En Desarrollo (Fase 2+)
- Programación automática de publicaciones
- Publicación directa en Instagram
- Analytics completo con insights
- Sistema de colas para generación masiva
- AI Strategy personalizada por cuenta

Ver roadmap completo en MASTER_PLAN.

## 🌐 URLs Importantes

- **Frontend:** http://localhost:5173
- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **Supabase Dashboard:** https://supabase.com/dashboard

## 🧪 Testing

```bash
# Backend - Tests individuales
cd backend
python -m tests.test_template_selector
python -m tests.test_image_composer
python -m tests.test_end_to_end

# Backend - Con pytest
cd backend
pytest tests/

# Frontend
cd frontend
npm run test
```

Ver `backend/tests/__init__.py` para documentación completa de tests.

## 🚀 Deployment

Ver sección completa de deployment en MASTER_PLAN, que incluye:
- Configuración de Render
- Setup de variables de entorno
- Comandos de deploy
- Health checks

## 💰 Costos

**Desarrollo (0-500 posts/mes):** $0/mes
- Supabase Free Tier: 500MB DB + 1GB Storage
- Google Gemini: 1500 requests/día FREE
- Google Drive: 15GB FREE
- Render: FREE tier

**Producción pequeña (~2000 posts/mes):** ~$25-32/mes

Ver desglose completo en MASTER_PLAN.

## 🐛 Troubleshooting

Para problemas comunes:
1. Ver sección "Troubleshooting" en MASTER_PLAN
2. Ejecutar script de diagnóstico:
   ```bash
   cd backend
   python scripts/diagnostic.py
   ```

## 📄 Licencia

MIT License - Ver LICENSE file

## 👨‍💻 Desarrollo

**Proyecto:** Instagram Content Planner para Hong Kong Football League
**Versión:** 1.0.0
**Fecha:** Enero 2025

## 🤝 Contribuir

1. Fork el proyecto
2. Crea tu feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

**📖 Para documentación completa y exhaustiva, consulta: [MASTER_PLAN_INSTAGRAM_PLANNER.md](./MASTER_PLAN_INSTAGRAM_PLANNER.md)**
