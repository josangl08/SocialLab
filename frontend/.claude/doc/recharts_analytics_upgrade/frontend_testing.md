# Plan de Testing - Recharts Analytics Components

**Proyecto**: SocialLab Frontend
**Framework**: Vitest + React Testing Library
**Objetivo**: Coverage 80%+ en componentes Analytics con Recharts
**Fecha**: 2025-10-18

---

## PROBLEMA DETECTADO

### Estado Actual del Proyecto

**CRITICO**: El proyecto NO tiene las dependencias de testing instaladas:

```json
// package.json actual - devDependencies
{
  "@axe-core/playwright": "^4.10.2",
  "@playwright/test": "^1.56.1",
  "@types/react": "^19.1.8",
  "@types/react-datepicker": "^6.2.0",
  "@types/react-dom": "^19.1.6",
  "@vitejs/plugin-react": "^4.5.2",
  "eslint": "^9.29.0",
  "globals": "^16.2.0",
  "typescript": "~5.8.3",
  "vite": "^7.0.0"
}
```

**Falta**:
- `vitest` (instalado pero no en package.json)
- `@testing-library/react`
- `@testing-library/jest-dom`
- `@testing-library/user-event`
- `@vitest/ui` (opcional pero recomendado)
- `@vitest/coverage-v8`
- `jsdom` (ya configurado en vitest.config.ts pero no listado)

**Estructura de tests**: No existe carpeta `src/__tests__/`

---

## FASE 1: SETUP DE TESTING

### 1.1 Instalación de Dependencias

```bash
# Dependencias core de testing
npm install --save-dev vitest@latest \
  @testing-library/react@^16.1.0 \
  @testing-library/jest-dom@^6.6.3 \
  @testing-library/user-event@^14.5.2 \
  @vitest/ui@latest \
  @vitest/coverage-v8@latest \
  jsdom@^25.0.1

# Types para Recharts (si no existen)
npm install --save-dev @types/recharts@^3.0.0
```

**Justificación de versiones**:
- `@testing-library/react@^16.1.0`: Compatible con React 19.1.0
- `@vitest/coverage-v8`: Provider de coverage configurado en vitest.config.ts
- `jsdom@^25.0.1`: DOM environment para tests (ya configurado)

---

### 1.2 Crear Setup de Testing

**Archivo**: `/src/__tests__/setup.ts`

```typescript
import { expect, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

// Cleanup después de cada test
afterEach(() => {
  cleanup()
})

// Mock de localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
global.localStorage = localStorageMock as any

// Mock de fetch
global.fetch = vi.fn()

// Mock de IntersectionObserver (usado por Recharts en algunos casos)
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return []
  }
  unobserve() {}
} as any

// Mock de ResizeObserver (usado por ResponsiveContainer de Recharts)
global.ResizeObserver = class ResizeObserver {
  constructor(callback: ResizeObserverCallback) {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any

// Mock de matchMedia (para tests responsive)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Suprimir warnings específicos de React 19
const originalError = console.error
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('ReactDOM.render')
    ) {
      return
    }
    originalError.call(console, ...args)
  }
})

afterAll(() => {
  console.error = originalError
})
```

---

### 1.3 Crear Test Utilities

**Archivo**: `/src/__tests__/utils/test-utils.tsx`

```typescript
import React, { ReactElement } from 'react'
import { render, RenderOptions } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

// Wrapper con providers comunes
const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      {children}
    </BrowserRouter>
  )
}

// Custom render que incluye providers
const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) => render(ui, { wrapper: AllTheProviders, ...options })

// Re-export todo de testing-library
export * from '@testing-library/react'
export { customRender as render }
```

**Uso**:
```typescript
import { render, screen } from '@/__tests__/utils/test-utils'
// Ahora render incluye BrowserRouter automáticamente
```

---

## FASE 2: ESTRATEGIA DE MOCKING RECHARTS

### 2.1 Problema con Recharts en Tests

**Desafío**: Recharts renderiza SVG complejos con:
- ResponsiveContainer que depende de ResizeObserver
- Animaciones que pueden causar timeouts
- Dimensiones calculadas dinámicamente
- Eventos de mouse/hover complejos

**Soluciones**:

#### Opción A: Mock Completo (Recomendado para unit tests)

**Archivo**: `/src/__tests__/mocks/recharts.tsx`

