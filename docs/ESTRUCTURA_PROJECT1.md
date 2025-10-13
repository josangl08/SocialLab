# 📁 Estructura de Exports de PROJECT 1

## 🎯 Problema Actual

Si estás viendo "No hay datos disponibles de PROJECT 1" en la app, es porque **la estructura de Google Drive no es la esperada**.

## ✅ Estructura Correcta

Tu carpeta `Stats_Project1` en Google Drive debe tener **SUBCARPETAS**, cada una representando un export:

```
Stats_Project1/                    ← Carpeta principal (ID en .env)
├── export_player_messi_2025_01/   ← Subcarpeta de export
│   ├── metadata.json               ← REQUERIDO ⭐
│   ├── grafico_stats.png          ← Tu imagen/gráfico
│   └── datos.json                 ← Opcional (datos adicionales)
│
├── export_match_barcelona_real/
│   ├── metadata.json               ← REQUERIDO ⭐
│   └── grafico_match.jpg
│
└── export_team_man_city/
    ├── metadata.json               ← REQUERIDO ⭐
    └── grafico_team.png
```

## 🔧 Solución Rápida: Usar el Script Helper

### Opción 1: Crear estructura automáticamente

```bash
cd backend

# Para un jugador:
python scripts/create_sample_export.py --type player --name "Lionel Messi"

# Para un partido:
python scripts/create_sample_export.py --type match --home "Barcelona" --away "Real Madrid"

# Para un equipo:
python scripts/create_sample_export.py --type team --name "Manchester City"
```

Esto te creará una carpeta en `backend/exports_to_upload/` con la estructura correcta.

**Después:**
1. Copia tu imagen/gráfico a la carpeta generada
2. Sube TODA la carpeta a Google Drive (dentro de Stats_Project1)

---

## 📝 Crear la Estructura Manualmente

### Paso 1: Crear una subcarpeta

En Google Drive, dentro de `Stats_Project1`, crea una nueva carpeta:
- Nombre: `export_player_messi_2025_01` (o cualquier nombre descriptivo)

### Paso 2: Crear metadata.json

Dentro de la carpeta, crea un archivo llamado `metadata.json` con este contenido:

#### Para Jugador (Player):

```json
{
  "export_type": "player",
  "export_version": "1.0",
  "generated_at": "2025-01-15T10:30:00",
  "player": {
    "name": "Lionel Messi",
    "position": "Forward",
    "team": "Inter Miami"
  },
  "stats": {
    "goals": 12,
    "assists": 9,
    "shots": 54,
    "pass_accuracy": "89%",
    "minutes_played": 1350
  },
  "context": "season",
  "files": {
    "main_graphic": "grafico_stats.png"
  }
}
```

#### Para Partido (Match):

```json
{
  "export_type": "match",
  "export_version": "1.0",
  "generated_at": "2025-01-14T20:00:00",
  "match": {
    "home_team": {"name": "Barcelona"},
    "away_team": {"name": "Real Madrid"},
    "score": "3-1",
    "status": "finished",
    "date": "2025-01-14"
  },
  "stats": {
    "possession": {"home": 58, "away": 42},
    "shots": {"home": 15, "away": 8},
    "corners": {"home": 7, "away": 3}
  },
  "files": {
    "main_graphic": "grafico_match.jpg"
  }
}
```

#### Para Equipo (Team):

```json
{
  "export_type": "team",
  "export_version": "1.0",
  "generated_at": "2025-01-13T15:00:00",
  "team": {
    "name": "Manchester City"
  },
  "stats": {
    "wins": 20,
    "draws": 3,
    "losses": 2,
    "goals_scored": 65,
    "goals_conceded": 18,
    "points": 63
  },
  "files": {
    "main_graphic": "grafico_team.png"
  }
}
```

### Paso 3: Subir tu imagen

Sube tu imagen/gráfico a la misma carpeta con el nombre que especificaste en `"main_graphic"`.

---

## 🔍 Verificar que Funciona

1. **Refresca la app** en el navegador
2. Ve a **"Generar Contenido"**
3. Deberías ver tus exports en la lista

Si no aparecen, revisa:
- ✅ ¿La carpeta está dentro de `Stats_Project1`?
- ✅ ¿Existe el archivo `metadata.json`?
- ✅ ¿El JSON es válido? (sin errores de sintaxis)
- ✅ ¿El nombre del gráfico en `files.main_graphic` coincide con el archivo?

---

## 🎨 Mientras Tanto: Datos de Prueba

**Buena noticia:** Si no tienes la estructura lista, la app **automáticamente mostrará datos de ejemplo** (mock) para que puedas probar el flujo completo de generación.

Los datos mock incluyen:
- ⚽ Lionel Messi (Player)
- 🏟️ Barcelona vs Real Madrid (Match)
- 🏆 Manchester City (Team)
- ⚡ Erling Haaland (Player)

---

## 💡 Tip para PROJECT 1

Si estás desarrollando PROJECT 1 (el analizador de Wyscout), haz que exporte esta estructura automáticamente:

```python
# En tu código de PROJECT 1:
import json
from pathlib import Path

def export_player_stats(player_name, stats):
    folder = Path(f"export_player_{player_name.lower().replace(' ', '_')}")
    folder.mkdir(exist_ok=True)

    metadata = {
        "export_type": "player",
        "player": {"name": player_name, ...},
        "stats": stats,
        "files": {"main_graphic": "grafico_stats.png"}
    }

    with open(folder / "metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    # Guardar tu gráfico como grafico_stats.png
    # ...
```

---

## ❓ FAQ

**P: ¿Por qué no aparecen mis datos?**
R: La app busca subcarpetas con metadata.json. Si solo tienes archivos sueltos, no los detectará.

**P: ¿Puedo cambiar los nombres de las carpetas?**
R: Sí, el nombre de la carpeta no importa. Lo importante es el contenido del metadata.json.

**P: ¿Qué formato de imagen acepta?**
R: PNG, JPG, JPEG - todos funcionan.

**P: ¿Debo tener PROJECT 1 instalado?**
R: No. Puedes crear la estructura manualmente como se indica arriba.

---

## 📧 Soporte

Si sigues teniendo problemas, revisa los logs del backend:

```bash
cd backend
uvicorn main:app --reload
# Observa los mensajes cuando entres a "Generar Contenido"
```

Busca mensajes como:
- `✅ Se encontraron X exports de PROJECT 1`
- `❌ Error listando exports: ...`
