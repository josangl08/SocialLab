# Sistema de Etiquetado - PROJECT 1 → SocialLab Planner

**Versión:** 1.0
**Fecha:** Enero 2025
**Propósito:** Estandarizar exports de PROJECT 1 para integración automática con SocialLab

---

## 📦 Estructura de Export

Cada export de PROJECT 1 debe seguir esta estructura:

```
Google Drive/PROJECT1_EXPORTS/{export_id}/
├── metadata.json          ← OBLIGATORIO: Metadatos del export
├── main_graphic.png       ← OBLIGATORIO: Gráfico principal
└── [archivos_opcionales]  ← Fotos, gráficos adicionales, etc.
```

---

## 🏷️ Naming Convention - export_id

### Formato:
```
{YYYY-MM-DD}_{export_type}_{entity}_{context}_{counter}
```

### Ejemplos:
```
2025-01-15_player_ronaldo_season_001
2025-01-15_team_realmadrid_last5games_001
2025-01-15_match_rmavsbarca_result_001
2025-01-15_competition_laliga_standings_001
```

### Componentes:
- **YYYY-MM-DD**: Fecha del export
- **export_type**: `player` | `team` | `match` | `competition`
- **entity**: Identificador de la entidad (slug: lowercase, sin espacios)
- **context**: `season` | `match` | `last5games` | `result` | `preview` | etc.
- **counter**: Número secuencial (001, 002, ...)

---

## 📄 Schema de metadata.json

### Campos Globales (SIEMPRE)

```json
{
  "export_id": "string (único)",
  "export_date": "ISO 8601 timestamp",
  "export_type": "player | team | match | competition"
}
```

---

## 🎯 Schemas por Tipo

### 1. PLAYER - Estadísticas de Jugador

```json
{
  "export_id": "2025-01-15_player_ronaldo_season_001",
  "export_date": "2025-01-15T22:30:00Z",
  "export_type": "player",

  "competition": {
    "id": "saudi_pro_league_2024",
    "name": "Saudi Pro League",
    "season": "2024/2025"
  },

  "team": {
    "id": "al_nassr",
    "name": "Al Nassr"
  },

  "player": {
    "id": "ronaldo_cr7",
    "name": "Cristiano Ronaldo",
    "position": "Forward",
    "number": 7,
    "nationality": "Portugal"
  },

  "context": "season",

  "stats": {
    "goals": 15,
    "assists": 8,
    "shots": 45,
    "shots_on_target": 28,
    "pass_accuracy": 87.5,
    "distance_covered_km": 10.2,
    "minutes_played": 1350
  },

  "files": {
    "main_graphic": "ronaldo_season_stats.png",
    "player_photo": "ronaldo_photo.jpg"
  }
}
```

**Valores válidos para `context`:**
- `season` - Estadísticas de toda la temporada
- `match` - Estadísticas de un partido específico
- `last_5_games` - Últimos 5 partidos
- `last_10_games` - Últimos 10 partidos
- `month` - Estadísticas del mes

---

### 2. TEAM - Estadísticas de Equipo

```json
{
  "export_id": "2025-01-15_team_realmadrid_season_001",
  "export_date": "2025-01-15T18:00:00Z",
  "export_type": "team",

  "competition": {
    "id": "laliga_2024",
    "name": "La Liga",
    "season": "2024/2025"
  },

  "team": {
    "id": "real_madrid",
    "name": "Real Madrid"
  },

  "context": "season",

  "stats": {
    "wins": 12,
    "draws": 3,
    "losses": 2,
    "goals_scored": 35,
    "goals_conceded": 12,
    "possession_avg": 62.5,
    "pass_accuracy_avg": 88.3,
    "clean_sheets": 8
  },

  "files": {
    "main_graphic": "realmadrid_season_performance.png"
  }
}
```

---

### 3. MATCH - Resultado o Preview de Partido

#### 3a. Match Result (Resultado)

```json
{
  "export_id": "2025-01-15_match_rmavsbarca_result_001",
  "export_date": "2025-01-15T23:00:00Z",
  "export_type": "match",

  "competition": {
    "id": "laliga_2024",
    "name": "La Liga",
    "matchday": 18
  },

  "match": {
    "id": "laliga_20250115_001",
    "date": "2025-01-15",
    "time": "21:00",
    "venue": "Santiago Bernabéu",
    "status": "finished",

    "home_team": {
      "id": "real_madrid",
      "name": "Real Madrid",
      "score": 2
    },

    "away_team": {
      "id": "barcelona",
      "name": "Barcelona",
      "score": 1
    },

    "winner": "home"
  },

  "stats": {
    "possession": {"home": 55, "away": 45},
    "shots": {"home": 12, "away": 8},
    "shots_on_target": {"home": 6, "away": 3},
    "cards": {
      "home": {"yellow": 2, "red": 0},
      "away": {"yellow": 3, "red": 1}
    }
  },

  "files": {
    "main_graphic": "rma_vs_barca_result.png"
  }
}
```