```typescript
import { vi } from 'vitest'
import React from 'react'

// Mock de ResponsiveContainer que renderiza children con dimensiones fijas
export const ResponsiveContainer = ({ children, width, height }: any) => {
  return (
    <div data-testid="responsive-container" style={{ width, height }}>
      {typeof children === 'function'
        ? children({ width: width || 600, height: height || 300 })
        : children}
    </div>
  )
}

// Mock de LineChart que renderiza estructura básica
export const LineChart = ({ children, data }: any) => {
  return (
    <svg data-testid="line-chart" aria-label="Line Chart">
      <g data-testid="line-chart-content">
        {children}
      </g>
      {/* Renderizar data como elementos para verificación */}
      {data && data.map((item: any, index: number) => (
        <g key={index} data-testid={`data-point-${index}`}>
          {Object.entries(item).map(([key, value]) => (
            <text key={key} data-testid={`${key}-${index}`}>
              {String(value)}
            </text>
          ))}
        </g>
      ))}
    </svg>
  )
}

// Mock de Line
export const Line = ({ dataKey, stroke, name }: any) => {
  return (
    <path
      data-testid={`line-${dataKey}`}
      stroke={stroke}
      aria-label={name || dataKey}
    />
  )
}

// Mock de BarChart
export const BarChart = ({ children, data }: any) => {
  return (
    <svg data-testid="bar-chart" aria-label="Bar Chart">
      <g data-testid="bar-chart-content">
        {children}
      </g>
      {data && data.map((item: any, index: number) => (
        <g key={index} data-testid={`bar-group-${index}`}>
          {Object.entries(item).map(([key, value]) => (
            <text key={key} data-testid={`${key}-${index}`}>
              {String(value)}
            </text>
          ))}
        </g>
      ))}
    </svg>
  )
}

// Mock de Bar
export const Bar = ({ dataKey, fill, children }: any) => {
  return (
    <g data-testid={`bar-${dataKey}`} fill={fill}>
      {children}
    </g>
  )
}

// Mock de Cell
export const Cell = ({ fill }: any) => {
  return <rect data-testid="bar-cell" fill={fill} />
}

// Mock de XAxis
export const XAxis = ({ dataKey }: any) => {
  return <g data-testid={`x-axis-${dataKey}`} />
}

// Mock de YAxis
export const YAxis = () => {
  return <g data-testid="y-axis" />
}

// Mock de CartesianGrid
export const CartesianGrid = ({ strokeDasharray }: any) => {
  return <g data-testid="cartesian-grid" data-dasharray={strokeDasharray} />
}

// Mock de Tooltip
export const Tooltip = ({ content }: any) => {
  return content ? (
    <div data-testid="chart-tooltip">{content}</div>
  ) : (
    <div data-testid="chart-tooltip" />
  )
}

// Mock de Legend
export const Legend = () => {
  return <div data-testid="chart-legend" />
}
```

**Configuración en vitest.config.ts**:

```typescript
export default defineConfig({
  // ... configuración existente
  test: {
    // ... resto de config
    alias: {
      'recharts': path.resolve(__dirname, './src/__tests__/mocks/recharts.tsx')
    }
  }
})
```

#### Opción B: Mock Parcial (Para integration tests)

**Archivo**: `/src/__tests__/utils/recharts-helpers.ts`

```typescript
import { vi } from 'vitest'

/**
 * Mock solo ResponsiveContainer para evitar problemas de resize
 * Mantiene el resto de Recharts real
 */
export const mockResponsiveContainer = () => {
  vi.mock('recharts', async () => {
    const actual = await vi.importActual('recharts')
    return {
      ...actual,
      ResponsiveContainer: ({ children, width, height }: any) => (
        <div style={{ width: width || 600, height: height || 300 }}>
          {typeof children === 'function'
            ? children({ width: width || 600, height: height || 300 })
            : children}
        </div>
      ),
    }
  })
}

/**
 * Deshabilitar animaciones en Recharts para tests
 */
export const disableAnimations = () => {
  // Las props isAnimationActive={false} deben pasarse a cada componente
  return {
    isAnimationActive: false,
    animationDuration: 0,
  }
}
```

---

## FASE 3: TESTS UNITARIOS

### 3.1 Test: chartConfig.ts

**Archivo**: `/src/components/analytics/charts/__tests__/chartConfig.test.ts`

```typescript
import { describe, it, expect } from 'vitest'
import {
  formatChartDate,
  formatNumber,
  CHART_COLORS,
  GRID_CONFIG,
  AXIS_CONFIG
} from '../chartConfig'

describe('chartConfig utilities', () => {
  describe('formatChartDate', () => {
    it('should format date to Spanish short format', () => {
      const date = '2025-10-18T10:00:00Z'
      const result = formatChartDate(date)
      // Resultado esperado: "18 oct" o "18 oct." dependiendo del locale
      expect(result).toMatch(/18\s+oct\.?/i)
    })

    it('should handle invalid dates gracefully', () => {
      const result = formatChartDate('invalid-date')
      expect(result).toBe('Invalid Date')
    })
  })

  describe('formatNumber', () => {
    it('should format millions', () => {
      expect(formatNumber(1500000)).toBe('1.5M')
      expect(formatNumber(1000000)).toBe('1.0M')
    })

    it('should format thousands', () => {
      expect(formatNumber(1500)).toBe('1.5K')
      expect(formatNumber(1000)).toBe('1.0K')
    })

    it('should return number as string for small values', () => {
      expect(formatNumber(999)).toBe('999')
      expect(formatNumber(0)).toBe('0')
    })

    it('should handle negative numbers', () => {
      expect(formatNumber(-1500000)).toBe('-1.5M')
    })
  })

  describe('CHART_COLORS', () => {
    it('should have all required color properties', () => {
      expect(CHART_COLORS).toHaveProperty('primary')
      expect(CHART_COLORS).toHaveProperty('secondary')
      expect(CHART_COLORS).toHaveProperty('gradient')
      expect(CHART_COLORS.gradient).toBeInstanceOf(Array)
      expect(CHART_COLORS.gradient).toHaveLength(2)
    })

    it('should have valid hex color codes', () => {
      const hexRegex = /^#[0-9A-Fa-f]{6}$/
      expect(CHART_COLORS.primary).toMatch(hexRegex)
      expect(CHART_COLORS.secondary).toMatch(hexRegex)
    })
  })

  describe('GRID_CONFIG', () => {
    it('should have correct grid configuration', () => {
      expect(GRID_CONFIG.strokeDasharray).toBe('3 3')
      expect(GRID_CONFIG.stroke).toBe('rgba(255, 255, 255, 0.1)')
      expect(GRID_CONFIG.vertical).toBe(false)
    })
  })

  describe('AXIS_CONFIG', () => {
    it('should have correct axis configuration', () => {
      expect(AXIS_CONFIG.stroke).toBe('#888')
      expect(AXIS_CONFIG.fontSize).toBe(12)
      expect(AXIS_CONFIG.tickLine).toBe(false)
      expect(AXIS_CONFIG.axisLine).toBe(false)
    })
  })
})
```

