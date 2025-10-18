## 📝 Descripción

<!-- Describe brevemente los cambios realizados en este PR -->

## 🎯 Tipo de Cambio

<!-- Marca con 'x' las opciones que apliquen -->

- [ ] 🐛 Bug fix (cambio que arregla un issue)
- [ ] ✨ Nueva feature (cambio que añade funcionalidad)
- [ ] 💥 Breaking change (fix o feature que causa que funcionalidad existente no funcione como antes)
- [ ] 📝 Documentación (cambios solo en documentación)
- [ ] 🎨 Refactoring (cambios que no arreglan bugs ni añaden features)
- [ ] ⚡️ Mejora de performance
- [ ] ✅ Tests (añadir tests faltantes o corregir tests existentes)
- [ ] 🔧 Configuración (cambios en archivos de configuración)

## 🔗 Issue Relacionado

<!-- Si este PR cierra un issue, referenciarlo: -->
Closes #(issue number)

## 🧪 Cómo se Ha Testeado

<!-- Describe las pruebas que ejecutaste para verificar tus cambios -->

- [ ] Backend tests (pytest)
- [ ] Frontend tests (vitest)
- [ ] E2E tests (Playwright)
- [ ] Tests manuales

**Comandos ejecutados:**
```bash
# Backend
cd backend && pytest tests/ -v --cov

# Frontend
cd frontend && npm run test:coverage

# E2E
cd frontend && npx playwright test
```

## ✅ Checklist Pre-Merge

### Código
- [ ] Mi código sigue las convenciones del proyecto (ver `.claude/CLAUDE.md`)
- [ ] He realizado self-review de mi código
- [ ] He comentado mi código en áreas difíciles de entender
- [ ] Mis cambios no generan nuevos warnings
- [ ] He actualizado la documentación correspondiente

### Testing
- [ ] He añadido tests que prueban mi fix/feature
- [ ] Todos los tests nuevos y existentes pasan localmente
- [ ] Cobertura de código >= 80% (backend y frontend)
- [ ] Tests de integración pasan (si aplica)

### Backend (Python)
- [ ] Código pasa Flake8 (max line length 88)
- [ ] Código formateado con Black
- [ ] Type hints añadidos donde corresponde
- [ ] Docstrings en funciones/clases nuevas
- [ ] Migrations de DB creadas (si aplica)

### Frontend (React)
- [ ] Código pasa ESLint sin errores
- [ ] Código formateado con Prettier
- [ ] TypeScript strict mode sin errores
- [ ] Componentes responsive (mobile, tablet, desktop)
- [ ] Accessibility (WCAG 2.1 AA) verificada

### CI/CD
- [ ] Pipeline de Backend CI pasa ✅
- [ ] Pipeline de Frontend CI pasa ✅
- [ ] Pipeline de E2E pasa ✅
- [ ] No hay security vulnerabilities reportadas

## 📸 Screenshots (si aplica)

<!-- Si hay cambios visuales, incluir screenshots -->

### Antes
<!-- Screenshot del estado anterior -->

### Después
<!-- Screenshot del nuevo estado -->

### Mobile
<!-- Screenshot mobile si hay cambios responsive -->

## 🔍 Notas para Reviewers

<!-- Información adicional útil para quien revise el PR -->

## 📋 Post-Merge Checklist

- [ ] Eliminar rama feature después del merge
- [ ] Cerrar issue relacionado (si no se cierra automáticamente)
- [ ] Actualizar documentación en producción (si aplica)
- [ ] Monitorear logs post-deploy (primeras 24h)

---

**⚡️ Generado con** [Claude Code](https://claude.com/claude-code)
