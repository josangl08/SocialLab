# 📚 Guía de Uso - SocialLab Planner

**Versión:** 1.0
**Fecha:** Octubre 2025

---

## ✅ Estado Actual del Sistema

### Base de Datos: 100% ✅
- ✅ 9 tablas creadas y configuradas
- ✅ Triggers y funciones activas
- ✅ RLS (Row Level Security) configurado

### Servicios Backend: 100% ✅
- ✅ Google Drive Connector
- ✅ Template Selector
- ✅ Image Composer
- ✅ Template Sync
- ✅ Post Cleanup

### API Endpoints: 100% ✅
- ✅ `/templates/*` - Gestión de templates
- ✅ `/templates/sync-from-drive` - Sincronización
- ✅ `/content/generate` - Generación automática
- ✅ `/content/queue/status` - Estado de cola

---

## 🚀 Flujo de Trabajo Completo

### **PASO 1: Configurar Supabase Storage**

**Crear 2 buckets en Supabase Dashboard:**

```
https://supabase.com/dashboard/project/nopkbwsiofcqhnxcqfka/storage/buckets
```

**Bucket 1: `templates`**
- Name: `templates`
- Public: ✅ Yes
- File size limit: 10 MB
- Allowed MIME: `image/png,image/jpeg`

**Bucket 2: `posts`**
- Name: `posts`
- Public: ✅ Yes
- File size limit: 10 MB
- Allowed MIME: `image/png,image/jpeg`

---

### **PASO 2: Subir Templates a Google Drive**

**Ubicación:**
```
Google Drive/TEMPLATES_SOCIALLAB/
```

**Formato de archivos:**
- PNG o JPG
- Dimensiones recomendadas: 1080x1080 (mínimo)
- Nombres descriptivos: `player_stats_modern_blue.png`

**Ejemplos de templates:**
```
TEMPLATES_SOCIALLAB/
├── player_stats_modern_blue.png
├── player_stats_dark_elegant.png
├── match_result_victory_green.png
├── match_result_defeat_red.png
├── team_performance_gradient.png
└── story_player_highlight.png
```

---

### **PASO 3: Sincronizar Templates**

**Endpoint:**
```http
POST /templates/sync-from-drive
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "success": true,
  "synced": 6,
  "errors": 0,
  "message": "Sincronizados 6 templates. Errores: 0",
  "templates": [
    {
      "id": 1,
      "name": "player_stats_modern_blue.png",
      "image_url": "https://...supabase.co/storage/v1/object/public/templates/user_123/player_stats_modern_blue.png"
    }
  ]
}
```

**¿Qué hace?**
1. Lee archivos de `Google Drive/TEMPLATES_SOCIALLAB/`
2. Los sube a Supabase Storage bucket `templates`
3. Crea registros en tabla `templates` con configuración por defecto

---

### **PASO 4: Configurar Reglas de Selección (Opcional)**

**Endpoint:**
```http
PUT /templates/{template_id}
```

**Body:**
```json
{
  "selection_rules": {
    "export_types": ["player"],
    "min_goals": 2,
    "positions": ["Forward", "Midfielder"]
  },
  "template_config": {
    "graphic_position": "center",
    "graphic_scale": 0.75,
    "margin": 80
  },
  "priority": 80
}
```

**Reglas disponibles por tipo:**

**Player:**
- `min_goals`, `min_assists`
- `positions`: ["Forward", "Midfielder", etc]
- `contexts`: ["match", "season", etc]

**Team:**
- `min_wins`, `min_points`
- `team_ids`: ["real_madrid", etc]

**Match:**
- `match_status`: ["finished", "upcoming"]
- `winners`: ["home", "away", "draw"]
- `is_derby`: true/false

**Competition:**
- `competition_ids`: ["laliga_2024", etc]

---

### **PASO 5: PROJECT 1 Crea Export**

**Estructura requerida:**
```
Google Drive/Stats_Project1/
└── 2025-01-15_player_ronaldo_hatrick_001/
    ├── metadata.json
    └── ronaldo_hatrick_stats.png
```

**metadata.json ejemplo:**
```json
{
  "export_id": "2025-01-15_player_ronaldo_hatrick_001",
  "export_date": "2025-01-15T22:45:00Z",
  "export_type": "player",
  "competition": {
    "id": "saudi_pro_league_2024",
    "name": "Saudi Pro League"
  },
  "team": {
    "id": "al_nassr",
    "name": "Al Nassr"
  },
  "player": {
    "id": "ronaldo_cr7",
    "name": "Cristiano Ronaldo",
    "position": "Forward"
  },
  "context": "match",
  "stats": {
    "goals": 3,
    "assists": 1
  },
  "files": {
    "main_graphic": "ronaldo_hatrick_stats.png"
  }
}
```

Ver `METADATA_SCHEMA.md` para detalles completos.

---

### **PASO 6: Generar Contenido Automáticamente**

**Endpoint:**
```http
POST /content/generate
```

**Body:**
```json
{
  "export_id": "2025-01-15_player_ronaldo_hatrick_001",
  "instagram_account_id": 1,
  "format_type": "square",
  "caption_style": "engaging",
  "auto_publish": false,
  "scheduled_time": null
}
```

**¿Qué hace?**
1. ✅ Lee `metadata.json` de Google Drive
2. ✅ Selecciona mejor template según reglas
3. ✅ Descarga gráfico de PROJECT 1
4. ✅ Compone imagen final (template + gráfico)
5. ✅ Sube imagen a Supabase Storage `posts/` (temporal)
6. ✅ Genera caption con IA
7. ✅ Crea post en DB (draft/scheduled)