**Valores válidos para `match.status`:**
- `finished` - Partido terminado
- `upcoming` - Partido próximo
- `live` - En vivo (opcional)

**Valores válidos para `match.winner`:**
- `home` - Ganó local
- `away` - Ganó visitante
- `draw` - Empate

#### 3b. Match Preview (Previa)

```json
{
  "export_id": "2025-01-20_match_rmavsbarca_preview_001",
  "export_date": "2025-01-18T10:00:00Z",
  "export_type": "match",

  "competition": {
    "id": "laliga_2024",
    "name": "La Liga",
    "matchday": 19
  },

  "match": {
    "id": "laliga_20250120_001",
    "date": "2025-01-20",
    "time": "20:00",
    "venue": "Camp Nou",
    "status": "upcoming",

    "home_team": {
      "id": "barcelona",
      "name": "Barcelona"
    },

    "away_team": {
      "id": "real_madrid",
      "name": "Real Madrid"
    }
  },

  "head_to_head": {
    "total_matches": 10,
    "home_wins": 5,
    "away_wins": 3,
    "draws": 2
  },

  "form": {
    "home_last_5": ["W", "W", "D", "W", "L"],
    "away_last_5": ["W", "D", "W", "W", "D"]
  },

  "files": {
    "main_graphic": "rma_vs_barca_preview.png"
  }
}
```

---

### 4. COMPETITION - Tabla de Clasificación

```json
{
  "export_id": "2025-01-15_competition_laliga_standings_001",
  "export_date": "2025-01-15T23:30:00Z",
  "export_type": "competition",

  "competition": {
    "id": "laliga_2024",
    "name": "La Liga",
    "season": "2024/2025",
    "matchday": 18
  },

  "standings": [
    {
      "position": 1,
      "team": {"id": "real_madrid", "name": "Real Madrid"},
      "points": 45,
      "played": 17,
      "won": 14,
      "drawn": 3,
      "lost": 0,
      "goals_for": 35,
      "goals_against": 12,
      "goal_difference": 23
    },
    {
      "position": 2,
      "team": {"id": "barcelona", "name": "Barcelona"},
      "points": 42,
      "played": 17,
      "won": 13,
      "drawn": 3,
      "lost": 1,
      "goals_for": 38,
      "goals_against": 15,
      "goal_difference": 23
    }
  ],

  "highlighted_teams": ["real_madrid", "barcelona"],

  "files": {
    "main_graphic": "laliga_standings.png"
  }
}
```

---

## 📋 Checklist de Campos

### ✅ OBLIGATORIOS (Todos los tipos)

```json
{
  "export_id": "string",
  "export_date": "ISO timestamp",
  "export_type": "player | team | match | competition",
  "files": {
    "main_graphic": "filename.png"
  }
}
```

### ✅ OBLIGATORIOS (Por tipo)

**Si `export_type == "player"`:**
- `competition` (objeto completo)
- `team` (objeto completo)
- `player` (objeto completo)
- `context` (string)
- `stats` (objeto con al menos 1 stat)

**Si `export_type == "team"`:**
- `competition` (objeto completo)
- `team` (objeto completo)
- `context` (string)
- `stats` (objeto con al menos 1 stat)

**Si `export_type == "match"`:**
- `competition` (objeto completo)
- `match` (objeto completo con home_team y away_team)
- `match.status` (finished | upcoming)
- Si `status == "finished"`: `match.winner` y `match.home_team.score`, `match.away_team.score`

**Si `export_type == "competition"`:**
- `competition` (objeto completo)
- `standings` (array con al menos 1 equipo)

### 💡 OPCIONALES (Recomendados)

- `template_hints.suggested_category`
- `template_hints.tags` (array)
- `template_hints.priority` (low | standard | high | viral)

---

## 🔧 Validación en PROJECT 1

### Script de Validación Python

```python
def validate_metadata(metadata: dict) -> bool:
    # 1. Campos globales obligatorios
    required_global = ['export_id', 'export_date', 'export_type', 'files']
    for field in required_global:
        if field not in metadata:
            raise ValueError(f"Campo obligatorio faltante: {field}")

    # 2. Validar export_type
    valid_types = ['player', 'team', 'match', 'competition']
    if metadata['export_type'] not in valid_types:
        raise ValueError(f"export_type inválido: {metadata['export_type']}")

    # 3. Validar files.main_graphic
    if 'main_graphic' not in metadata.get('files', {}):
        raise ValueError("files.main_graphic es obligatorio")

    # 4. Validaciones específicas por tipo
    export_type = metadata['export_type']

    if export_type == 'player':
        required = ['competition', 'team', 'player', 'context', 'stats']
        for field in required:
            if field not in metadata:
                raise ValueError(f"Campo obligatorio para 'player': {field}")

    elif export_type == 'team':
        required = ['competition', 'team', 'context', 'stats']
        for field in required:
            if field not in metadata:
                raise ValueError(f"Campo obligatorio para 'team': {field}")

    elif export_type == 'match':
        required = ['competition', 'match']
        for field in required:
            if field not in metadata:
                raise ValueError(f"Campo obligatorio para 'match': {field}")

        # Validar match.status
        if metadata['match'].get('status') not in ['finished', 'upcoming']:
            raise ValueError("match.status debe ser 'finished' o 'upcoming'")

        # Si finished, validar winner y scores
        if metadata['match']['status'] == 'finished':
            if 'winner' not in metadata['match']:
                raise ValueError("match.winner obligatorio si status=finished")
            if 'score' not in metadata['match'].get('home_team', {}):
                raise ValueError("home_team.score obligatorio si status=finished")
            if 'score' not in metadata['match'].get('away_team', {}):
                raise ValueError("away_team.score obligatorio si status=finished")

    elif export_type == 'competition':
        required = ['competition', 'standings']
        for field in required:
            if field not in metadata:
                raise ValueError(f"Campo obligatorio para 'competition': {field}")

    return True
```

