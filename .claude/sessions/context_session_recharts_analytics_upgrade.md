# Session Context: Recharts Analytics Upgrade

**Feature:** recharts_analytics_upgrade
**Fecha inicio:** 2025-01-18
**Estado:** 🔵 Planning

---

## 📋 Objetivo

Actualizar el componente Analytics.tsx para usar Recharts en lugar de barras CSS básicas, proporcionando visualizaciones profesionales e interactivas.

---

## 🎯 Alcance

### Backend
- ✅ **Ya existe** - No requiere cambios
- Endpoint: `GET /api/instagram/analytics/cached-overview?days={days}`
- Datos perfectos para Recharts

### Frontend
- ❌ **Requiere actualización**
- Componente actual: `frontend/src/components/analytics/Analytics.tsx`
- Usa barras CSS básicas (líneas 203-230)
- Recharts ya está en package.json pero NO se usa

### Testing
- ❌ **Requiere nuevos tests**
- Tests unitarios para componentes de charts
- Tests de integración para Analytics.tsx

### UI/UX
- ❌ **Requiere análisis**
- Mejora de interactividad
- Tooltips y animaciones
- Responsive design

---

## 🔍 Estado Actual

### Datos del Backend

Endpoint actual retorna:
```json
{
  "engagement_trend": [
    { "date": "2025-01-01", "likes": 120, "comments": 15, "engagement": 135 }
  ],
  "best_posting_times": [
    { "hour": "14:00", "avg_engagement_rate": 4.5, "posts_count": 8 }
  ],
  "top_posts": [...]
}
```

### Componente Actual

`Analytics.tsx` usa barras CSS:
```tsx
<div className="trend-chart">
  {analytics.engagement_trend.map((day, index) => {
    const height = (day.likes / maxLikes) * 100;
    return (
      <div className="chart-bar" style={{ height: `${height}%` }}>
        ...
      </div>
    );
  })}
</div>
```

**Problemas:**
- ❌ No hay tooltips interactivos
- ❌ No hay animaciones
- ❌ Pobre experiencia mobile
- ❌ No hay leyendas
- ❌ Difícil de mantener

---

## 📦 Dependencias

### Ya instaladas
- ✅ `recharts` (verificar versión en package.json)
- ✅ `react` ^19.1.0
- ✅ `react-dom` ^19.1.0

### Por verificar
- Versión de Recharts compatible con React 19

---

## 🎨 Componentes a Crear

### 1. EngagementTrendChart.tsx
**Tipo:** LineChart
**Datos:** `engagement_trend`
**Props:**
- `data: EngagementTrendItem[]`
- `timeRange?: string`

### 2. BestTimesChart.tsx
**Tipo:** BarChart
**Datos:** `best_posting_times`
**Props:**
- `data: BestPostingTime[]`

### 3. ContentTypeChart.tsx (opcional)
**Tipo:** PieChart
**Datos:** Por tipo de contenido (FEED, REELS, STORY)
**Props:**
- `data: ContentTypeData[]`

---

## 🔄 Plan Inicial

1. **Análisis de compatibilidad**
   - Verificar versión de Recharts
   - Compatibilidad con React 19

2. **Crear componentes de charts**
   - EngagementTrendChart
   - BestTimesChart

3. **Refactorizar Analytics.tsx**
   - Reemplazar barras CSS
   - Integrar nuevos componentes

4. **Testing**
   - Tests unitarios
   - Tests de integración
   - Snapshot tests

5. **UI/UX**
   - Responsive design
   - Tooltips
   - Animaciones
   - Colores Tailwind

---

## 👥 Equipo Seleccionado

### Agentes a Consultar (ejecución paralela):

1. **react-frontend-architect** 🔵
   - Arquitectura de componentes Recharts
   - Estructura de carpetas
   - Props e interfaces TypeScript
   - Integración con Analytics.tsx
   - Output: `.claude/doc/recharts_analytics_upgrade/frontend.md`

2. **react-test-engineer** 🟡
   - Estrategia de testing para charts
   - Tests unitarios para componentes
   - Tests de integración
   - Mocking de Recharts
   - Output: `.claude/doc/recharts_analytics_upgrade/frontend_testing.md`

3. **ui-ux-analyzer** 🎨
   - Análisis de mejoras visuales
   - Color palette (Tailwind)
   - Responsive design
   - Tooltips y animaciones
   - Accesibilidad
   - Output: `.claude/doc/recharts_analytics_upgrade/ui_analysis.md`

### Agentes NO necesarios:
- ❌ api-designer - Backend no requiere cambios
- ❌ backend-architect - Backend perfecto
- ❌ qa-criteria-validator - No hay nuevo flujo E2E

---

## 📝 Notas

- Recharts ya está instalado pero no se usa
- Backend perfecto, no requiere cambios
- Foco en UX y testing

---

**Última actualización:** 2025-01-18 18:30
