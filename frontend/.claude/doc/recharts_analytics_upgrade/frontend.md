# Plan de Arquitectura Frontend - Recharts Analytics Upgrade

## Análisis del Estado Actual

### Componente Analytics.tsx
- **Ubicación**: `/Users/joseangel/Proyectos/SocialLab/frontend/src/components/analytics/Analytics.tsx`
- **Líneas**: 296 líneas totales
- **Stack actual**: React 19 + TypeScript + CSS Modules
- **Problema**: Usa barras CSS básicas en lugar de gráficos profesionales

### Secciones que requieren upgrade:

1. **Engagement Trend** (líneas 203-230)
   - Implementación actual: Barras CSS con altura calculada manualmente
   - Datos: `engagement_trend: Array<{ date: string; likes: number; comments: number }>`
   - Necesita: LineChart profesional con múltiples series

2. **Best Posting Times** (líneas 256-275)
   - Implementación actual: Barras horizontales CSS simples
   - Datos: `best_posting_times: Array<{ time: string; avg_engagement: number }>`
   - Necesita: BarChart con mejor visualización

---

## Arquitectura de Componentes Propuesta

### Estructura de Carpetas

```
/Users/joseangel/Proyectos/SocialLab/frontend/src/components/analytics/
├── Analytics.tsx                    # Componente principal (refactorizado)
├── Analytics.css                     # Estilos generales (existente)
├── charts/
│   ├── EngagementTrendChart.tsx     # NUEVO: LineChart con Recharts
│   ├── BestTimesChart.tsx           # NUEVO: BarChart con Recharts
│   ├── ChartContainer.tsx           # NUEVO: Wrapper responsive común
│   └── chartConfig.ts               # NUEVO: Configuración compartida
└── types/
    └── analytics.types.ts           # NUEVO: Tipos TypeScript centralizados
```

---

## Interfaces TypeScript

### `/types/analytics.types.ts`

```typescript
// Datos del backend (ya definidos en Analytics.tsx)
export interface EngagementTrendItem {
  date: string;
  likes: number;
  comments: number;
  engagement?: number; // Calculado en el backend
}

export interface BestPostingTime {
  time: string;           // Formato: "14:00" o "14h"
  avg_engagement: number; // Porcentaje: 5.2
  hour?: string;          // Alternativo del backend
  avg_engagement_rate?: number; // Alternativo del backend
  posts_count?: number;   // Opcional: cantidad de posts en ese horario
}

// Props para componentes de charts
export interface EngagementTrendChartProps {
  data: EngagementTrendItem[];
  height?: number;
  showLegend?: boolean;
  showGrid?: boolean;
}

export interface BestTimesChartProps {
  data: BestPostingTime[];
  height?: number;
  maxValue?: number;
  showValues?: boolean;
}

export interface ChartContainerProps {
  children: React.ReactNode;
  title: string;
  icon?: string;
  className?: string;
}
```

---

## Componente 1: EngagementTrendChart

### `/charts/EngagementTrendChart.tsx`

```typescript
import React, { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import { EngagementTrendChartProps } from '../types/analytics.types';
import { formatChartDate, formatNumber } from './chartConfig';

const EngagementTrendChart: React.FC<EngagementTrendChartProps> = ({
  data,
  height = 280,
  showLegend = true,
  showGrid = true
}) => {
  // Transformar datos para Recharts
  const chartData = useMemo(() => {
    return data.map((item) => ({
      date: formatChartDate(item.date),
      likes: item.likes,
      comments: item.comments,
      total: item.likes + item.comments
    }));
  }, [data]);

  // Custom Tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || !payload.length) return null;

    return (
      <div className="recharts-custom-tooltip">
        <p className="tooltip-label">{label}</p>
        <div className="tooltip-content">
          <div className="tooltip-item likes">
            <span className="tooltip-icon">❤️</span>
            <span className="tooltip-value">{formatNumber(payload[0]?.value || 0)} likes</span>
          </div>
          <div className="tooltip-item comments">
            <span className="tooltip-icon">💬</span>
            <span className="tooltip-value">{formatNumber(payload[1]?.value || 0)} comments</span>
          </div>
          <div className="tooltip-item total">
            <span className="tooltip-icon">📊</span>
            <span className="tooltip-value">{formatNumber(payload[2]?.value || 0)} total</span>
          </div>
        </div>
      </div>
    );
  };

  if (!data || data.length === 0) {
    return (
      <div className="chart-empty-state">
        <p>No hay datos de tendencia disponibles</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart
        data={chartData}
        margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
      >
        {showGrid && (
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255, 255, 255, 0.1)"
            vertical={false}
          />
        )}
        <XAxis
          dataKey="date"
          stroke="#888"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="#888"
          fontSize={12}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => formatNumber(value)}
        />
        <Tooltip content={<CustomTooltip />} />
        {showLegend && (
          <Legend
            wrapperStyle={{
              paddingTop: '20px',
              fontSize: '14px'
            }}
            iconType="line"
          />
        )}
        <Line
          type="monotone"
          dataKey="likes"
          stroke="#667eea"
          strokeWidth={3}
          dot={{ fill: '#667eea', r: 4 }}
          activeDot={{ r: 6, fill: '#667eea' }}
          name="Likes"
        />
        <Line
          type="monotone"
          dataKey="comments"
          stroke="#764ba2"
          strokeWidth={3}
          dot={{ fill: '#764ba2', r: 4 }}
          activeDot={{ r: 6, fill: '#764ba2' }}
          name="Comentarios"
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default EngagementTrendChart;
```