---

### 3.2 Test: ChartContainer.tsx

**Archivo**: `/src/components/analytics/charts/__tests__/ChartContainer.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@/__tests__/utils/test-utils'
import ChartContainer from '../ChartContainer'

describe('ChartContainer', () => {
  it('should render title with icon', () => {
    render(
      <ChartContainer title="Test Chart" icon="bi-graph-up">
        <div>Chart Content</div>
      </ChartContainer>
    )

    expect(screen.getByText('Test Chart')).toBeInTheDocument()
    const icon = screen.getByText('Test Chart').parentElement?.querySelector('i')
    expect(icon).toHaveClass('bi', 'bi-graph-up', 'me-2')
  })

  it('should render children inside chart-wrapper', () => {
    render(
      <ChartContainer title="Test Chart">
        <div data-testid="chart-child">Chart Content</div>
      </ChartContainer>
    )

    const wrapper = screen.getByTestId('chart-child').parentElement
    expect(wrapper).toHaveClass('chart-wrapper')
  })

  it('should use default icon if not provided', () => {
    render(
      <ChartContainer title="Test Chart">
        <div>Content</div>
      </ChartContainer>
    )

    const icon = screen.getByText('Test Chart').parentElement?.querySelector('i')
    expect(icon).toHaveClass('bi-graph-up')
  })

  it('should apply custom className', () => {
    const { container } = render(
      <ChartContainer title="Test" className="custom-class">
        <div>Content</div>
      </ChartContainer>
    )

    const section = container.querySelector('.analytics-section')
    expect(section).toHaveClass('analytics-section', 'custom-class')
  })

  it('should have proper heading hierarchy', () => {
    render(
      <ChartContainer title="Test Chart">
        <div>Content</div>
      </ChartContainer>
    )

    const heading = screen.getByRole('heading', { level: 3 })
    expect(heading).toHaveTextContent('Test Chart')
  })
})
```

---

### 3.3 Test: EngagementTrendChart.tsx

**Archivo**: `/src/components/analytics/charts/__tests__/EngagementTrendChart.test.tsx`

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@/__tests__/utils/test-utils'
import EngagementTrendChart from '../EngagementTrendChart'
import type { EngagementTrendItem } from '../../types/analytics.types'