---

## 🎨 Template Selection Hints (Opcional)

Puedes incluir hints para ayudar al Template Selector:

```json
{
  "template_hints": {
    "suggested_category": "Player Stats",
    "tags": ["hatrick", "star_player", "match_winner"],
    "priority": "viral",
    "style_preference": "modern"
  }
}
```

**Valores sugeridos para `tags`:**
- Player: `star_player`, `hatrick`, `goal_scorer`, `playmaker`, `defensive_star`
- Team: `winning_streak`, `league_leaders`, `strong_attack`, `solid_defense`
- Match: `derby`, `el_clasico`, `important_match`, `rivalry`, `comeback`
- Competition: `title_race`, `relegation_battle`, `top_3`, `mid_table`

**Valores para `priority`:**
- `low` - Contenido rutinario
- `standard` - Contenido normal
- `high` - Contenido importante
- `viral` - Contenido destacado/viral

---

## 📂 Ejemplo Completo de Export

```
PROJECT1_EXPORTS/2025-01-15_player_ronaldo_hatrick_001/
├── metadata.json
├── ronaldo_hatrick_stats.png
└── ronaldo_celebration.jpg
```

**metadata.json:**
```json
{
  "export_id": "2025-01-15_player_ronaldo_hatrick_001",
  "export_date": "2025-01-15T22:45:00Z",
  "export_type": "player",

  "competition": {
    "id": "saudi_pro_league_2024",
    "name": "Saudi Pro League",
    "season": "2024/2025",
    "matchday": 16
  },

  "team": {
    "id": "al_nassr",
    "name": "Al Nassr"
  },

  "player": {
    "id": "ronaldo_cr7",
    "name": "Cristiano Ronaldo",
    "position": "Forward",
    "number": 7,
    "nationality": "Portugal"
  },

  "context": "match",

  "match": {
    "id": "spl_20250115_001",
    "date": "2025-01-15",
    "home_team": "Al Nassr",
    "away_team": "Al Hilal",
    "score": "3-2"
  },

  "stats": {
    "goals": 3,
    "assists": 1,
    "shots": 7,
    "shots_on_target": 5,
    "minutes_played": 90
  },

  "files": {
    "main_graphic": "ronaldo_hatrick_stats.png",
    "player_photo": "ronaldo_celebration.jpg"
  },

  "template_hints": {
    "suggested_category": "Player Stats",
    "tags": ["hatrick", "match_winner", "star_performance"],
    "priority": "viral"
  }
}
```

---

## 🔄 Flujo de Integración

```
PROJECT 1
    ↓
1. Analiza CSV de Wyscout
    ↓
2. Genera gráfico (matplotlib/seaborn)
    ↓
3. Crea metadata.json con schema correcto
    ↓
4. Valida metadata con script de validación
    ↓
5. Sube carpeta a Google Drive/PROJECT1_EXPORTS/
    ↓
SocialLab Planner
    ↓
6. Detecta nuevo export (polling/webhook)
    ↓
7. Lee metadata.json
    ↓
8. Template Selector elige template según export_type
    ↓
9. Image Composer combina template + gráfico
    ↓
10. Caption Generator crea texto desde metadata
    ↓
11. Publica en Instagram
```

---

## ✅ Quick Start Checklist

Para cada export de PROJECT 1:

- [ ] Crear carpeta con nombre: `{YYYY-MM-DD}_{export_type}_{entity}_{context}_{counter}`
- [ ] Generar `metadata.json` con campos obligatorios según tipo
- [ ] Incluir `files.main_graphic` con nombre del PNG
- [ ] Validar con script de validación
- [ ] Asegurar que `export_id` sea único
- [ ] Subir a Google Drive/PROJECT1_EXPORTS/

---

## 📞 Soporte

Para dudas sobre el schema:
- Consultar ejemplos en este documento
- Verificar campos obligatorios por tipo
- Usar script de validación antes de subir

**Última actualización:** Enero 2025