### Estilos para EngagementTrendChart (agregar a Analytics.css)

```css
/* Recharts Custom Tooltip */
.recharts-custom-tooltip {
  background: rgba(0, 0, 0, 0.9);
  border: 2px solid #667eea;
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.tooltip-label {
  color: #fff;
  font-weight: 600;
  margin: 0 0 8px 0;
  font-size: 0.875rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  padding-bottom: 6px;
}

.tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tooltip-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
}

.tooltip-icon {
  font-size: 1rem;
}

.tooltip-value {
  color: #e8e9ed;
  font-weight: 500;
}

.chart-empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 280px;
  color: var(--text-muted);
  font-size: 0.875rem;
  background: var(--background-input);
  border-radius: var(--radius-md);
}
```

---

## Componente 2: BestTimesChart

### `/charts/BestTimesChart.tsx`

```typescript
import React, { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import { BestTimesChartProps } from '../types/analytics.types';

const BestTimesChart: React.FC<BestTimesChartProps> = ({
  data,
  height = 300,
  maxValue,
  showValues = true
}) => {
  // Normalizar datos del backend
  const chartData = useMemo(() => {
    return data.map((item) => ({
      time: item.time || item.hour || '00:00',
      engagement: item.avg_engagement || item.avg_engagement_rate || 0,
      postsCount: item.posts_count || 0
    }))
    .sort((a, b) => {
      // Ordenar por hora
      const timeA = parseInt(a.time.split(':')[0]);
      const timeB = parseInt(b.time.split(':')[0]);
      return timeA - timeB;
    });
  }, [data]);

  // Calcular color según engagement
  const getBarColor = (engagement: number) => {
    const max = maxValue || Math.max(...chartData.map(d => d.engagement));
    const percentage = (engagement / max) * 100;

    if (percentage >= 80) return '#667eea'; // Mejor hora
    if (percentage >= 60) return '#764ba2'; // Buena hora
    if (percentage >= 40) return '#8e7cc3'; // Normal
    return '#a8a8b3'; // Baja engagement
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null;

    const data = payload[0].payload;
    return (
      <div className="recharts-custom-tooltip">
        <p className="tooltip-label">Hora: {data.time}</p>
        <div className="tooltip-content">
          <div className="tooltip-item">
            <span className="tooltip-icon">📈</span>
            <span className="tooltip-value">{data.engagement.toFixed(1)}% engagement</span>
          </div>
          {data.postsCount > 0 && (
            <div className="tooltip-item">
              <span className="tooltip-icon">📝</span>
              <span className="tooltip-value">{data.postsCount} posts</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  const CustomLabel = (props: any) => {
    const { x, y, width, value } = props;
    if (!showValues) return null;

    return (
      <text
        x={x + width / 2}
        y={y - 5}
        fill="#e8e9ed"
        textAnchor="middle"
        fontSize={11}
        fontWeight={600}
      >
        {value.toFixed(1)}%
      </text>
    );
  };

  if (!data || data.length === 0) {
    return (
      <div className="chart-empty-state">
        <p>No hay suficientes datos para análisis de horarios</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={chartData}
        margin={{ top: 20, right: 20, left: 0, bottom: 5 }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(255, 255, 255, 0.1)"
          vertical={false}
        />
        <XAxis
          dataKey="time"
          stroke="#888"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="#888"
          fontSize={12}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => `${value}%`}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar
          dataKey="engagement"
          radius={[8, 8, 0, 0]}
          label={<CustomLabel />}
        >
          {chartData.map((entry, index) => (
            <Cell
              key={`cell-${index}`}
              fill={getBarColor(entry.engagement)}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
};

export default BestTimesChart;
```