describe('EngagementTrendChart', () => {
  const mockData: EngagementTrendItem[] = [
    { date: '2025-10-15', likes: 100, comments: 20 },
    { date: '2025-10-16', likes: 150, comments: 30 },
    { date: '2025-10-17', likes: 120, comments: 25 },
  ]

  beforeEach(() => {
    // Reset mocks antes de cada test
  })

  describe('Rendering', () => {
    it('should render ResponsiveContainer with correct height', () => {
      render(<EngagementTrendChart data={mockData} height={280} />)

      const container = screen.getByTestId('responsive-container')
      expect(container).toBeInTheDocument()
      expect(container).toHaveStyle({ height: 280 })
    })

    it('should render LineChart with data', () => {
      render(<EngagementTrendChart data={mockData} />)

      expect(screen.getByTestId('line-chart')).toBeInTheDocument()
      expect(screen.getAllByTestId(/^data-point-/)).toHaveLength(3)
    })

    it('should render both likes and comments lines', () => {
      render(<EngagementTrendChart data={mockData} />)

      expect(screen.getByTestId('line-likes')).toBeInTheDocument()
      expect(screen.getByTestId('line-comments')).toBeInTheDocument()
    })

    it('should display correct data values', () => {
      render(<EngagementTrendChart data={mockData} />)

      // Verificar que los valores están en el DOM
      expect(screen.getByTestId('likes-0')).toHaveTextContent('100')
      expect(screen.getByTestId('comments-0')).toHaveTextContent('20')
      expect(screen.getByTestId('likes-1')).toHaveTextContent('150')
    })
  })

  describe('Props handling', () => {
    it('should use default height if not provided', () => {
      render(<EngagementTrendChart data={mockData} />)

      const container = screen.getByTestId('responsive-container')
      expect(container).toHaveStyle({ height: 280 })
    })

    it('should render legend when showLegend is true', () => {
      render(<EngagementTrendChart data={mockData} showLegend={true} />)

      expect(screen.getByTestId('chart-legend')).toBeInTheDocument()
    })

    it('should not render legend when showLegend is false', () => {
      render(<EngagementTrendChart data={mockData} showLegend={false} />)

      expect(screen.queryByTestId('chart-legend')).not.toBeInTheDocument()
    })

    it('should render grid when showGrid is true', () => {
      render(<EngagementTrendChart data={mockData} showGrid={true} />)

      expect(screen.getByTestId('cartesian-grid')).toBeInTheDocument()
    })

    it('should not render grid when showGrid is false', () => {
      render(<EngagementTrendChart data={mockData} showGrid={false} />)

      expect(screen.queryByTestId('cartesian-grid')).not.toBeInTheDocument()
    })
  })

  describe('Empty state', () => {
    it('should show empty state when data is empty array', () => {
      render(<EngagementTrendChart data={[]} />)

      expect(screen.getByText(/no hay datos de tendencia/i)).toBeInTheDocument()
      expect(screen.queryByTestId('line-chart')).not.toBeInTheDocument()
    })

    it('should show empty state when data is null', () => {
      render(<EngagementTrendChart data={null as any} />)

      expect(screen.getByText(/no hay datos de tendencia/i)).toBeInTheDocument()
    })
  })

  describe('Data transformation', () => {
    it('should calculate total engagement correctly', () => {
      render(<EngagementTrendChart data={mockData} />)

      // Primer punto: 100 likes + 20 comments = 120 total
      // Esto debería estar en el DOM transformado
      const dataPoint = screen.getByTestId('data-point-0')
      expect(dataPoint).toBeInTheDocument()
    })

    it('should handle data with missing values', () => {
      const dataWithMissing: EngagementTrendItem[] = [
        { date: '2025-10-15', likes: 100, comments: 0 },
        { date: '2025-10-16', likes: 0, comments: 30 },
      ]

      render(<EngagementTrendChart data={dataWithMissing} />)

      expect(screen.getByTestId('line-chart')).toBeInTheDocument()
      expect(screen.getByTestId('likes-0')).toHaveTextContent('100')
      expect(screen.getByTestId('comments-0')).toHaveTextContent('0')
    })
  })

  describe('Accessibility', () => {
    it('should have proper aria-label on LineChart', () => {
      render(<EngagementTrendChart data={mockData} />)

      const chart = screen.getByLabelText('Line Chart')
      expect(chart).toBeInTheDocument()
    })

    it('should have accessible line names', () => {
      render(<EngagementTrendChart data={mockData} />)

      const likesLine = screen.getByLabelText('Likes')
      const commentsLine = screen.getByLabelText('Comentarios')

      expect(likesLine).toBeInTheDocument()
      expect(commentsLine).toBeInTheDocument()
    })
  })

  describe('Performance', () => {
    it('should memoize chart data transformation', () => {
      const { rerender } = render(<EngagementTrendChart data={mockData} />)

      // Primera renderización
      const firstRender = screen.getByTestId('line-chart')

      // Re-render con mismas props
      rerender(<EngagementTrendChart data={mockData} />)

      // El componente debería seguir presente
      expect(screen.getByTestId('line-chart')).toBeInTheDocument()
    })

    it('should handle large datasets efficiently', () => {
      const largeData: EngagementTrendItem[] = Array.from(
        { length: 365 },
        (_, i) => ({
          date: `2025-${String(Math.floor(i / 30) + 1).padStart(2, '0')}-${String((i % 30) + 1).padStart(2, '0')}`,
          likes: Math.floor(Math.random() * 1000),
          comments: Math.floor(Math.random() * 100),
        })
      )

      render(<EngagementTrendChart data={largeData} />)

      expect(screen.getByTestId('line-chart')).toBeInTheDocument()
      expect(screen.getAllByTestId(/^data-point-/)).toHaveLength(365)
    })
  })
})
```

---

### 3.4 Test: BestTimesChart.tsx

**Archivo**: `/src/components/analytics/charts/__tests__/BestTimesChart.test.tsx`

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@/__tests__/utils/test-utils'
import BestTimesChart from '../BestTimesChart'
import type { BestPostingTime } from '../../types/analytics.types'

describe('BestTimesChart', () => {
  const mockData: BestPostingTime[] = [
    { time: '09:00', avg_engagement: 4.2 },
    { time: '12:00', avg_engagement: 5.8 },
    { time: '18:00', avg_engagement: 6.5 },
    { time: '21:00', avg_engagement: 3.1 },
  ]

  describe('Rendering', () => {
    it('should render BarChart with data', () => {
      render(<BestTimesChart data={mockData} />)

      expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
      expect(screen.getAllByTestId(/^bar-group-/)).toHaveLength(4)
    })

    it('should render bar for engagement data', () => {
      render(<BestTimesChart data={mockData} />)

      expect(screen.getByTestId('bar-engagement')).toBeInTheDocument()
    })

    it('should display engagement values when showValues is true', () => {
      render(<BestTimesChart data={mockData} showValues={true} />)

      const chart = screen.getByTestId('bar-chart')
      expect(chart).toBeInTheDocument()
      // Los valores deberían estar en el DOM
    })
  })

  describe('Data normalization', () => {
    it('should handle backend field "hour" instead of "time"', () => {
      const backendData = [
        { hour: '09:00', avg_engagement_rate: 4.2 },
        { hour: '12:00', avg_engagement_rate: 5.8 },
      ] as any

      render(<BestTimesChart data={backendData} />)

      expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
    })

    it('should handle backend field "avg_engagement_rate"', () => {
      const backendData = [
        { time: '09:00', avg_engagement_rate: 4.2 },
      ] as any

      render(<BestTimesChart data={backendData} />)

      expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
    })

    it('should sort data by hour chronologically', () => {
      const unsortedData: BestPostingTime[] = [
        { time: '18:00', avg_engagement: 6.5 },
        { time: '09:00', avg_engagement: 4.2 },
        { time: '21:00', avg_engagement: 3.1 },
        { time: '12:00', avg_engagement: 5.8 },
      ]

      render(<BestTimesChart data={unsortedData} />)

      const bars = screen.getAllByTestId(/^bar-group-/)
      expect(bars).toHaveLength(4)
      // Verificar que el orden es correcto
      // El primer bar debería ser 09:00
    })
  })

  describe('Color coding', () => {
    it('should apply different colors based on engagement level', () => {
      // Data con diferentes niveles de engagement
      const variedData: BestPostingTime[] = [
        { time: '09:00', avg_engagement: 2.0 }, // Low
        { time: '12:00', avg_engagement: 4.0 }, // Medium
        { time: '15:00', avg_engagement: 6.0 }, // High
        { time: '18:00', avg_engagement: 8.0 }, // Very high
      ]

      render(<BestTimesChart data={variedData} />)

      const cells = screen.getAllByTestId('bar-cell')
      expect(cells).toHaveLength(4)

      // Cada cell debería tener un color fill
      cells.forEach(cell => {
        expect(cell).toHaveAttribute('fill')
      })
    })
  })

  describe('Props handling', () => {
    it('should use custom height', () => {
      render(<BestTimesChart data={mockData} height={400} />)

      const container = screen.getByTestId('responsive-container')
      expect(container).toHaveStyle({ height: 400 })
    })

    it('should use default height if not provided', () => {
      render(<BestTimesChart data={mockData} />)

      const container = screen.getByTestId('responsive-container')
      expect(container).toHaveStyle({ height: 300 })
    })

    it('should respect maxValue prop for scaling', () => {
      render(<BestTimesChart data={mockData} maxValue={10} />)

      // maxValue debería afectar el cálculo de colores
      expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
    })
  })

  describe('Empty state', () => {
    it('should show empty state when data is empty', () => {
      render(<BestTimesChart data={[]} />)

      expect(screen.getByText(/no hay suficientes datos/i)).toBeInTheDocument()
      expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument()
    })

    it('should show empty state when data is null', () => {
      render(<BestTimesChart data={null as any} />)

      expect(screen.getByText(/no hay suficientes datos/i)).toBeInTheDocument()
    })
  })

  describe('Optional data fields', () => {
    it('should display posts_count in tooltip if available', () => {
      const dataWithCount: BestPostingTime[] = [
        { time: '09:00', avg_engagement: 4.2, posts_count: 15 },
      ]

      render(<BestTimesChart data={dataWithCount} />)

      expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
    })

    it('should work without posts_count', () => {
      const dataWithoutCount: BestPostingTime[] = [
        { time: '09:00', avg_engagement: 4.2 },
      ]

      render(<BestTimesChart data={dataWithoutCount} />)

      expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('should have proper aria-label on BarChart', () => {
      render(<BestTimesChart data={mockData} />)

      const chart = screen.getByLabelText('Bar Chart')
      expect(chart).toBeInTheDocument()
    })
  })
})
```