**Respuesta:**
```json
{
  "success": true,
  "post_id": 42,
  "preview_url": "https://...supabase.co/storage/.../posts/generated/...",
  "caption": "¡Hat-trick de Cristiano! 🔥⚽⚽⚽...",
  "template_used": {
    "id": 1,
    "name": "player_stats_modern_blue.png"
  }
}
```

---

### **PASO 7: Publicar en Instagram**

**Cuando post está listo (draft/scheduled):**

**Endpoint:**
```http
POST /instagram/publish/{post_id}
```

**¿Qué hace?**
1. ✅ Obtiene post de DB
2. ✅ Usa URL de Supabase Storage para publicar
3. ✅ Instagram API crea el post
4. ✅ **Cleanup automático:**
   - Elimina imagen de Supabase Storage
   - Guarda URL de Instagram en DB
   - Marca post como `published`

**Resultado:**
```json
{
  "success": true,
  "instagram_post_id": "18123456789",
  "message": "Post publicado exitosamente en Instagram"
}
```

---

## 🔄 Resumen de Arquitectura

```
┌──────────────────────────────────────────────┐
│ PROJECT 1 (Google Drive)                     │
│ ├── Stats_Project1/                          │
│ │   └── exports/ (metadata.json + gráficos) │
│ └── TEMPLATES_SOCIALLAB/                     │
│     └── templates PNG/JPG                    │
└──────────────────────────────────────────────┘
                    ↓
          ┌─────────────────┐
          │ /templates/     │
          │ sync-from-drive │ ← Sincroniza templates
          └─────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ Supabase Storage                             │
│ ├── templates/ (permanente)                  │
│ └── posts/ (temporal, se borra al publicar) │
└──────────────────────────────────────────────┘
                    ↓
          ┌─────────────────┐
          │ /content/       │
          │ generate        │ ← Genera contenido
          └─────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ Post en DB (draft/scheduled)                 │
│ └── media_url: Supabase Storage (temporal)   │
└──────────────────────────────────────────────┘
                    ↓
          ┌─────────────────┐
          │ /instagram/     │
          │ publish/{id}    │ ← Publica + Cleanup
          └─────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ Instagram + DB actualizado                   │
│ ├── Imagen eliminada de Supabase            │
│ └── media_url: URL de Instagram             │
└──────────────────────────────────────────────┘
```

---

## 🧪 Testing

### Test Sincronización Templates
```bash
python services/template_sync.py
```

### Test Composición Imagen
```bash
python services/image_composer.py
```

### Test Selector
```bash
python services/template_selector.py
```

### Test Cleanup
```bash
python services/post_cleanup.py
```

---

## 📊 Endpoints Útiles

### Estado de Cola
```http
GET /content/queue/status
```

### Historial de Generaciones
```http
GET /content/history?limit=50
```

### Templates Activos
```http
GET /templates?is_active=true
```

### Estado Google Drive
```http
GET /templates/drive-status
```

### Storage Stats
```python
from services.post_cleanup import get_post_cleanup
cleanup = get_post_cleanup()
stats = cleanup.get_storage_usage(user_id)
```

---

## ⚙️ Configuración Actual

### Variables de Entorno
```bash
# Supabase
SUPABASE_URL=https://nopkbwsiofcqhnxcqfka.supabase.co
SUPABASE_KEY=...

# Google Drive
GOOGLE_DRIVE_PROJECT1_FOLDER_ID=1D8jdpegnshgCwu6neSK1Wmpa3FY9TIqo
GOOGLE_DRIVE_TEMPLATES_FOLDER_ID=1L-8zozDCmBUS7U14e70fXAw8VkXOSj_u
GOOGLE_OAUTH_TYPE=desktop

# Google AI
GOOGLE_API_KEY=...

# Instagram
INSTAGRAM_APP_ID=...
```

---

## 🎯 Checklist de Inicio

- [ ] **1. Crear buckets en Supabase** (`templates`, `posts`)
- [ ] **2. Subir templates a Google Drive/TEMPLATES_SOCIALLAB/**
- [ ] **3. Sincronizar templates** (`POST /templates/sync-from-drive`)
- [ ] **4. Configurar reglas de selección** (opcional)
- [ ] **5. PROJECT 1 crea export** con metadata.json
- [ ] **6. Generar contenido** (`POST /content/generate`)
- [ ] **7. Revisar preview** y caption generado
- [ ] **8. Publicar** (`POST /instagram/publish/{id}`)
- [ ] **9. Verificar cleanup** automático

---

## 🆘 Troubleshooting

### Templates no se sincronizan
```bash
# Verificar configuración
GET /templates/drive-status

# Verificar archivos en Drive
python -c "from services.google_drive_connector import get_drive_connector; \
drive = get_drive_connector(); \
print(drive.list_files('FOLDER_ID'))"
```

### Error al generar contenido
```bash
# Verificar metadata PROJECT 1
python -c "from services.google_drive_connector import get_drive_connector; \
drive = get_drive_connector(); \
metadata = drive.download_metadata_json('EXPORT_FOLDER_ID'); \
print(metadata)"
```

### Imagen no se elimina después de publicar
```bash
# Verificar post
GET /posts/{post_id}

# Ejecutar cleanup manual
python -c "from services.post_cleanup import get_post_cleanup; \
cleanup = get_post_cleanup(); \
result = cleanup.cleanup_after_publish(POST_ID, 'INSTAGRAM_URL'); \
print(result)"
```

---

**¡Sistema listo para producción!** 🚀