---

## Componente 3: ChartContainer (Wrapper Común)

### `/charts/ChartContainer.tsx`

```typescript
import React from 'react';
import { ChartContainerProps } from '../types/analytics.types';

const ChartContainer: React.FC<ChartContainerProps> = ({
  children,
  title,
  icon = 'bi-graph-up',
  className = ''
}) => {
  return (
    <div className={`analytics-section ${className}`}>
      <h3>
        <i className={`bi ${icon} me-2`}></i>
        {title}
      </h3>
      <div className="chart-wrapper">
        {children}
      </div>
    </div>
  );
};

export default ChartContainer;
```

---

## Configuración Compartida

### `/charts/chartConfig.ts`

```typescript
// Utilidades para formateo en charts
export const formatChartDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  return date.toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short'
  });
};

export const formatNumber = (num: number): string => {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return num.toString();
};

// Colores del tema
export const CHART_COLORS = {
  primary: '#667eea',
  secondary: '#764ba2',
  gradient: ['#667eea', '#764ba2'],
  success: '#10b981',
  warning: '#f59e0b',
  danger: '#ef4444',
  muted: '#a8a8b3'
};

// Configuración de grid común
export const GRID_CONFIG = {
  strokeDasharray: '3 3',
  stroke: 'rgba(255, 255, 255, 0.1)',
  vertical: false
};

// Configuración de ejes común
export const AXIS_CONFIG = {
  stroke: '#888',
  fontSize: 12,
  tickLine: false,
  axisLine: false
};
```

---

## Refactorización de Analytics.tsx

### Cambios a realizar:

**1. Importar nuevos componentes (línea 2-4)**
```typescript
import React, { useState, useEffect, useRef } from 'react';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './Analytics.css';
import EngagementTrendChart from './charts/EngagementTrendChart';
import BestTimesChart from './charts/BestTimesChart';
import ChartContainer from './charts/ChartContainer';
```

**2. Reemplazar sección Engagement Trend (líneas 203-230)**

**ANTES:**
```typescript
{/* Engagement Trend */}
<div className="analytics-section">
  <h3><i className="bi bi-graph-up me-2"></i>Tendencia de Engagement</h3>
  <div className="trend-chart">
    {analytics.engagement_trend.map((day, index) => {
      const maxLikes = Math.max(...analytics.engagement_trend.map(d => d.likes));
      const height = (day.likes / maxLikes) * 100;
      return (
        <div key={index} className="chart-bar-container">
          {/* ... código de barras CSS ... */}
        </div>
      );
    })}
  </div>
</div>
```

**DESPUÉS:**
```typescript
{/* Engagement Trend - UPGRADED */}
<ChartContainer
  title="Tendencia de Engagement"
  icon="bi-graph-up"
>
  <EngagementTrendChart
    data={analytics.engagement_trend}
    height={280}
    showLegend={true}
    showGrid={true}
  />
</ChartContainer>
```

**3. Reemplazar sección Best Posting Times (líneas 256-275)**

**ANTES:**
```typescript
{/* Best Posting Times */}
<div className="analytics-section">
  <h3><i className="bi bi-clock me-2"></i>Mejores Horarios para Publicar</h3>
  <div className="best-times-list">
    {analytics.best_posting_times.map((time, index) => (
      <div key={index} className="time-item">
        <div className="time-label"><i className="bi bi-clock me-1"></i>{time.time}</div>
        <div className="time-bar-container">
          <div className="time-bar" style={{ width: `${(time.avg_engagement / 6) * 100}%` }}></div>
        </div>
        <div className="time-value">{time.avg_engagement}% engagement</div>
      </div>
    ))}
  </div>
</div>
```

**DESPUÉS:**
```typescript
{/* Best Posting Times - UPGRADED */}
<ChartContainer
  title="Mejores Horarios para Publicar"
  icon="bi-clock"
>
  <BestTimesChart
    data={analytics.best_posting_times}
    height={300}
    showValues={true}
  />
</ChartContainer>
```

---

## CSS Adicional para Recharts

### Agregar a `/analytics/Analytics.css`