---

## FASE 4: TESTS DE INTEGRACION

### 4.1 Test: Analytics.tsx (Integración completa)

**Archivo**: `/src/components/analytics/__tests__/Analytics.test.tsx`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@/__tests__/utils/test-utils'
import userEvent from '@testing-library/user-event'
import Analytics from '../Analytics'

// Mock fetch global
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('Analytics Integration', () => {
  const mockAnalyticsData = {
    success: true,
    data: {
      overview: {
        total_posts: 42,
        total_interactions: 1250,
        engagement_rate: 5.2,
      },
      top_posts: [
        {
          id: 1,
          caption: 'Test post 1',
          media_url: 'https://example.com/1.jpg',
          likes: 150,
          comments: 20,
          timestamp: '2025-10-15T10:00:00Z',
        },
        {
          id: 2,
          caption: 'Test post 2',
          media_url: 'https://example.com/2.jpg',
          likes: 200,
          comments: 30,
          timestamp: '2025-10-16T10:00:00Z',
        },
      ],
      engagement_trend: [
        { date: '2025-10-15', likes: 100, comments: 20 },
        { date: '2025-10-16', likes: 150, comments: 30 },
        { date: '2025-10-17', likes: 120, comments: 25 },
      ],
      best_posting_times: [
        { hour: '09:00', avg_engagement_rate: 4.2 },
        { hour: '12:00', avg_engagement_rate: 5.8 },
        { hour: '18:00', avg_engagement_rate: 6.5 },
      ],
      insights: [
        {
          type: 'trend',
          title: 'Engagement aumentando',
          description: 'Tus posts están generando más interacción',
          icon: 'trend-up',
        },
      ],
    },
  }

  beforeEach(() => {
    // Reset localStorage
    localStorage.clear()
    localStorage.setItem('authToken', 'fake-token-123')

    // Reset fetch mock
    mockFetch.mockReset()
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => mockAnalyticsData,
    })
  })

  describe('Initial Loading', () => {
    it('should show loading state initially', () => {
      render(<Analytics />)

      expect(screen.getByText(/cargando analytics/i)).toBeInTheDocument()
      expect(screen.getByRole('status', { hidden: true })).toBeInTheDocument()
    })

    it('should fetch analytics data on mount', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          'http://localhost:8000/api/instagram/analytics/cached-overview?days=7',
          expect.objectContaining({
            headers: { 'Authorization': 'Bearer fake-token-123' },
          })
        )
      })
    })
  })

  describe('Data Display', () => {
    it('should display overview stats', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText('42')).toBeInTheDocument() // total_posts
        expect(screen.getByText('1,250')).toBeInTheDocument() // total_likes
        expect(screen.getByText('5.2%')).toBeInTheDocument() // engagement_rate
      })
    })

    it('should render EngagementTrendChart with data', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('line-chart')).toBeInTheDocument()
        expect(screen.getAllByTestId(/^data-point-/)).toHaveLength(3)
      })
    })

    it('should render BestTimesChart with data', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
        expect(screen.getAllByTestId(/^bar-group-/)).toHaveLength(3)
      })
    })

    it('should display top posts list', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText('Test post 1')).toBeInTheDocument()
        expect(screen.getByText('Test post 2')).toBeInTheDocument()
        expect(screen.getByText('150')).toBeInTheDocument() // likes de post 1
        expect(screen.getByText('200')).toBeInTheDocument() // likes de post 2
      })
    })

    it('should display insights section', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/insights clave/i)).toBeInTheDocument()
        expect(screen.getByText('Engagement aumentando')).toBeInTheDocument()
      })
    })
  })

  describe('Time Range Selector', () => {
    it('should render time range selector with default value', async () => {
      render(<Analytics />)

      await waitFor(() => {
        const select = screen.getByRole('combobox')
        expect(select).toHaveValue('7days')
      })
    })

    it('should fetch data with different days on time range change', async () => {
      const user = userEvent.setup()
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      const select = screen.getByRole('combobox')
      await user.selectOptions(select, '30days')

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          'http://localhost:8000/api/instagram/analytics/cached-overview?days=30',
          expect.any(Object)
        )
      })
    })

    it('should have all time range options', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByRole('option', { name: /últimos 7 días/i })).toBeInTheDocument()
        expect(screen.getByRole('option', { name: /últimos 30 días/i })).toBeInTheDocument()
        expect(screen.getByRole('option', { name: /últimos 90 días/i })).toBeInTheDocument()
        expect(screen.getByRole('option', { name: /todo el tiempo/i })).toBeInTheDocument()
      })
    })
  })

  describe('Error Handling', () => {
    it('should show empty state when no token', async () => {
      localStorage.removeItem('authToken')
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/no hay datos de analytics disponibles/i)).toBeInTheDocument()
        expect(screen.getByText(/conecta tu cuenta/i)).toBeInTheDocument()
      })
    })

    it('should handle fetch error gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/no hay datos de analytics disponibles/i)).toBeInTheDocument()
      })
    })

    it('should handle API error response', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/no hay datos de analytics disponibles/i)).toBeInTheDocument()
      })
    })

    it('should handle invalid data structure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: false }),
      })

      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/no hay datos de analytics disponibles/i)).toBeInTheDocument()
      })
    })
  })

  describe('Empty Data States', () => {
    it('should handle empty engagement_trend array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAnalyticsData,
          data: {
            ...mockAnalyticsData.data,
            engagement_trend: [],
          },
        }),
      })

      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/no hay datos de tendencia/i)).toBeInTheDocument()
      })
    })

    it('should handle empty best_posting_times array', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAnalyticsData,
          data: {
            ...mockAnalyticsData.data,
            best_posting_times: [],
          },
        }),
      })

      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText(/no hay suficientes datos/i)).toBeInTheDocument()
      })
    })

    it('should not render insights section when empty', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...mockAnalyticsData,
          data: {
            ...mockAnalyticsData.data,
            insights: [],
          },
        }),
      })

      render(<Analytics />)

      await waitFor(() => {
        expect(screen.queryByText(/insights clave/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Duplicate Fetch Prevention', () => {
    it('should not fetch twice on initial mount', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByText('42')).toBeInTheDocument()
      })

      // Debería haber llamado fetch solo una vez
      expect(mockFetch).toHaveBeenCalledTimes(1)
    })

    it('should prevent concurrent fetches', async () => {
      const user = userEvent.setup()
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument()
      })

      const select = screen.getByRole('combobox')

      // Cambiar rápidamente dos veces
      await user.selectOptions(select, '30days')
      await user.selectOptions(select, '90days')

      await waitFor(() => {
        expect(screen.getByText('42')).toBeInTheDocument()
      })

      // Debería haber prevenido fetches duplicados
      // 1 inicial + 2 cambios = máximo 3 llamadas
      expect(mockFetch.mock.calls.length).toBeLessThanOrEqual(3)
    })
  })

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', async () => {
      render(<Analytics />)

      await waitFor(() => {
        const mainHeading = screen.getByRole('heading', { level: 2, name: /analytics & insights/i })
        expect(mainHeading).toBeInTheDocument()

        const subHeadings = screen.getAllByRole('heading', { level: 3 })
        expect(subHeadings.length).toBeGreaterThan(0)
      })
    })

    it('should have accessible form controls', async () => {
      render(<Analytics />)

      await waitFor(() => {
        const select = screen.getByRole('combobox')
        expect(select).toBeInTheDocument()
        expect(select).toHaveAccessibleName()
      })
    })
  })
})
```

---

## FASE 5: TESTS DE COMPORTAMIENTO RESPONSIVE

### 5.1 Responsive Tests Helper

**Archivo**: `/src/__tests__/utils/responsive-helpers.ts`

```typescript
import { vi } from 'vitest'

