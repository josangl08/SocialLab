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
├── backend/                 # Backend FastAPI
│   ├── main.py             # Aplicación principal
│   ├── migrations/         # Migraciones SQL (001-005)
│   ├── requirements.txt    # Dependencias Python
│   └── .env               # Variables de entorno
├── frontend/               # Frontend React
│   ├── src/
│   │   ├── components/    # Componentes React
│   │   └── context/       # Context providers
│   ├── package.json
│   └── vite.config.ts
├── start.py               # Script para iniciar todo
└── MASTER_PLAN_INSTAGRAM_PLANNER.md  # 📖 GUÍA COMPLETA
```

## 🔑 Variables de Entorno Requeridas

### Backend (.env)

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# JWT
JWT_SECRET=your_jwt_secret

# Instagram/Facebook
INSTAGRAM_APP_ID=your_instagram_app_id
INSTAGRAM_APP_SECRET=your_instagram_app_secret
INSTAGRAM_REDIRECT_URI=http://localhost:8000/callback/instagram

# Google Drive (opcional para PROJECT 1)
GOOGLE_DRIVE_FOLDER_ID=your_folder_id

# Google Gemini AI (gratuito)
GEMINI_API_KEY=your_gemini_api_key
```

Ver documentación completa en MASTER_PLAN para todas las variables.

## 📊 Base de Datos

### Migraciones disponibles:

1. **001_add_instagram_post_id.sql** - Columna para IDs de Instagram
2. **002_ensure_instagram_columns.sql** - Columnas adicionales
3. **003_create_instagram_accounts_table.sql** - Tabla de cuentas Instagram
4. **004_add_media_product_type.sql** - Tipo de contenido (FEED, REELS, STORY)
5. **005_add_scheduled_publish_time.sql** - Programación de posts

Ejecutar en Supabase SQL Editor en orden.

## 🎨 Funcionalidades Principales

### ✅ Implementado (PROJECT 1 Base)
- Autenticación de usuarios
- Conexión con Instagram Business
- Sincronización de posts existentes
- Dashboard básico
- Calendario de publicaciones

### 🚧 En Desarrollo (PROJECT 2 Planner)
- Sincronización con Google Drive (datos PROJECT 1)
- Selección inteligente de templates
- Composición de imágenes con Pillow
- Generación de captions con IA (Gemini)
- Programación automática
- Publicación directa en Instagram
- Analytics completo con insights

Ver roadmap completo en MASTER_PLAN.

## 🌐 URLs Importantes

- **Frontend:** http://localhost:5173
- **Backend:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **Supabase Dashboard:** https://supabase.com/dashboard

## 🧪 Testing

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run test
```

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
2. Ejecutar script de diagnóstico (si existe):
   ```bash
   cd backend
   python diagnostic.py
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