```css
/* Chart Wrapper */
.chart-wrapper {
  padding: 1rem 0;
  min-height: 280px;
}

/* Responsive Charts */
@media (max-width: 768px) {
  .chart-wrapper {
    padding: 0.5rem 0;
    min-height: 240px;
  }

  .recharts-custom-tooltip {
    padding: 10px 14px;
  }

  .tooltip-label {
    font-size: 0.8rem;
  }

  .tooltip-item {
    font-size: 0.75rem;
  }
}

@media (max-width: 480px) {
  .chart-wrapper {
    min-height: 200px;
  }

  .recharts-custom-tooltip {
    padding: 8px 12px;
  }
}

/* Recharts Legend Customization */
.recharts-legend-wrapper {
  padding-top: 20px !important;
}

.recharts-legend-item {
  margin-right: 20px !important;
}

/* Recharts Surface (container principal) */
.recharts-surface {
  overflow: visible !important;
}

/* Animaciones suaves */
.recharts-bar-rectangle,
.recharts-line-curve {
  transition: all 0.3s ease;
}

/* Hover effects */
.recharts-bar-rectangle:hover {
  opacity: 0.8;
  filter: brightness(1.2);
}
```

---

## Plan de Implementación por Pasos

### Fase 1: Setup (10 min)
1. ✅ Crear estructura de carpetas
2. ✅ Crear archivo `types/analytics.types.ts`
3. ✅ Crear archivo `charts/chartConfig.ts`

### Fase 2: Componentes Base (30 min)
4. ✅ Implementar `ChartContainer.tsx`
5. ✅ Implementar `EngagementTrendChart.tsx`
6. ✅ Implementar `BestTimesChart.tsx`

### Fase 3: Estilos (15 min)
7. ✅ Agregar estilos CSS para tooltips
8. ✅ Agregar estilos responsive
9. ✅ Ajustar colores al tema dark

### Fase 4: Refactorización (20 min)
10. ✅ Actualizar imports en `Analytics.tsx`
11. ✅ Reemplazar sección Engagement Trend
12. ✅ Reemplazar sección Best Posting Times
13. ✅ Remover CSS antiguo no usado

### Fase 5: Testing (15 min)
14. ✅ Verificar datos se renderizan correctamente
15. ✅ Probar responsive en mobile/tablet
16. ✅ Verificar tooltips funcionan
17. ✅ Probar con datos vacíos

**Tiempo total estimado**: 90 minutos

---

## Mejoras Adicionales Opcionales

### 1. Modo de Vista Toggle
```typescript
// En Analytics.tsx
const [chartView, setChartView] = useState<'line' | 'bar'>('line');

// Botón toggle
<div className="chart-view-toggle">
  <button onClick={() => setChartView('line')}>Líneas</button>
  <button onClick={() => setChartView('bar')}>Barras</button>
</div>
```

### 2. Export Chart como Imagen
```typescript
import { toBlob } from 'recharts-to-image';

const handleExportChart = async () => {
  const chartElement = document.querySelector('.recharts-wrapper');
  if (chartElement) {
    const blob = await toBlob(chartElement as HTMLElement);
    // Descargar blob
  }
};
```

### 3. Animaciones Avanzadas
```typescript
// En LineChart
<Line
  type="monotone"
  dataKey="likes"
  stroke="#667eea"
  strokeWidth={3}
  animationDuration={800}
  animationEasing="ease-in-out"
/>
```

### 4. Zoom y Pan
```typescript
import { Brush } from 'recharts';

// Dentro de LineChart
<Brush
  dataKey="date"
  height={30}
  stroke="#667eea"
/>
```

---

## Compatibilidad TypeScript

### Versiones requeridas:
- ✅ React: 19.1.0 (instalado)
- ✅ TypeScript: 5.8.3 (instalado)
- ✅ Recharts: 3.3.0 (instalado)

### Types adicionales necesarios:

```bash
npm install --save-dev @types/recharts
```

---

## Pruebas de Accesibilidad

### ARIA Labels para charts:
```typescript
<ResponsiveContainer
  width="100%"
  height={height}
  role="img"
  aria-label="Gráfico de tendencia de engagement"
>
```

### Keyboard Navigation:
- Recharts soporta navegación por teclado por defecto
- Los tooltips son accesibles via hover y focus

---

## Performance Considerations

### 1. Memoización de datos transformados
```typescript
const chartData = useMemo(() => {
  return data.map(/* transformación */);
}, [data]);
```

### 2. Lazy Loading (si analytics es pesado)
```typescript
const EngagementTrendChart = lazy(() => import('./charts/EngagementTrendChart'));

<Suspense fallback={<ChartLoadingSkeleton />}>
  <EngagementTrendChart data={data} />
</Suspense>
```