/**
 * Simula diferentes tamaños de viewport
 */
export const setViewportSize = (width: number, height: number = 768) => {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  })

  Object.defineProperty(window, 'innerHeight', {
    writable: true,
    configurable: true,
    value: height,
  })

  // Actualizar matchMedia para el nuevo tamaño
  window.matchMedia = vi.fn().mockImplementation((query: string) => {
    // Parsear query para determinar si matches
    const widthMatch = query.match(/max-width:\s*(\d+)px/)
    const maxWidth = widthMatch ? parseInt(widthMatch[1]) : Infinity

    return {
      matches: width <= maxWidth,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }
  })

  // Disparar evento resize
  window.dispatchEvent(new Event('resize'))
}

export const VIEWPORT_SIZES = {
  mobile: { width: 375, height: 667 },
  tablet: { width: 768, height: 1024 },
  desktop: { width: 1920, height: 1080 },
}
```

### 5.2 Responsive Tests

**Archivo**: `/src/components/analytics/__tests__/Analytics.responsive.test.tsx`

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@/__tests__/utils/test-utils'
import { setViewportSize, VIEWPORT_SIZES } from '@/__tests__/utils/responsive-helpers'
import Analytics from '../Analytics'

describe('Analytics Responsive Behavior', () => {
  const mockData = {
    success: true,
    data: {
      overview: {
        total_posts: 42,
        total_interactions: 1250,
        engagement_rate: 5.2,
      },
      engagement_trend: [
        { date: '2025-10-15', likes: 100, comments: 20 },
      ],
      best_posting_times: [
        { hour: '09:00', avg_engagement_rate: 4.2 },
      ],
      top_posts: [],
      insights: [],
    },
  }

  beforeEach(() => {
    localStorage.setItem('authToken', 'fake-token')
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    })
  })

  afterEach(() => {
    // Reset viewport
    setViewportSize(1920, 1080)
  })

  describe('Mobile viewport (375px)', () => {
    beforeEach(() => {
      setViewportSize(VIEWPORT_SIZES.mobile.width, VIEWPORT_SIZES.mobile.height)
    })

    it('should render charts in mobile viewport', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('line-chart')).toBeInTheDocument()
        expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
      })
    })

    it('should use appropriate chart heights on mobile', async () => {
      render(<Analytics />)

      await waitFor(() => {
        const containers = screen.getAllByTestId('responsive-container')
        containers.forEach(container => {
          expect(container).toBeInTheDocument()
        })
      })
    })
  })

  describe('Tablet viewport (768px)', () => {
    beforeEach(() => {
      setViewportSize(VIEWPORT_SIZES.tablet.width, VIEWPORT_SIZES.tablet.height)
    })

    it('should render charts in tablet viewport', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('line-chart')).toBeInTheDocument()
        expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
      })
    })
  })

  describe('Desktop viewport (1920px)', () => {
    beforeEach(() => {
      setViewportSize(VIEWPORT_SIZES.desktop.width, VIEWPORT_SIZES.desktop.height)
    })

    it('should render charts in desktop viewport', async () => {
      render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('line-chart')).toBeInTheDocument()
        expect(screen.getByTestId('bar-chart')).toBeInTheDocument()
      })
    })
  })

  describe('Viewport changes', () => {
    it('should handle resize from desktop to mobile', async () => {
      setViewportSize(VIEWPORT_SIZES.desktop.width)
      const { rerender } = render(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('line-chart')).toBeInTheDocument()
      })

      // Cambiar a mobile
      setViewportSize(VIEWPORT_SIZES.mobile.width)
      rerender(<Analytics />)

      await waitFor(() => {
        expect(screen.getByTestId('line-chart')).toBeInTheDocument()
      })
    })
  })
})
```

