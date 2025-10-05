# Configuración de Google Drive API 🔧

## Paso 1: Crear Proyecto en Google Cloud Console

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Nombre sugerido: **"SocialLab Instagram Planner"**

## Paso 2: Habilitar Google Drive API

1. En el menú lateral: **APIs & Services > Library**
2. Busca: **"Google Drive API"**
3. Click en **"Enable"**

## Paso 3: Crear Credenciales OAuth 2.0

1. **APIs & Services > Credentials**
2. Click en **"Create Credentials" > "OAuth client ID"**
3. Si es la primera vez, configura pantalla de consentimiento:
   - User Type: **External**
   - App name: **SocialLab**
   - User support email: tu email
   - Developer contact: tu email
   - Scopes: Agregar **Google Drive API (read only)**
   - Test users: Agrega tu email

4. Volver a **Create Credentials > OAuth client ID**:
   - Application type: **Desktop app**
   - Name: **SocialLab Desktop Client**
   - Click **Create**

5. **Descargar el archivo JSON**:
   - Click en el botón de descarga (⬇️)
   - Renombrar a: **`credentials.json`**
   - Mover a: `/backend/credentials.json`

## Paso 4: Configurar Variables de Entorno

Agregar a `.env`:

```bash
# Google Drive (PROJECT 1 Integration)
GOOGLE_DRIVE_PROJECT1_FOLDER_ID=your_project1_folder_id_here
GOOGLE_DRIVE_TEMPLATES_FOLDER_ID=your_templates_folder_id_here

# Google OAuth Type (desktop para desarrollo, web para producción)
GOOGLE_OAUTH_TYPE=desktop

# Solo para producción (Web App)
# GOOGLE_REDIRECT_URI=https://sociallab.onrender.com/callback/google
```

### ¿Cómo obtener los Folder IDs?

1. Abre Google Drive
2. Navega a la carpeta que quieres
3. Mira la URL:
   ```
   https://drive.google.com/drive/folders/1ABcDEfGhIjKlMnOp
                                           ^------------------^
                                           Este es el FOLDER_ID
   ```

## Paso 5: Primera Autenticación

Ejecutar el script de prueba:

```bash
cd backend
python3 services/google_drive_connector.py
```

Esto abrirá un navegador para:
1. Seleccionar tu cuenta Google
2. Autorizar acceso a Google Drive (solo lectura)
3. Crear archivo `token.pickle` (se guarda automáticamente)

**IMPORTANTE:** Agregar a `.gitignore`:
```
credentials.json
token.pickle
```

## Paso 6: Estructura de Carpetas en Google Drive

Crea esta estructura en tu Google Drive:

```
📁 SocialLab/
├── 📁 PROJECT1_EXPORTS/          ← FOLDER_ID para PROJECT 1
│   ├── 📁 2025-01-15_player_stats/
│   │   ├── metadata.json
│   │   ├── ronaldo_stats.png
│   │   └── messi_stats.png
│   └── 📁 2025-01-16_match_results/
│       ├── metadata.json
│       └── match_result.png
│
└── 📁 TEMPLATES/                 ← FOLDER_ID para templates
    ├── 📁 player_stats/
    │   ├── modern_blue_player.png
    │   └── dark_elegant_player.png
    └── 📁 match_results/
        └── victory_green_result.png
```

## Paso 7: Instalar Dependencias

```bash
cd backend
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Paso 8: Probar Conexión

```python
from services.google_drive_connector import get_drive_connector

# Obtener conector
connector = get_drive_connector()

# Listar archivos
files = connector.list_files(limit=10)
for f in files:
    print(f"📄 {f['name']}")

# Listar exports de PROJECT 1
folder_id = "YOUR_PROJECT1_FOLDER_ID"
exports = connector.list_project1_exports(folder_id)
print(f"Encontrados {len(exports)} exports")
```

## ✅ Verificación

Si todo funciona, deberías ver:
```
✅ Autenticado con Google Drive exitosamente
📁 Encontrados X archivos
```

## 🔒 Seguridad

**NUNCA commitear:**
- ❌ `credentials.json`
- ❌ `token.pickle`
- ❌ `.env`

Estos archivos están en `.gitignore` por defecto.

## 📊 Límites y Quotas

**Google Drive API - Free Tier:**
- ✅ 15 GB storage
- ✅ Queries ilimitadas (dentro de quotas)
- ⚠️ Quota: 10,000 requests / 100 segundos
- ⚠️ 1,000 requests por usuario / 100 segundos

Para este proyecto: **Más que suficiente** ✅

## 🆘 Troubleshooting

### Error: "File not found: credentials.json"
- Descarga el archivo desde Google Cloud Console
- Colócalo en `/backend/credentials.json`

### Error: "Access denied"
- Verifica que la Google Drive API esté habilitada
- Verifica los scopes en OAuth consent screen

### Error: "Invalid grant"
- Elimina `token.pickle`
- Vuelve a ejecutar la autenticación

## 🔀 Desktop App vs Web App

### **Desarrollo Local (Ahora)**
✅ Usa: **Desktop App**
- OAuth flow abre navegador local
- Redirect a `http://localhost`
- Más fácil de configurar
- `GOOGLE_OAUTH_TYPE=desktop` en `.env`

### **Producción (Futuro - Render)**
🚀 Usa: **Web App**
- OAuth flow con redirect público
- Redirect a `https://sociallab.onrender.com/callback/google`
- Requiere endpoint `/callback/google` en backend
- `GOOGLE_OAUTH_TYPE=web` en Render

### **Cambio entre entornos**
El código ya soporta ambos automáticamente:
```bash
# .env local
GOOGLE_OAUTH_TYPE=desktop

# Variables de entorno en Render
GOOGLE_OAUTH_TYPE=web
GOOGLE_REDIRECT_URI=https://sociallab.onrender.com/callback/google
```

## 🔄 Siguiente Paso

Una vez configurado Google Drive, continuar con:
1. ✅ **Template Selector Service** (selección inteligente de templates)
2. ✅ **Image Composer Service** (composición con Pillow)
