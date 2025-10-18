import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],

  test: {
    // Test environment
    environment: 'jsdom',

    // Setup files
    setupFiles: ['./src/__tests__/setup.ts'],

    // Global test utilities
    globals: true,

    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json', 'lcov'],
      reportsDirectory: './coverage',

      // Coverage thresholds
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80
      },

      // Files to exclude from coverage
      exclude: [
        'node_modules/',
        'src/__tests__/',
        'src/**/*.test.ts',
        'src/**/*.test.tsx',
        'src/**/*.spec.ts',
        'src/**/*.spec.tsx',
        'dist/',
        'build/',
        '**/*.d.ts',
        '**/*.config.ts',
        '**/*.config.js',
        'src/main.tsx',
        'src/vite-env.d.ts'
      ],

      // Include only source files
      include: [
        'src/**/*.ts',
        'src/**/*.tsx'
      ]
    },

    // Test include/exclude patterns
    include: [
      'src/**/*.{test,spec}.{ts,tsx}'
    ],

    exclude: [
      'node_modules',
      'dist',
      'build',
      '.idea',
      '.git',
      '.cache'
    ],

    // Test timeout
    testTimeout: 10000,
    hookTimeout: 10000,

    // Watch mode ignore patterns
    watchExclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/build/**'
    ],

    // Reporters
    reporters: ['verbose'],

    // Benchmark configuration (if using)
    benchmark: {
      include: ['src/**/*.bench.{ts,tsx}'],
      exclude: ['node_modules', 'dist']
    },

    // CSS handling
    css: {
      include: /.+/
    },

    // Mock reset
    clearMocks: true,
    mockReset: true,
    restoreMocks: true,

    // Parallel execution
    pool: 'threads',
    poolOptions: {
      threads: {
        singleThread: false
      }
    }
  },

  // Resolve aliases (match tsconfig.json paths)
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/context': path.resolve(__dirname, './src/context'),
      '@/utils': path.resolve(__dirname, './src/utils'),
      '@/__tests__': path.resolve(__dirname, './src/__tests__')
    }
  }
})