### 3. Debounce en resize
```typescript
useEffect(() => {
  const handleResize = debounce(() => {
    // Recalcular dimensiones
  }, 300);

  window.addEventListener('resize', handleResize);
  return () => window.removeEventListener('resize', handleResize);
}, []);
```

---

## Checklist Final

### Antes de commit:
- [ ] Todos los componentes TypeScript sin errores
- [ ] Estilos CSS aplicados correctamente
- [ ] Responsive funciona en mobile (< 768px)
- [ ] Tooltips visibles y legibles
- [ ] Datos del backend se mapean correctamente
- [ ] Empty states funcionan
- [ ] No hay console.errors en navegador
- [ ] Colores coherentes con tema dark
- [ ] Animaciones suaves (no lag)
- [ ] Analytics.tsx refactorizado completamente

---

## Archivos a Crear/Modificar

### Nuevos archivos (5):
1. `/src/components/analytics/types/analytics.types.ts`
2. `/src/components/analytics/charts/chartConfig.ts`
3. `/src/components/analytics/charts/ChartContainer.tsx`
4. `/src/components/analytics/charts/EngagementTrendChart.tsx`
5. `/src/components/analytics/charts/BestTimesChart.tsx`

### Archivos a modificar (2):
1. `/src/components/analytics/Analytics.tsx` (remover líneas 203-230 y 256-275)
2. `/src/components/analytics/Analytics.css` (agregar estilos Recharts)

---

## Ejemplo de Resultado Final

### Analytics.tsx refactorizado (fragmento relevante):

```typescript
// ... imports y lógica existente ...

return (
  <div className="analytics-container">
    {/* Header y Overview Stats - SIN CAMBIOS */}

    {/* Engagement Trend - NUEVO */}
    <ChartContainer title="Tendencia de Engagement" icon="bi-graph-up">
      <EngagementTrendChart
        data={analytics.engagement_trend}
        height={280}
        showLegend={true}
        showGrid={true}
      />
    </ChartContainer>

    {/* Two Column Layout */}
    <div className="analytics-columns">
      {/* Top Posts - SIN CAMBIOS */}
      <div className="analytics-section">
        {/* ... código existente ... */}
      </div>

      {/* Best Posting Times - NUEVO */}
      <ChartContainer title="Mejores Horarios para Publicar" icon="bi-clock">
        <BestTimesChart
          data={analytics.best_posting_times}
          height={300}
          showValues={true}
        />
      </ChartContainer>
    </div>

    {/* Insights - SIN CAMBIOS */}
  </div>
);
```

---

## Ventajas de esta Arquitectura

### 1. Separación de Responsabilidades
- Analytics.tsx: Lógica de negocio y data fetching
- Charts: Presentación y visualización
- Types: Contratos TypeScript
- Config: Utilidades compartidas

### 2. Reutilización
- ChartContainer puede usarse en Dashboard u otros componentes
- chartConfig.ts centraliza formateo
- Tipos exportables a otros módulos

### 3. Mantenibilidad
- Un bug en gráficos solo afecta a charts/
- Fácil agregar nuevos charts sin tocar Analytics.tsx
- Tests unitarios por componente

### 4. Performance
- Memoización previene re-renders innecesarios
- ResponsiveContainer solo renderiza cuando cambia tamaño
- Datos transformados una sola vez

### 5. Escalabilidad
- Agregar AreaChart, PieChart, etc. es trivial
- Migrar a otra librería (Victory, Nivo) solo afecta charts/
- Temas y colores centralizados en chartConfig.ts

---

## Próximos Pasos

Una vez implementado este upgrade, se pueden considerar:

1. **Agregar más visualizaciones**:
   - PieChart para distribución de tipos de posts
   - AreaChart para alcance vs engagement
   - RadarChart para análisis multidimensional

2. **Dashboard principal**:
   - Reutilizar estos charts en Dashboard.tsx (líneas 376-396)
   - Crear versión mini de charts para cards

3. **Interactividad avanzada**:
   - Click en barra para filtrar posts de esa hora
   - Click en punto del LineChart para ver post específico
   - Zoom temporal para análisis detallado

4. **Exportación**:
   - PDF report con charts
   - CSV de datos
   - Imágenes PNG para redes sociales

---

**Documento creado**: 2025-10-18
**Autor**: Claude Code (Frontend Specialist)
**Proyecto**: SocialLab - Analytics Recharts Upgrade
**Stack**: React 19 + TypeScript + Recharts 3.3.0
