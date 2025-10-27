# Plan de Implementación: Dashboard de Analytics Avanzado
**SocialLab - Instagram Content Planner**
**Fecha:** 2025-01-20
**Versión:** 1.0

---

## 📋 Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Arquitectura del Dashboard](#arquitectura-del-dashboard)
3. [Métricas y Endpoints del API](#métricas-y-endpoints-del-api)
4. [Secciones del Dashboard](#secciones-del-dashboard)
5. [Stack Tecnológico](#stack-tecnológico)
6. [Plan de Implementación por Fases](#plan-de-implementación-por-fases)
7. [Estructura de Datos](#estructura-de-datos)
8. [Componentes Frontend](#componentes-frontend)
9. [Servicios Backend](#servicios-backend)
10. [Testing y Validación](#testing-y-validación)

---

## 🎯 Resumen Ejecutivo

### Objetivo
Crear un Dashboard de Analytics Avanzado que proporcione insights accionables sobre el rendimiento de Instagram, análisis de audiencia y optimización de contenido.

### Alcance
- **5 Secciones principales** de analytics
- **15+ métricas** de Instagram Insights API
- **8+ visualizaciones** interactivas con Recharts
- **Filtros temporales** con comparación de períodos
- **Insights automáticos** basados en datos

### Mejoras vs Dashboard Actual
| Aspecto | Actual | Propuesto | Mejora |
|---------|--------|-----------|---------|
| Métricas mostradas | 6 | 15+ | +150% |
| Visualizaciones | 3 | 8+ | +167% |
| Análisis demográfico | ❌ | ✅ | Nuevo |
| Insights accionables | ❌ | ✅ | Nuevo |
| Comparación temporal | ❌ | ✅ | Nuevo |
| Análisis por tipo contenido | ❌ | ✅ | Nuevo |

---

## 🏗️ Arquitectura del Dashboard

```
┌─────────────────────────────────────────────────────────┐
│                    DASHBOARD LAYOUT                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Header con Filtros]                                  │
│  └─ Rango: [Últimos 7 días ▼] [Comparar ☐]           │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ① KPIs - Resumen de Métricas Clave                   │
│  ┌───────┬───────┬───────┬───────┬───────┐            │
│  │Alcance│Visitas│Interac│Seguido│Engagem│            │
│  │125.5K │ 8.2K  │ 15.3K │  +450 │ 8.5%  │            │
│  │+12.5% │ +8.3% │+15.2% │ +5.1% │ +2.1% │            │
│  └───────┴───────┴───────┴───────┴───────┘            │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ② ¿Quién es tu Audiencia?                            │
│  ┌──────────────────┬───────────────────┐             │
│  │ Crecimiento      │ Demografía        │             │
│  │ [Línea]          │ [Barras H]        │             │
│  │                  │ • Género/Edad     │             │
│  └──────────────────┴───────────────────┘             │
│  ┌─────────────────────────────────────┐              │
│  │ Actividad + Mejores Horarios        │              │
│  │ [Mapa de Calor Combinado]           │              │
│  │ 🔵 = Seguidores online              │              │
│  │ 🟢 = Tus mejores horarios           │              │
│  │ 🌟 = Sweet spot (overlap)           │              │
│  └─────────────────────────────────────┘              │
│  ┌─────────────────────────────────────┐              │
│  │ Top Ubicaciones                     │              │
│  │ [Tabla o Mapa]                      │              │
│  │ 1. 🇪🇸 España (45%)                 │              │
│  │ 2. 🇲🇽 México (22%)                 │              │
│  └─────────────────────────────────────┘              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ③ Rendimiento del Contenido                          │
│  ┌─────────────────────────────────────┐              │
│  │ Alcance vs Interacciones            │              │
│  │ [Gráfico Combinado: Líneas + Barras]│              │
│  └─────────────────────────────────────┘              │
│  ┌──────────────────┬──────────────────┐             │
│  │ Por Tipo         │ Tasa Guardado    │             │
│  │ [Barras Agrup.]  │ [Barras]         │             │
│  │ • Reels          │ • Por tipo       │             │
│  │ • Carruseles     │                  │             │
│  │ • Posts          │                  │             │
│  └──────────────────┴──────────────────┘             │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ④ Contenido Destacado                                │
│  ┌─────────────────────────────────────┐              │
│  │ [Tabs: Interacciones│Alcance│Saves] │              │
│  │                                      │              │
│  │ #1 [img] Caption...  ❤️ 1.2K 💬 45  │              │
│  │ #2 [img] Caption...  ❤️ 980  💬 38  │              │
│  │ #3 [img] Caption...  ❤️ 875  💬 32  │              │
│  │ #4 [img] Caption...  ❤️ 820  💬 28  │              │
│  │ #5 [img] Caption...  ❤️ 750  💬 24  │              │
│  └─────────────────────────────────────┘              │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⑤ Insights Accionables                               │
│  💡 Tu mejor día: Martes (+15% engagement)            │
│  📈 Reels superan posts en +28% de alcance           │
│  👥 Mayor crecimiento en 18-24 años (+12%)           │
│  🎯 Publica Mar/Jue 18:00 para máximo impacto        │
│                                                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ⑥ Próximos Posts Programados                         │
│  ┌─────────────────────────────────────┐              │
│  │ 🟢 Hoy 18:00    - Beach sunset...   │              │
│  │ 🔵 Mañana 12:00 - Product launch... │              │
│  │ ⚪ Viernes 19:00 - Weekend vibes... │              │
│  └─────────────────────────────────────┘              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Métricas y Endpoints del API

### Métricas Disponibles (Instagram Insights API)

Basándome en la documentación oficial de Instagram Platform API:

#### 1. **Account-Level Metrics (User Insights)**
Endpoint: `GET /{ig-user-id}/insights`

| Métrica                 | Period             | Notes                                                 | Descripción                               |
|-------------------------|--------------------|-------------------------------------------------------|-------------------------------------------|
| `reach`                 | `days_28`          | Solo disponible para 28 días.                         | Cuentas únicas alcanzadas.                |
| `profile_views`         | `day`              | Solo disponible por día.                              | Visitas al perfil.                        |
| `follower_count`        | `day`              | -                                                     | Total de seguidores (snapshot diario).      |
| `website_clicks`        | `day`              | Requiere `metric_type=total_value`.                   | Clics en el sitio web del perfil.         |
| `total_interactions`    | `day`              | Requiere `metric_type=total_value`. Nueva métrica.    | Suma de interacciones en el contenido.     |

#### 2. **Audience Demographics (Insights)**
Endpoint: `GET /{ig-user-id}/insights`

| Métrica | Period | Since/Until | Timeframe | Descripción |
|---------|--------|-------------|-----------|-------------|
| `audience_city` | lifetime | ❌ | lifetime | Top 5 ciudades |
| `audience_country` | lifetime | ❌ | lifetime | Top 5 países |
| `audience_gender_age` | lifetime | ❌ | lifetime | Distribución género/edad |
| `audience_locale` | lifetime | ❌ | lifetime | Top 5 idiomas |

#### 3. **Audience Activity (Online Followers)**
Endpoint: `GET /{ig-user-id}/insights`

| Métrica | Period | Since/Until | Timeframe | Descripción |
|---------|--------|-------------|-----------|-------------|
| `online_followers` | lifetime | ❌ | lifetime | Seguidores online por hora |

#### 4. **Media-Level Metrics (Post Insights)**
Endpoint: `GET /{ig-media-id}/insights`

| Métrica | Period | Since/Until | Timeframe | Descripción |
|---------|--------|-------------|-----------|-------------|
| `engagement` | lifetime | ❌ | lifetime | Total interacciones |
| `impressions` | lifetime | ❌ | lifetime | Impresiones del post |
| `reach` | lifetime | ❌ | lifetime | Alcance del post |
| `saved` | lifetime | ❌ | lifetime | Guardados |
| `video_views` | lifetime | ❌ | lifetime | Vistas de video (si aplica) |
| `shares` | lifetime | ❌ | lifetime | Compartidos (Stories) |

**Nota:** Los likes y comments se obtienen del endpoint `/{ig-media-id}` (no insights), campos `like_count` y `comments_count`.

---

## 🎨 Secciones del Dashboard

### **Sección 1: KPIs - Resumen de Métricas Clave**

#### Diseño
```tsx
<div className="kpi-grid">
  <KPICard
    title="Alcance"
    value="125.5K"
    change="+12.5%"
    trend="up"
    icon="bi-broadcast"
    color="primary"
  />
  <KPICard
    title="Visitas al Perfil"
    value="8.2K"
    change="+8.3%"
    trend="up"
    icon="bi-eye"
    color="info"
  />
  <KPICard
    title="Interacciones"
    value="15.3K"
    change="+15.2%"
    trend="up"
    icon="bi-heart"
    color="success"
  />
  <KPICard
    title="Seguidores"
    value="+450"
    change="+5.1%"
    trend="up"
    icon="bi-people"
    color="warning"
  />
  <KPICard
    title="Engagement Rate"
    value="8.5%"
    change="+2.1%"
    trend="up"
    icon="bi-graph-up"
    color="purple"
  />
</div>
```

#### Métricas
1. **Alcance (Reach)** - `reach` desde User Insights
2. **Visitas al Perfil** - `profile_views` desde User Insights
3. **Interacciones Totales** - Suma de likes + comments + saved de todos los posts
4. **Nuevos Seguidores** - Delta de `follower_count`
5. **Engagement Rate** - `(interacciones / reach) * 100`

#### Cálculos
```python
# Backend Service: AnalyticsService.get_kpi_overview()

def calculate_engagement_rate(total_interactions: int, total_reach: int) -> float:
    """Calcula tasa de engagement."""
    if total_reach == 0:
        return 0.0
    return (total_interactions / total_reach) * 100

def calculate_follower_growth(current: int, previous: int) -> dict:
    """Calcula crecimiento de seguidores."""
    delta = current - previous
    percentage = ((delta / previous) * 100) if previous > 0 else 0
    return {
        "absolute": delta,
        "percentage": percentage
    }
```

#### API Calls
```python
# 1. Obtener reach del período actual
GET /{ig-user-id}/insights?metric=reach&period=day&since={start}&until={end}

# 2. Obtener profile_views del período actual
GET /{ig-user-id}/insights?metric=profile_views&period=day&since={start}&until={end}

# 3. Obtener follower_count del último día
GET /{ig-user-id}/insights?metric=follower_count&period=day

# 4. Obtener posts del período y calcular interacciones
GET /{ig-user-id}/media?fields=id,like_count,comments_count,timestamp
GET /{ig-media-id}/insights?metric=saved,engagement
```

---

### **Sección 2: ¿Quién es tu Audiencia?**

#### 2.1 Gráfico de Crecimiento de Seguidores

**Tipo:** Line Chart (Recharts)

**Datos:**
```typescript
interface FollowerGrowthData {
  date: string;           // "2025-01-15"
  followers: number;      // 12450
  change: number;         // +25
}
```

**API Call:**
```python
# Obtener follower_count histórico
# NOTA: API no provee histórico directo, debemos guardarlo en BD
# Alternativa: Calcular desde nuestra BD con datos de sincronizaciones

SELECT date, follower_count
FROM instagram_account_snapshots
WHERE instagram_account_id = {id}
  AND date BETWEEN {start} AND {end}
ORDER BY date ASC
```

#### 2.2 Demografía de Audiencia

**Tipo:** Stacked Bar Chart (Horizontal)

**Datos:**
```typescript
interface AudienceDemo {
  ageGender: {
    range: string;        // "18-24"
    male: number;         // 350
    female: number;       // 420
    other: number;        // 15
  }[];
}
```

**API Call:**
```python
GET /{ig-user-id}/insights?metric=audience_gender_age&period=lifetime

# Response format:
{
  "data": [{
    "name": "audience_gender_age",
    "period": "lifetime",
    "values": [{
      "value": {
        "F.18-24": 420,
        "M.18-24": 350,
        "U.18-24": 15,
        "F.25-34": 580,
        ...
      }
    }]
  }]
}
```

#### 2.3 Mapa de Calor: Actividad + Mejores Horarios

**Tipo:** Heatmap (Custom Component)

**Concepto:**
- **Capa 1 (Azul):** Cuando tus seguidores están online (`online_followers`)
- **Capa 2 (Verde):** Cuando tus posts han tenido mejor engagement (histórico)
- **Overlap (Amarillo/Verde brillante):** Sweet spot óptimo

**Datos:**
```typescript
interface HeatmapData {
  onlineFollowers: {
    hour: number;         // 0-23
    value: number;        // cantidad de seguidores online
  }[];
  historicalPerformance: {
    dayOfWeek: number;    // 0-6 (Dom-Sab)
    hour: number;         // 0-23
    avgEngagement: number; // % promedio
    postsCount: number;   // cantidad de posts en ese slot
  }[];
  recommendations: {
    dayOfWeek: string;    // "Martes"
    hour: string;         // "18:00-20:00"
    score: number;        // 0-100 (overlap quality)
    reason: string;       // "Alta audiencia + alto engagement histórico"
  }[];
}
```

**API Calls:**
```python
# 1. Online followers
GET /{ig-user-id}/insights?metric=online_followers&period=lifetime

# Response format:
{
  "data": [{
    "name": "online_followers",
    "period": "lifetime",
    "values": [{
      "value": {
        "0": 125,   # Hora 00:00
        "1": 98,    # Hora 01:00
        ...
        "23": 156   # Hora 23:00
      }
    }]
  }]
}

# 2. Performance histórico (calcular desde BD)
SELECT
  EXTRACT(DOW FROM timestamp) as day_of_week,
  EXTRACT(HOUR FROM timestamp) as hour,
  AVG((like_count + comments_count + saved_count) / NULLIF(reach, 0) * 100) as avg_engagement,
  COUNT(*) as posts_count
FROM instagram_posts
WHERE instagram_account_id = {id}
  AND timestamp BETWEEN {start} AND {end}
  AND reach > 0
GROUP BY day_of_week, hour
ORDER BY day_of_week, hour
```

**Algoritmo de Recomendación:**
```python
def calculate_best_posting_times(
    online_followers: dict,
    historical_performance: list
) -> list:
    """
    Calcula los mejores momentos para publicar.

    Score = (online_followers_normalized * 0.4) + (engagement_rate * 0.6)
    """
    recommendations = []

    for perf in historical_performance:
        hour = perf['hour']
        online = online_followers.get(str(hour), 0)

        # Normalizar online followers (0-100)
        max_online = max(online_followers.values())
        online_score = (online / max_online) * 100 if max_online > 0 else 0

        # Engagement score (ya está en %)
        engagement_score = perf['avg_engagement']

        # Calcular score combinado
        combined_score = (online_score * 0.4) + (engagement_score * 0.6)

        recommendations.append({
            'day_of_week': get_day_name(perf['day_of_week']),
            'hour': f"{hour}:00-{hour+2}:00",
            'score': round(combined_score, 1),
            'online_followers': online,
            'avg_engagement': round(engagement_score, 1),
            'posts_count': perf['posts_count']
        })

    # Ordenar por score y retornar top 5
    return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:5]
```

#### 2.4 Top Ubicaciones

**Tipo:** Table o Mapa (opcional)

**Datos:**
```typescript
interface LocationData {
  countries: {
    code: string;         // "ES"
    name: string;         // "España"
    percentage: number;   // 45.2
    followers: number;    // 5652
  }[];
  cities: {
    name: string;         // "Madrid, Spain"
    percentage: number;   // 18.5
    followers: number;    // 2314
  }[];
}
```

**API Calls:**
```python
# Países
GET /{ig-user-id}/insights?metric=audience_country&period=lifetime

# Ciudades
GET /{ig-user-id}/insights?metric=audience_city&period=lifetime
```

---

### **Sección 3: Rendimiento del Contenido**

#### 3.1 Alcance vs Interacciones (Dual Axis)

**Tipo:** ComposedChart (Recharts) - Líneas + Barras

**Datos:**
```typescript
interface ContentPerformance {
  date: string;           // "2025-01-15"
  reach: number;          // 12500
  interactions: number;   // 1050
  posts_count: number;    // 3
}
```

**Visualización:**
- **Barra (Azul):** Reach por día
- **Línea (Rojo):** Interacciones por día
- **Eje Y Izquierdo:** Reach (escala mayor)
- **Eje Y Derecho:** Interacciones (escala menor)

**Query:**
```sql
SELECT
  DATE(timestamp) as date,
  SUM(reach) as reach,
  SUM(like_count + comments_count + saved_count) as interactions,
  COUNT(*) as posts_count
FROM instagram_posts
WHERE instagram_account_id = {id}
  AND timestamp BETWEEN {start} AND {end}
GROUP BY DATE(timestamp)
ORDER BY date ASC
```

#### 3.2 Rendimiento por Tipo de Contenido

**Tipo:** Grouped Bar Chart (Recharts)

**Datos:**
```typescript
interface ContentTypePerformance {
  type: string;           // "REELS" | "CAROUSEL_ALBUM" | "IMAGE" | "VIDEO"
  avgReach: number;       // 15230
  avgInteractions: number;// 1250
  avgEngagement: number;  // 8.2
  postsCount: number;     // 15
  totalReach: number;     // 228450
}
```

**Visualización:**
- **Barra 1 (Azul):** Alcance promedio
- **Barra 2 (Verde):** Interacciones promedio
- **Barra 3 (Naranja):** Engagement rate promedio

**Query:**
```sql
SELECT
  media_type as type,
  AVG(reach) as avg_reach,
  AVG(like_count + comments_count + saved_count) as avg_interactions,
  AVG((like_count + comments_count + saved_count) / NULLIF(reach, 0) * 100) as avg_engagement,
  COUNT(*) as posts_count,
  SUM(reach) as total_reach
FROM instagram_posts
WHERE instagram_account_id = {id}
  AND timestamp BETWEEN {start} AND {end}
  AND reach > 0
GROUP BY media_type
ORDER BY avg_engagement DESC
```

#### 3.3 Tasa de Guardado por Tipo

**Tipo:** Bar Chart (Recharts)

**Datos:**
```typescript
interface SaveRateByType {
  type: string;           // "REELS"
  avgSaveRate: number;    // 5.2 (%)
  totalSaves: number;     // 450
  postsCount: number;     // 15
}
```

**Fórmula:**
```
Save Rate = (saved_count / reach) * 100
```

**Query:**
```sql
SELECT
  media_type as type,
  AVG(saved_count / NULLIF(reach, 0) * 100) as avg_save_rate,
  SUM(saved_count) as total_saves,
  COUNT(*) as posts_count
FROM instagram_posts
WHERE instagram_account_id = {id}
  AND timestamp BETWEEN {start} AND {end}
  AND reach > 0
GROUP BY media_type
ORDER BY avg_save_rate DESC
```

---

### **Sección 4: Contenido Destacado**

**Tipo:** Card Grid con Tabs

**Tabs:**
1. Top por Interacciones (likes + comments + saves)
2. Top por Alcance (reach)
3. Top por Tasa de Guardado (saved / reach * 100)

**Datos:**
```typescript
interface TopPost {
  id: string;
  media_url: string;
  caption: string;        // Truncado a 80 chars
  timestamp: string;
  likes: number;
  comments: number;
  saved: number;
  reach: number;
  engagement_rate: number;
  save_rate: number;
  permalink: string;
}
```

**Queries:**

```sql
-- Top 5 por Interacciones
SELECT
  id, media_url, caption, timestamp, permalink,
  like_count as likes,
  comments_count as comments,
  saved_count as saved,
  reach,
  (like_count + comments_count + saved_count) as total_interactions,
  ((like_count + comments_count + saved_count) / NULLIF(reach, 0) * 100) as engagement_rate,
  (saved_count / NULLIF(reach, 0) * 100) as save_rate
FROM instagram_posts
WHERE instagram_account_id = {id}
  AND timestamp BETWEEN {start} AND {end}
  AND reach > 0
ORDER BY total_interactions DESC
LIMIT 5

-- Top 5 por Alcance
... ORDER BY reach DESC LIMIT 5

-- Top 5 por Tasa de Guardado
... ORDER BY save_rate DESC LIMIT 5
```

---

### **Sección 5: Insights Accionables**

**Tipo:** Alert/Info Cards

**Datos:**
```typescript
interface ActionableInsight {
  type: 'success' | 'info' | 'warning';
  icon: string;
  title: string;
  description: string;
  action?: string;      // Texto del botón de acción
  actionUrl?: string;   // URL de la acción
}
```

**Algoritmo de Generación:**
```python
def generate_insights(analytics_data: dict) -> list:
    """Genera insights accionables automáticamente."""
    insights = []

    # 1. Mejor día de la semana
    best_day = find_best_performing_day(analytics_data['posts'])
    if best_day['engagement_diff'] > 10:  # 10% mejor que promedio
        insights.append({
            'type': 'success',
            'icon': 'bi-calendar-check',
            'title': f'Tu mejor día es {best_day["name"]}',
            'description': f'{best_day["engagement_diff"]}% más engagement que el promedio'
        })

    # 2. Tipo de contenido ganador
    best_type = find_best_content_type(analytics_data['by_content_type'])
    if best_type['performance_diff'] > 20:  # 20% mejor
        insights.append({
            'type': 'info',
            'icon': 'bi-film',
            'title': f'{best_type["name"]} superan otros formatos',
            'description': f'{best_type["performance_diff"]}% más alcance promedio'
        })

    # 3. Segmento de audiencia en crecimiento
    growing_segment = find_growing_audience_segment(analytics_data['demographics'])
    if growing_segment['growth'] > 5:  # 5% crecimiento
        insights.append({
            'type': 'info',
            'icon': 'bi-people-fill',
            'title': f'Audiencia creciendo en {growing_segment["range"]}',
            'description': f'{growing_segment["growth"]}% de aumento en este segmento'
        })

    # 4. Recomendación de horario
    best_time = analytics_data['best_posting_times'][0]
    insights.append({
        'type': 'warning',
        'icon': 'bi-clock',
        'title': 'Hora óptima para publicar',
        'description': f'{best_time["day_of_week"]} {best_time["hour"]} - Score: {best_time["score"]}/100',
        'action': 'Programar post',
        'actionUrl': '/create-post'
    })

    # 5. Alerta de engagement bajo (si aplica)
    if analytics_data['engagement_trend'] < -15:  # -15% vs período anterior
        insights.append({
            'type': 'warning',
            'icon': 'bi-exclamation-triangle',
            'title': 'Engagement en descenso',
            'description': f'{abs(analytics_data["engagement_trend"])}% menos que período anterior. Considera variar tu contenido.'
        })

    return insights
```

---

### **Sección 6: Próximos Posts Programados**

**Tipo:** Timeline/List

**Ubicación:** Sección al final del dashboard (no sidebar)

**Diseño:**
```tsx
<div className="scheduled-posts-section">
  <h3>📅 Próximos Posts Programados</h3>
  <div className="scheduled-posts-timeline">
    {scheduledPosts.map(post => (
      <div className="scheduled-post-item" key={post.id}>
        <div className={`status-indicator ${getTimeStatus(post.scheduled_at)}`} />
        <div className="post-timing">
          <span className="date">{formatDate(post.scheduled_at)}</span>
          <span className="time">{formatTime(post.scheduled_at)}</span>
        </div>
        <div className="post-preview">
          {post.media_url && <img src={post.media_url} alt="" />}
          <p>{truncate(post.caption, 80)}</p>
        </div>
        <button className="btn-edit-post">Editar</button>
      </div>
    ))}
  </div>
</div>
```

**Estados de Color:**
- 🟢 **Verde:** Hoy (próximas 24h)
- 🔵 **Azul:** Esta semana
- ⚪ **Gris:** Más adelante

**Query:**
```sql
SELECT
  id, caption, media_url, scheduled_at, status
FROM posts
WHERE user_id = {user_id}
  AND status = 'scheduled'
  AND scheduled_at > NOW()
ORDER BY scheduled_at ASC
LIMIT 10
```

---

## 🛠️ Stack Tecnológico

### Frontend
```json
{
  "framework": "React 18 + TypeScript",
  "charts": "Recharts 2.x",
  "styling": "Tailwind CSS + Dashboard.css",
  "state": "Context API (AnalyticsContext)",
  "routing": "React Router",
  "http": "Axios",
  "date": "date-fns"
}
```

### Backend
```json
{
  "framework": "FastAPI",
  "language": "Python 3.11+",
  "database": "Supabase PostgreSQL",
  "caching": "Redis (opcional para métricas)",
  "scheduling": "APScheduler (sync diario)",
  "external_apis": [
    "Instagram Graph API",
    "Instagram Insights API"
  ]
}
```

---

## 📅 Plan de Implementación por Fases

### **Fase 1: Infraestructura y Datos (3 días)**

#### Día 1: Backend - Modelos y Servicios Base
- [ ] Crear modelos de datos en Supabase
  - `instagram_account_snapshots` (follower_count histórico)
  - `instagram_post_metrics` (métricas expandidas)
  - `analytics_cache` (caché de insights)
- [ ] Implementar `AnalyticsService` base
  - Métodos para obtener KPIs
  - Métodos para cálculos de engagement
  - Sistema de caché

#### Día 2: Backend - Integración con Instagram API
- [ ] Implementar `InstagramInsightsService`
  - Obtener account-level insights
  - Obtener media-level insights
  - Manejar rate limits y paginación
- [ ] Crear jobs de sincronización
  - Sync diario de métricas de cuenta
  - Sync de demografía semanal
  - Histórico de follower_count

#### Día 3: Backend - Endpoints API
- [ ] Crear endpoints RESTful
  - `GET /api/analytics/overview` - KPIs
  - `GET /api/analytics/audience` - Demografía + actividad
  - `GET /api/analytics/content-performance` - Rendimiento
  - `GET /api/analytics/top-posts` - Contenido destacado
  - `GET /api/analytics/insights` - Insights accionables
- [ ] Testing de endpoints

### **Fase 2: Frontend - Componentes Base (3 días)**

#### Día 4: Componentes Reutilizables
- [ ] `KPICard` - Tarjeta de métrica
- [ ] `AnalyticsChart` wrapper - Wrapper de Recharts
- [ ] `DateRangePicker` - Selector de fechas
- [ ] `ComparisonToggle` - Toggle de comparación
- [ ] `LoadingStates` - Estados de carga

#### Día 5: Sección 1 y 2
- [ ] Sección 1: KPIs
  - Implementar grid de KPIs
  - Conectar con API
  - Animaciones y transiciones
- [ ] Sección 2: Audiencia (Parte 1)
  - Gráfico de crecimiento de seguidores
  - Gráfico de demografía

#### Día 6: Sección 2 (continuación) y 3
- [ ] Sección 2: Audiencia (Parte 2)
  - Mapa de calor de actividad + horarios
  - Tabla de ubicaciones
- [ ] Sección 3: Rendimiento del Contenido
  - Gráfico alcance vs interacciones
  - Gráfico por tipo de contenido
  - Gráfico tasa de guardado

### **Fase 3: Frontend - Secciones Avanzadas (2 días)**

#### Día 7: Sección 4 y 5
- [ ] Sección 4: Contenido Destacado
  - Grid de top posts
  - Sistema de tabs
  - Enlaces a Instagram
- [ ] Sección 5: Insights Accionables
  - Cards de insights
  - Lógica de generación frontend
  - Botones de acción

#### Día 8: Sección 6 y Pulido
- [ ] Sección 6: Próximos Posts
  - Timeline de posts programados
  - Estados de color
  - Botones de edición
- [ ] Responsive design
- [ ] Optimización de performance

### **Fase 4: Testing y Deployment (2 días)**

#### Día 9: Testing Completo
- [ ] Testing backend
  - Tests unitarios de servicios
  - Tests de endpoints
  - Tests de integración con Instagram API
- [ ] Testing frontend
  - Tests de componentes (Vitest + RTL)
  - Tests de integración
  - Tests E2E con Playwright

#### Día 10: Deployment y Documentación
- [ ] Deployment
  - Deploy backend
  - Deploy frontend
  - Configuración de variables de entorno
- [ ] Documentación
  - README actualizado
  - Documentación de API
  - Guía de usuario

---

## 📦 Estructura de Datos

### Database Schema

#### `instagram_account_snapshots`
```sql
CREATE TABLE instagram_account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id BIGINT NOT NULL REFERENCES instagram_accounts(id),
    date DATE NOT NULL,
    follower_count INTEGER NOT NULL,
    following_count INTEGER,
    media_count INTEGER,
    reach INTEGER,
    impressions INTEGER,
    profile_views INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(instagram_account_id, date)
);

CREATE INDEX idx_snapshots_account_date
ON instagram_account_snapshots(instagram_account_id, date DESC);
```

#### `instagram_post_metrics` (Extender tabla existente)
```sql
ALTER TABLE instagram_posts
ADD COLUMN reach INTEGER DEFAULT 0,
ADD COLUMN impressions INTEGER DEFAULT 0,
ADD COLUMN saved_count INTEGER DEFAULT 0,
ADD COLUMN engagement_rate NUMERIC(5,2),
ADD COLUMN save_rate NUMERIC(5,2);

CREATE INDEX idx_posts_engagement
ON instagram_posts(instagram_account_id, engagement_rate DESC);

CREATE INDEX idx_posts_reach
ON instagram_posts(instagram_account_id, reach DESC);
```

#### `analytics_cache`
```sql
CREATE TABLE analytics_cache (
    id BIGSERIAL PRIMARY KEY,
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    data JSONB NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_cache_key_expires
ON analytics_cache(cache_key, expires_at);
```

#### `audience_demographics`
```sql
CREATE TABLE audience_demographics (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id BIGINT NOT NULL REFERENCES instagram_accounts(id),
    sync_date DATE NOT NULL,
    gender_age_data JSONB NOT NULL,      -- {"F.18-24": 420, "M.18-24": 350, ...}
    country_data JSONB NOT NULL,         -- {"ES": 45.2, "MX": 22.1, ...}
    city_data JSONB NOT NULL,            -- {"Madrid": 18.5, ...}
    locale_data JSONB,                   -- {"es_ES": 60, ...}
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(instagram_account_id, sync_date)
);
```

#### `online_followers_data`
```sql
CREATE TABLE online_followers_data (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id BIGINT NOT NULL REFERENCES instagram_accounts(id),
    sync_date DATE NOT NULL,
    hour_data JSONB NOT NULL,            -- {"0": 125, "1": 98, ...}
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(instagram_account_id, sync_date)
);
```

---

## 🧩 Componentes Frontend

### Estructura de Archivos
```
frontend/src/components/analytics/
├── AdvancedAnalytics.tsx          # Componente principal
├── AdvancedAnalytics.css          # Estilos del dashboard
├── sections/
│   ├── KPISection.tsx             # Sección 1
│   ├── AudienceSection.tsx        # Sección 2
│   ├── ContentPerformanceSection.tsx  # Sección 3
│   ├── TopPostsSection.tsx        # Sección 4
│   ├── InsightsSection.tsx        # Sección 5
│   └── ScheduledPostsSection.tsx  # Sección 6
├── charts/
│   ├── FollowerGrowthChart.tsx
│   ├── DemographicsChart.tsx
│   ├── ActivityHeatmap.tsx
│   ├── ReachVsInteractionsChart.tsx
│   ├── ContentTypeChart.tsx
│   └── SaveRateChart.tsx
├── cards/
│   ├── KPICard.tsx
│   ├── TopPostCard.tsx
│   └── InsightCard.tsx
└── utils/
    ├── analyticsHelpers.ts
    └── chartConfig.ts
```

### Componente Principal

```tsx
// AdvancedAnalytics.tsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { DateRangePicker } from '../common/DateRangePicker';
import KPISection from './sections/KPISection';
import AudienceSection from './sections/AudienceSection';
import ContentPerformanceSection from './sections/ContentPerformanceSection';
import TopPostsSection from './sections/TopPostsSection';
import InsightsSection from './sections/InsightsSection';
import ScheduledPostsSection from './sections/ScheduledPostsSection';
import './AdvancedAnalytics.css';

interface AnalyticsData {
  kpis: KPIData;
  audience: AudienceData;
  contentPerformance: ContentPerformanceData;
  topPosts: TopPost[];
  insights: ActionableInsight[];
  scheduledPosts: ScheduledPost[];
}

const AdvancedAnalytics: React.FC = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [dateRange, setDateRange] = useState<DateRange>({
    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), // 7 días atrás
    end: new Date()
  });
  const [compareEnabled, setCompareEnabled] = useState(false);

  useEffect(() => {
    fetchAnalyticsData();
  }, [dateRange, compareEnabled]);

  const fetchAnalyticsData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('authToken');

      // Parallel fetching de todas las secciones
      const [kpis, audience, performance, topPosts, insights, scheduled] = await Promise.all([
        fetch(`/api/analytics/overview?${buildQueryParams()}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()),

        fetch(`/api/analytics/audience?${buildQueryParams()}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()),

        fetch(`/api/analytics/content-performance?${buildQueryParams()}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()),

        fetch(`/api/analytics/top-posts?${buildQueryParams()}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()),

        fetch(`/api/analytics/insights?${buildQueryParams()}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json()),

        fetch(`/api/posts/scheduled`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }).then(r => r.json())
      ]);

      setData({
        kpis: kpis.data,
        audience: audience.data,
        contentPerformance: performance.data,
        topPosts: topPosts.data,
        insights: insights.data,
        scheduledPosts: scheduled.data
      });
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const buildQueryParams = () => {
    const params = new URLSearchParams({
      start: dateRange.start.toISOString(),
      end: dateRange.end.toISOString(),
      compare: compareEnabled.toString()
    });
    return params.toString();
  };

  if (loading) {
    return <AnalyticsLoadingSkeleton />;
  }

  if (!data) {
    return <AnalyticsError />;
  }

  return (
    <div className="advanced-analytics-container">
      {/* Header con filtros */}
      <div className="analytics-header">
        <div>
          <h1>📊 Analytics Avanzado</h1>
          <p>Insights detallados sobre tu rendimiento en Instagram</p>
        </div>
        <div className="analytics-controls">
          <DateRangePicker
            value={dateRange}
            onChange={setDateRange}
          />
          <label className="compare-toggle">
            <input
              type="checkbox"
              checked={compareEnabled}
              onChange={(e) => setCompareEnabled(e.target.checked)}
            />
            <span>Comparar con período anterior</span>
          </label>
        </div>
      </div>

      {/* Sección 1: KPIs */}
      <KPISection data={data.kpis} />

      {/* Sección 2: Audiencia */}
      <AudienceSection data={data.audience} />

      {/* Sección 3: Rendimiento del Contenido */}
      <ContentPerformanceSection data={data.contentPerformance} />

      {/* Sección 4: Top Posts */}
      <TopPostsSection posts={data.topPosts} />

      {/* Sección 5: Insights Accionables */}
      <InsightsSection insights={data.insights} />

      {/* Sección 6: Próximos Posts */}
      <ScheduledPostsSection posts={data.scheduledPosts} />
    </div>
  );
};

export default AdvancedAnalytics;
```

### Ejemplo: KPICard Component

```tsx
// cards/KPICard.tsx
import React from 'react';
import './KPICard.css';

interface KPICardProps {
  title: string;
  value: string | number;
  change?: string;        // "+12.5%"
  trend?: 'up' | 'down' | 'neutral';
  icon: string;           // Bootstrap icon class
  color?: string;         // primary, success, warning, etc.
  comparison?: {
    value: string | number;
    label: string;
  };
}

export const KPICard: React.FC<KPICardProps> = ({
  title,
  value,
  change,
  trend = 'neutral',
  icon,
  color = 'primary',
  comparison
}) => {
  return (
    <div className={`kpi-card kpi-card-${color}`}>
      <div className="kpi-icon">
        <i className={`bi ${icon}`}></i>
      </div>
      <div className="kpi-content">
        <h3 className="kpi-title">{title}</h3>
        <div className="kpi-value">{value}</div>
        {change && (
          <div className={`kpi-change kpi-change-${trend}`}>
            <i className={`bi bi-arrow-${trend === 'up' ? 'up' : 'down'}`}></i>
            {change}
          </div>
        )}
        {comparison && (
          <div className="kpi-comparison">
            <span className="comparison-label">{comparison.label}:</span>
            <span className="comparison-value">{comparison.value}</span>
          </div>
        )}
      </div>
    </div>
  );
};
```

---

## ⚙️ Servicios Backend

### Estructura de Archivos
```
backend/
├── routes/
│   └── analytics_routes.py        # Endpoints de analytics
├── services/
│   ├── analytics_service.py       # Lógica de analytics
│   ├── instagram_insights_service.py  # Instagram API
│   └── insights_generator_service.py  # Generador de insights
├── models/
│   └── analytics_models.py        # Pydantic schemas
└── utils/
    ├── cache_utils.py
    └── date_utils.py
```

### Servicio Principal

```python
# services/analytics_service.py

from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import text
from ..database.supabase_client import get_db
from .instagram_insights_service import InstagramInsightsService
from .insights_generator_service import InsightsGeneratorService

class AnalyticsService:
    """Servicio principal para analytics avanzado."""

    def __init__(self, db_session):
        self.db = db_session
        self.instagram_service = InstagramInsightsService()
        self.insights_generator = InsightsGeneratorService()

    async def get_kpi_overview(
        self,
        instagram_account_id: int,
        start_date: datetime,
        end_date: datetime,
        compare: bool = False
    ) -> Dict:
        """Obtiene KPIs del dashboard."""

        # 1. Obtener reach del período
        reach_data = await self._get_account_metric(
            instagram_account_id,
            'reach',
            start_date,
            end_date
        )
        total_reach = sum([d['value'] for d in reach_data])

        # 2. Obtener profile views
        profile_views_data = await self._get_account_metric(
            instagram_account_id,
            'profile_views',
            start_date,
            end_date
        )
        total_profile_views = sum([d['value'] for d in profile_views_data])

        # 3. Obtener interacciones de posts
        posts_metrics = await self._get_posts_metrics(
            instagram_account_id,
            start_date,
            end_date
        )
        total_interactions = sum([
            p['likes'] + p['comments'] + p['saved']
            for p in posts_metrics
        ])

        # 4. Obtener follower count
        follower_data = await self._get_follower_growth(
            instagram_account_id,
            start_date,
            end_date
        )

        # 5. Calcular engagement rate
        engagement_rate = (total_interactions / total_reach * 100) if total_reach > 0 else 0

        kpis = {
            'reach': {
                'value': total_reach,
                'change': None
            },
            'profile_views': {
                'value': total_profile_views,
                'change': None
            },
            'interactions': {
                'value': total_interactions,
                'change': None
            },
            'followers': {
                'value': follower_data['current'],
                'change': follower_data['delta']
            },
            'engagement_rate': {
                'value': round(engagement_rate, 1),
                'change': None
            }
        }

        # Si compare está activado, calcular cambios
        if compare:
            previous_period = await self._get_previous_period_kpis(
                instagram_account_id,
                start_date,
                end_date
            )

            for key in kpis:
                if key in previous_period and previous_period[key] > 0:
                    current = kpis[key]['value']
                    previous = previous_period[key]
                    change_pct = ((current - previous) / previous) * 100
                    kpis[key]['change'] = f"{'+' if change_pct > 0 else ''}{change_pct:.1f}%"

        return kpis

    async def get_audience_data(
        self,
        instagram_account_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Obtiene datos de audiencia."""

        # 1. Crecimiento de seguidores
        follower_growth = await self._get_follower_growth_timeseries(
            instagram_account_id,
            start_date,
            end_date
        )

        # 2. Demografía
        demographics = await self._get_latest_demographics(
            instagram_account_id
        )

        # 3. Actividad de seguidores
        online_followers = await self._get_online_followers(
            instagram_account_id
        )

        # 4. Performance histórico por horario
        historical_performance = await self._get_historical_performance_by_time(
            instagram_account_id,
            start_date,
            end_date
        )

        # 5. Generar recomendaciones de horarios
        best_posting_times = self._calculate_best_posting_times(
            online_followers,
            historical_performance
        )

        # 6. Top ubicaciones
        top_locations = demographics.get('countries', [])[:5]

        return {
            'follower_growth': follower_growth,
            'demographics': demographics,
            'activity_heatmap': {
                'online_followers': online_followers,
                'historical_performance': historical_performance
            },
            'best_posting_times': best_posting_times,
            'top_locations': top_locations
        }

    async def get_content_performance(
        self,
        instagram_account_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Obtiene rendimiento del contenido."""

        # 1. Reach vs Interacciones por día
        daily_performance = await self._get_daily_performance(
            instagram_account_id,
            start_date,
            end_date
        )

        # 2. Rendimiento por tipo de contenido
        by_content_type = await self._get_performance_by_type(
            instagram_account_id,
            start_date,
            end_date
        )

        # 3. Tasa de guardado por tipo
        save_rate_by_type = await self._get_save_rate_by_type(
            instagram_account_id,
            start_date,
            end_date
        )

        return {
            'daily_performance': daily_performance,
            'by_content_type': by_content_type,
            'save_rate_by_type': save_rate_by_type
        }

    async def get_top_posts(
        self,
        instagram_account_id: int,
        start_date: datetime,
        end_date: datetime,
        sort_by: str = 'interactions'  # 'interactions' | 'reach' | 'save_rate'
    ) -> List[Dict]:
        """Obtiene top 5 posts."""

        sort_column_map = {
            'interactions': '(like_count + comments_count + saved_count) DESC',
            'reach': 'reach DESC',
            'save_rate': '(saved_count::float / NULLIF(reach, 0)) DESC'
        }

        sort_column = sort_column_map.get(sort_by, sort_column_map['interactions'])

        query = text(f"""
            SELECT
                id, media_url, caption, timestamp, permalink,
                like_count as likes,
                comments_count as comments,
                saved_count as saved,
                reach,
                (like_count + comments_count + saved_count) as total_interactions,
                ((like_count + comments_count + saved_count)::float / NULLIF(reach, 0) * 100) as engagement_rate,
                (saved_count::float / NULLIF(reach, 0) * 100) as save_rate
            FROM instagram_posts
            WHERE instagram_account_id = :account_id
              AND timestamp BETWEEN :start_date AND :end_date
              AND reach > 0
            ORDER BY {sort_column}
            LIMIT 5
        """)

        result = await self.db.execute(
            query,
            {
                'account_id': instagram_account_id,
                'start_date': start_date,
                'end_date': end_date
            }
        )

        return [dict(row) for row in result]

    async def get_actionable_insights(
        self,
        instagram_account_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Genera insights accionables."""

        # Obtener datos necesarios
        analytics_data = {
            'posts': await self._get_posts_metrics(instagram_account_id, start_date, end_date),
            'by_content_type': await self._get_performance_by_type(instagram_account_id, start_date, end_date),
            'demographics': await self._get_latest_demographics(instagram_account_id),
            'best_posting_times': await self.get_audience_data(instagram_account_id, start_date, end_date)
        }

        # Generar insights
        insights = self.insights_generator.generate_insights(analytics_data)

        return insights

    # Métodos auxiliares privados

    async def _get_account_metric(
        self,
        instagram_account_id: int,
        metric: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Obtiene métrica de cuenta desde Instagram API."""
        # TODO: Implementar con InstagramInsightsService
        pass

    async def _get_posts_metrics(
        self,
        instagram_account_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Obtiene métricas de posts desde BD."""
        query = text("""
            SELECT
                id, timestamp, media_type,
                like_count as likes,
                comments_count as comments,
                saved_count as saved,
                reach, impressions,
                ((like_count + comments_count + saved_count)::float / NULLIF(reach, 0) * 100) as engagement_rate
            FROM instagram_posts
            WHERE instagram_account_id = :account_id
              AND timestamp BETWEEN :start_date AND :end_date
              AND reach > 0
            ORDER BY timestamp ASC
        """)

        result = await self.db.execute(
            query,
            {
                'account_id': instagram_account_id,
                'start_date': start_date,
                'end_date': end_date
            }
        )

        return [dict(row) for row in result]

    def _calculate_best_posting_times(
        self,
        online_followers: Dict,
        historical_performance: List[Dict]
    ) -> List[Dict]:
        """Calcula mejores horarios para publicar."""
        # Implementación del algoritmo de recomendación
        # Ver sección anterior
        pass
```

### Endpoint de API

```python
# routes/analytics_routes.py

from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
from ..services.analytics_service import AnalyticsService
from ..database.supabase_client import get_db
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/overview")
async def get_analytics_overview(
    start: datetime = Query(..., description="Fecha inicio (ISO 8601)"),
    end: datetime = Query(..., description="Fecha fin (ISO 8601)"),
    compare: bool = Query(False, description="Comparar con período anterior"),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Obtiene KPIs del dashboard."""

    service = AnalyticsService(db)

    # Obtener instagram_account_id del usuario
    instagram_account = await get_user_instagram_account(current_user.id, db)
    if not instagram_account:
        raise HTTPException(status_code=404, detail="Instagram account not connected")

    kpis = await service.get_kpi_overview(
        instagram_account.id,
        start,
        end,
        compare
    )

    return {
        "success": True,
        "data": kpis
    }

@router.get("/audience")
async def get_audience_data(
    start: datetime = Query(...),
    end: datetime = Query(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Obtiene datos de audiencia."""

    service = AnalyticsService(db)
    instagram_account = await get_user_instagram_account(current_user.id, db)

    audience_data = await service.get_audience_data(
        instagram_account.id,
        start,
        end
    )

    return {
        "success": True,
        "data": audience_data
    }

@router.get("/content-performance")
async def get_content_performance(
    start: datetime = Query(...),
    end: datetime = Query(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Obtiene rendimiento del contenido."""

    service = AnalyticsService(db)
    instagram_account = await get_user_instagram_account(current_user.id, db)

    performance_data = await service.get_content_performance(
        instagram_account.id,
        start,
        end
    )

    return {
        "success": True,
        "data": performance_data
    }

@router.get("/top-posts")
async def get_top_posts(
    start: datetime = Query(...),
    end: datetime = Query(...),
    sort_by: str = Query("interactions", regex="^(interactions|reach|save_rate)$"),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Obtiene top 5 posts."""

    service = AnalyticsService(db)
    instagram_account = await get_user_instagram_account(current_user.id, db)

    top_posts = await service.get_top_posts(
        instagram_account.id,
        start,
        end,
        sort_by
    )

    return {
        "success": True,
        "data": top_posts
    }

@router.get("/insights")
async def get_actionable_insights(
    start: datetime = Query(...),
    end: datetime = Query(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Genera insights accionables."""

    service = AnalyticsService(db)
    instagram_account = await get_user_instagram_account(current_user.id, db)

    insights = await service.get_actionable_insights(
        instagram_account.id,
        start,
        end
    )

    return {
        "success": True,
        "data": insights
    }
```

---

## 🧪 Testing y Validación

### Backend Tests

```python
# tests/test_analytics_service.py

import pytest
from datetime import datetime, timedelta
from backend.services.analytics_service import AnalyticsService

@pytest.mark.asyncio
async def test_get_kpi_overview(mock_db_session, sample_instagram_account):
    """Test obtención de KPIs."""

    service = AnalyticsService(mock_db_session)

    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()

    kpis = await service.get_kpi_overview(
        sample_instagram_account.id,
        start_date,
        end_date,
        compare=False
    )

    assert 'reach' in kpis
    assert 'profile_views' in kpis
    assert 'interactions' in kpis
    assert 'followers' in kpis
    assert 'engagement_rate' in kpis

    assert isinstance(kpis['reach']['value'], int)
    assert isinstance(kpis['engagement_rate']['value'], float)

@pytest.mark.asyncio
async def test_best_posting_times_calculation(sample_online_followers, sample_performance_data):
    """Test algoritmo de mejores horarios."""

    service = AnalyticsService(None)

    best_times = service._calculate_best_posting_times(
        sample_online_followers,
        sample_performance_data
    )

    assert len(best_times) == 5
    assert all('score' in t for t in best_times)
    assert all('day_of_week' in t for t in best_times)
    assert best_times[0]['score'] >= best_times[1]['score']  # Ordenados desc
```

### Frontend Tests

```typescript
// __tests__/components/analytics/KPICard.test.tsx

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KPICard } from '../../../components/analytics/cards/KPICard';

describe('KPICard', () => {
  it('should render with basic props', () => {
    render(
      <KPICard
        title="Alcance"
        value="125.5K"
        icon="bi-broadcast"
        color="primary"
      />
    );

    expect(screen.getByText('Alcance')).toBeInTheDocument();
    expect(screen.getByText('125.5K')).toBeInTheDocument();
  });

  it('should display change indicator when provided', () => {
    render(
      <KPICard
        title="Alcance"
        value="125.5K"
        change="+12.5%"
        trend="up"
        icon="bi-broadcast"
        color="primary"
      />
    );

    expect(screen.getByText('+12.5%')).toBeInTheDocument();
    const changeElement = screen.getByText('+12.5%').closest('.kpi-change');
    expect(changeElement).toHaveClass('kpi-change-up');
  });
});
```

### E2E Tests

```typescript
// tests/e2e/analytics-dashboard.spec.ts

import { test, expect } from '@playwright/test';

test.describe('Advanced Analytics Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'password123');
    await page.click('button[type="submit"]');

    // Navigate to analytics
    await page.click('a[href="/analytics"]');
    await page.waitForURL('**/analytics');
  });

  test('should display all KPI cards', async ({ page }) => {
    await expect(page.locator('.kpi-card')).toHaveCount(5);

    await expect(page.getByText('Alcance')).toBeVisible();
    await expect(page.getByText('Visitas al Perfil')).toBeVisible();
    await expect(page.getByText('Interacciones')).toBeVisible();
    await expect(page.getByText('Seguidores')).toBeVisible();
    await expect(page.getByText('Engagement Rate')).toBeVisible();
  });

  test('should filter by date range', async ({ page }) => {
    // Click date range picker
    await page.click('.date-range-picker');

    // Select "Últimos 30 días"
    await page.click('text=Últimos 30 días');

    // Wait for data to refresh
    await page.waitForResponse(resp =>
      resp.url().includes('/api/analytics/overview') && resp.status() === 200
    );

    // Verify charts updated
    await expect(page.locator('.follower-growth-chart')).toBeVisible();
  });

  test('should display top posts with tabs', async ({ page }) => {
    // Scroll to top posts section
    await page.locator('.top-posts-section').scrollIntoViewIfNeeded();

    // Verify tabs
    await expect(page.getByText('Interacciones')).toBeVisible();
    await expect(page.getByText('Alcance')).toBeVisible();
    await expect(page.getByText('Guardados')).toBeVisible();

    // Click "Alcance" tab
    await page.click('text=Alcance');

    // Verify posts updated
    await expect(page.locator('.top-post-card')).toHaveCount(5);
  });

  test('should display scheduled posts section at bottom', async ({ page }) => {
    // Scroll to bottom
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    // Verify scheduled posts section
    await expect(page.getByText('Próximos Posts Programados')).toBeVisible();

    // Verify at least one scheduled post
    const scheduledPosts = page.locator('.scheduled-post-item');
    await expect(scheduledPosts.first()).toBeVisible();
  });
});
```

---

## 📝 Notas de Implementación

### Rate Limits de Instagram API

Instagram tiene límites estrictos en las llamadas al API:

```python
# utils/rate_limiter.py

from datetime import datetime, timedelta
from typing import Dict
import asyncio

class InstagramRateLimiter:
    """Manejador de rate limits de Instagram API."""

    def __init__(self):
        self.calls_per_hour = {}  # {endpoint: [(timestamp, count)]}
        self.max_calls_per_hour = 200

    async def check_and_wait(self, endpoint: str):
        """Verifica rate limit y espera si es necesario."""

        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Limpiar llamadas antiguas
        if endpoint in self.calls_per_hour:
            self.calls_per_hour[endpoint] = [
                (ts, count) for ts, count in self.calls_per_hour[endpoint]
                if ts > hour_ago
            ]

        # Contar llamadas en última hora
        total_calls = sum(
            count for _, count in self.calls_per_hour.get(endpoint, [])
        )

        # Si excede límite, esperar
        if total_calls >= self.max_calls_per_hour:
            oldest_call = min(ts for ts, _ in self.calls_per_hour[endpoint])
            wait_time = (oldest_call + timedelta(hours=1) - now).total_seconds()

            if wait_time > 0:
                print(f"Rate limit reached. Waiting {wait_time}s...")
                await asyncio.sleep(wait_time)

        # Registrar llamada
        if endpoint not in self.calls_per_hour:
            self.calls_per_hour[endpoint] = []
        self.calls_per_hour[endpoint].append((now, 1))
```

### Caching Strategy

Para reducir llamadas al API y mejorar performance:

```python
# utils/cache_utils.py

from datetime import datetime, timedelta
from typing import Optional, Any
import json

class AnalyticsCache:
    """Sistema de caché para analytics."""

    @staticmethod
    async def get(key: str, db) -> Optional[Any]:
        """Obtiene valor del caché."""

        query = """
            SELECT data, expires_at
            FROM analytics_cache
            WHERE cache_key = :key
              AND expires_at > NOW()
        """

        result = await db.execute(text(query), {'key': key})
        row = result.fetchone()

        if row:
            return json.loads(row['data'])
        return None

    @staticmethod
    async def set(key: str, data: Any, ttl_minutes: int, db):
        """Guarda valor en caché."""

        expires_at = datetime.now() + timedelta(minutes=ttl_minutes)

        query = """
            INSERT INTO analytics_cache (cache_key, data, expires_at)
            VALUES (:key, :data, :expires_at)
            ON CONFLICT (cache_key)
            DO UPDATE SET data = :data, expires_at = :expires_at
        """

        await db.execute(
            text(query),
            {
                'key': key,
                'data': json.dumps(data),
                'expires_at': expires_at
            }
        )
        await db.commit()

# Uso en servicio
async def get_kpi_overview(self, ...):
    cache_key = f"kpis_{instagram_account_id}_{start_date}_{end_date}"

    # Intentar obtener del caché
    cached_data = await AnalyticsCache.get(cache_key, self.db)
    if cached_data:
        return cached_data

    # Si no está en caché, calcular
    kpis = await self._calculate_kpis(...)

    # Guardar en caché (TTL: 15 minutos)
    await AnalyticsCache.set(cache_key, kpis, 15, self.db)

    return kpis
```

### Error Handling

```python
# utils/error_handler.py

class InstagramAPIError(Exception):
    """Error de Instagram API."""
    pass

class RateLimitError(InstagramAPIError):
    """Rate limit excedido."""
    pass

class InsufficientDataError(Exception):
    """Datos insuficientes para generar insights."""
    pass

# En servicios
try:
    insights_data = await instagram_service.get_insights(...)
except RateLimitError:
    # Usar datos cacheados o retornar partial data
    logger.warning("Rate limit reached, using cached data")
    insights_data = await get_cached_insights(...)
except InstagramAPIError as e:
    logger.error(f"Instagram API error: {e}")
    raise HTTPException(status_code=502, detail="Instagram API unavailable")
```

---

## ✅ Checklist de Implementación

### Fase 1: Backend
- [ ] Crear migraciones de BD para nuevas tablas
- [ ] Implementar `AnalyticsService` con todos los métodos
- [ ] Implementar `InstagramInsightsService` con rate limiting
- [ ] Implementar `InsightsGeneratorService` con algoritmos
- [ ] Crear endpoints API con documentación
- [ ] Implementar sistema de caché
- [ ] Implementar jobs de sincronización diaria
- [ ] Tests unitarios (80%+ coverage)
- [ ] Tests de integración

### Fase 2: Frontend - Componentes Base
- [ ] Crear componentes reutilizables (KPICard, Charts, etc.)
- [ ] Implementar `DateRangePicker` con presets
- [ ] Implementar loading skeletons
- [ ] Implementar error boundaries
- [ ] Tests de componentes con Vitest

### Fase 3: Frontend - Secciones
- [ ] Sección 1: KPIs
- [ ] Sección 2: Audiencia (Crecimiento, Demografía, Actividad, Ubicaciones)
- [ ] Sección 3: Rendimiento del Contenido
- [ ] Sección 4: Top Posts con tabs
- [ ] Sección 5: Insights Accionables
- [ ] Sección 6: Próximos Posts
- [ ] Responsive design para todas las secciones
- [ ] Tests de integración

### Fase 4: Testing y Deploy
- [ ] Tests E2E con Playwright (scenarios completos)
- [ ] Performance testing (Lighthouse score > 90)
- [ ] Accessibility testing (WCAG 2.1 AA)
- [ ] Deploy a producción
- [ ] Monitoreo de errores (Sentry)
- [ ] Analytics de uso (Google Analytics)

---

## 📊 Métricas de Éxito

### KPIs del Proyecto

1. **Performance:**
   - Tiempo de carga inicial < 3s
   - Lighthouse Performance > 90
   - Time to Interactive < 5s

2. **Cobertura de Tests:**
   - Backend: > 80%
   - Frontend: > 75%
   - E2E: Scenarios críticos cubiertos

3. **Usabilidad:**
   - Tasa de adopción del nuevo dashboard > 70%
   - Tiempo promedio en dashboard > 5 min
   - Bounce rate < 30%

4. **Técnicas:**
   - Error rate < 1%
   - API response time p95 < 2s
   - Uptime > 99.5%

---

## 🎓 Conclusión

Este plan de implementación proporciona una hoja de ruta completa para desarrollar un Dashboard de Analytics Avanzado de nivel profesional para SocialLab.

**Puntos clave:**
✅ Arquitectura escalable y mantenible
✅ Integración completa con Instagram Insights API
✅ 15+ métricas accionables
✅ 8+ visualizaciones interactivas
✅ Sistema de caché para performance
✅ Testing comprehensivo
✅ Documentación detallada

**Próximos pasos:**
1. Revisar y aprobar el plan
2. Crear tickets en el sistema de gestión de proyectos
3. Asignar recursos y timeline
4. Comenzar Fase 1: Backend

---

**Documento creado por:** Claude (Anthropic)
**Fecha:** 2025-01-20
**Versión:** 1.0
**Estado:** ✅ Listo para implementación