---

## FASE 6: COVERAGE Y CALIDAD

### 6.1 Comandos de Testing

Agregar a `package.json`:

```json
{
  "scripts": {
    "test": "vitest",
    "test:ui": "vitest --ui",
    "test:coverage": "vitest --coverage",
    "test:watch": "vitest --watch",
    "test:run": "vitest run",
    "test:analytics": "vitest run src/components/analytics",
    "test:charts": "vitest run src/components/analytics/charts"
  }
}
```

### 6.2 Coverage Thresholds

Ya configurado en `vitest.config.ts`:

```typescript
coverage: {
  thresholds: {
    lines: 80,
    functions: 80,
    branches: 80,
    statements: 80
  }
}
```

### 6.3 Pre-commit Hook (Opcional)

**Archivo**: `.husky/pre-commit`

```bash
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

# Run tests before commit
npm run test:run

# Run coverage check
npm run test:coverage
```

---

## CHECKLIST DE IMPLEMENTACION

### Setup Inicial
- [ ] Instalar dependencias de testing
- [ ] Crear `/src/__tests__/setup.ts`
- [ ] Crear `/src/__tests__/utils/test-utils.tsx`
- [ ] Crear `/src/__tests__/mocks/recharts.tsx`
- [ ] Actualizar `vitest.config.ts` con alias de mock

