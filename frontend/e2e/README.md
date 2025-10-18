# E2E Testing con Playwright

Este directorio contiene los tests end-to-end (E2E) para SocialLab usando Playwright.

## 📋 Requisitos

- Node.js 18+
- Playwright instalado (`@playwright/test`)
- Chromium browser instalado

## 🚀 Setup Inicial

```bash
# Instalar dependencias (si no están instaladas)
npm install

# Instalar browsers de Playwright
npm run playwright:install
```

## 🧪 Ejecutar Tests

### Todos los tests

```bash
npm run test:e2e
```

### Con UI interactiva

```bash
npm run test:e2e:ui
```

### En modo debug

```bash
npm run test:e2e:debug
```

### Con browser visible (headed mode)

```bash
npm run test:e2e:headed
```

### Solo un archivo específico

```bash
npx playwright test e2e/auth.spec.ts
```

### Solo tests que coincidan con un nombre

```bash
npx playwright test -g "should login"
```

## 📁 Estructura

```
e2e/
├── README.md               # Este archivo
├── fixtures/              # Datos de prueba
│   └── test-users.ts      # Usuarios de prueba
├── utils/                 # Utilidades y helpers
│   └── auth-helpers.ts    # Helpers de autenticación
├── auth.spec.ts          # Tests de autenticación
└── dashboard.spec.ts     # Tests del dashboard
```

## 🔧 Configuración

La configuración de Playwright está en `playwright.config.ts` en la raíz del proyecto frontend.

### Browsers configurados:

- Chromium (Desktop)
- Firefox (Desktop)
- WebKit/Safari (Desktop)
- Mobile Chrome (Pixel 5)
- Mobile Safari (iPhone 12)

### Features habilitadas:

- ✅ Screenshots on failure
- ✅ Videos on failure
- ✅ Traces on first retry
- ✅ Accessibility testing con axe-core
- ✅ Parallel execution
- ✅ Auto dev server start

## 📝 Escribir Tests

### Ejemplo básico:

```typescript
import { test, expect } from '@playwright/test';

test('should display page title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/SocialLab/);
});
```

### Con autenticación:

```typescript
import { test, expect } from '@playwright/test';
import { login } from './utils/auth-helpers';

test('authenticated user can access dashboard', async ({ page }) => {
  await login(page);
  await expect(page).toHaveURL(/\/dashboard/);
});
```

### Test de accesibilidad:

```typescript
import { test } from '@playwright/test';
import { injectAxe, checkA11y } from '@axe-core/playwright';

test('page should be accessible', async ({ page }) => {
  await page.goto('/dashboard');
  await injectAxe(page);
  await checkA11y(page);
});
```

## 🎯 Best Practices

1. **Use data-testid** para seleccionar elementos:
   ```html
   <button data-testid="login-button">Login</button>
   ```
   ```typescript
   await page.click('[data-testid="login-button"]');
   ```

2. **Espera explícitas** mejor que sleeps:
   ```typescript
   // ❌ Malo
   await page.waitForTimeout(3000);

   // ✅ Bueno
   await page.waitForSelector('[data-testid="dashboard"]');
   ```

3. **Page Object Model** para tests complejos:
   ```typescript
   class LoginPage {
     constructor(private page: Page) {}

     async login(email: string, password: string) {
       await this.page.fill('[data-testid="email"]', email);
       await this.page.fill('[data-testid="password"]', password);
       await this.page.click('[data-testid="submit"]');
     }
   }
   ```

4. **Cleanup** después de cada test:
   ```typescript
   test.afterEach(async ({ page }) => {
     await page.context().clearCookies();
     await page.evaluate(() => localStorage.clear());
   });
   ```

## 🐛 Debug

### Ver trace de un test fallido:

```bash
npx playwright show-trace test-results/path-to-trace.zip
```

### Generar report HTML:

```bash
npx playwright show-report
```

## 📊 CI/CD

Los tests E2E se ejecutan automáticamente en GitHub Actions:

- En push a `main` y `develop`
- En pull requests
- Manualmente con `workflow_dispatch`

Ver: `.github/workflows/e2e.yml`

## 🔗 Links Útiles

- [Playwright Documentation](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [axe-core Playwright](https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright)

## ⚠️ Notas Importantes

- Los tests con `test.skip(true)` requieren backend funcionando
- Asegúrate de tener el dev server corriendo antes de ejecutar tests localmente
- En CI, el dev server se inicia automáticamente
- Los browsers se instalan automáticamente en CI