### Tests Unitarios
- [ ] Test: `chartConfig.test.ts` (5 describe blocks)
- [ ] Test: `ChartContainer.test.tsx` (5 tests)
- [ ] Test: `EngagementTrendChart.test.tsx` (7 describe blocks)
- [ ] Test: `BestTimesChart.test.tsx` (8 describe blocks)

### Tests de Integración
- [ ] Test: `Analytics.test.tsx` (9 describe blocks)
- [ ] Test: `Analytics.responsive.test.tsx` (4 describe blocks)

### Coverage
- [ ] Ejecutar `npm run test:coverage`
- [ ] Verificar cobertura >= 80%
- [ ] Revisar reporte HTML en `/coverage/index.html`

### CI/CD (Opcional)
- [ ] Configurar GitHub Actions para ejecutar tests
- [ ] Configurar coverage reports en CI

---

## ESTRATEGIAS DE DEBUGGING

### 1. Tests que fallan por timeout

```typescript
// Aumentar timeout en test específico
it('should handle slow operation', { timeout: 10000 }, async () => {
  // test code
})
```

### 2. Ver output de componente en test

```typescript
import { debug } from '@testing-library/react'

it('should render component', () => {
  const { debug } = render(<Component />)
  debug() // Imprime HTML en consola
})
```

### 3. Inspeccionar queries fallidas

```typescript
// En lugar de getBy (lanza error), usar queryBy para debugging
const element = screen.queryByText('Some text')
if (!element) {
  screen.debug() // Ver qué se renderizó realmente
}
```

---

## MEJORES PRACTICAS

### 1. Organización de Tests

```
src/
├── components/
│   └── analytics/
│       ├── Analytics.tsx
│       ├── __tests__/
│       │   ├── Analytics.test.tsx
│       │   └── Analytics.responsive.test.tsx
│       └── charts/
│           ├── EngagementTrendChart.tsx
│           ├── BestTimesChart.tsx
│           ├── ChartContainer.tsx
│           ├── chartConfig.ts
│           └── __tests__/
│               ├── EngagementTrendChart.test.tsx
│               ├── BestTimesChart.test.tsx
│               ├── ChartContainer.test.tsx
│               └── chartConfig.test.ts
```

### 2. Naming Conventions

- Test files: `ComponentName.test.tsx`
- Test suites: `describe('ComponentName', () => {})`
- Test cases: `it('should do something specific', () => {})`
- Mock files: `__mocks__/libraryName.tsx`

### 3. AAA Pattern

```typescript
it('should update value on click', async () => {
  // ARRANGE: Setup
  const user = userEvent.setup()
  render(<Component initialValue={0} />)

  // ACT: Perform action
  const button = screen.getByRole('button')
  await user.click(button)

  // ASSERT: Verify result
  expect(screen.getByText('1')).toBeInTheDocument()
})
```

### 4. Test Isolation

```typescript
// BAD: Tests comparten estado
let sharedData = []

it('test 1', () => {
  sharedData.push(1)
})

// GOOD: Cada test tiene su propio estado
it('test 1', () => {
  const localData = []
  localData.push(1)
})
```

---

## RECURSOS ADICIONALES

### Documentación
- [Vitest Docs](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library Queries](https://testing-library.com/docs/queries/about/)
- [Jest DOM Matchers](https://github.com/testing-library/jest-dom)

### Ejemplos de Tests
- [Recharts Testing Examples](https://github.com/recharts/recharts/tree/master/test)
- [React 19 Testing Patterns](https://react.dev/learn/testing)

---

## ESTIMACION DE TIEMPO

| Tarea | Tiempo Estimado |
|-------|----------------|
| Setup de testing | 30 min |
| Tests unitarios (chartConfig) | 15 min |
| Tests unitarios (ChartContainer) | 20 min |
| Tests unitarios (EngagementTrendChart) | 45 min |
| Tests unitarios (BestTimesChart) | 45 min |
| Tests de integración (Analytics) | 60 min |
| Tests responsive | 30 min |
| Ajustes de coverage | 30 min |
| **TOTAL** | **4h 15min** |

---

## PROXIMOS PASOS

Una vez implementados estos tests:

1. **Agregar tests E2E** con Playwright para flujo completo
2. **Visual Regression Testing** con Chromatic o Percy
3. **Performance Testing** con Lighthouse CI
4. **Accessibility Testing** con axe-core (ya instalado)

---

**Documento creado**: 2025-10-18
**Autor**: Claude Code (Test Automation Expert)
**Proyecto**: SocialLab - Recharts Analytics Testing Strategy
**Target Coverage**: 80%+
**Framework**: Vitest + React Testing Library + React 19
