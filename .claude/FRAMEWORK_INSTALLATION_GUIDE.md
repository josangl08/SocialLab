# 🚀 GUÍA DE INSTALACIÓN DEL FRAMEWORK GLOBAL

## 📍 ARQUITECTURA DEL SISTEMA

El framework tiene dos niveles:

1. **Framework Global** (`~/.claude-framework/`)
   - Templates reutilizables
   - Scripts de generación
   - Plugins del ecosistema
   - Documentación

2. **Proyecto Local** (`/tu/proyecto/.claude/`)
   - Configuración específica (project.config.json)
   - Agentes generados
   - Sesiones y documentación del proyecto

---

## 🛠️ INSTALACIÓN DEL FRAMEWORK GLOBAL

### **Método 1: Instalación Manual (Recomendado para desarrollo)**

```bash
# 1. Crear directorio del framework global
mkdir -p ~/.claude-framework
cd ~/.claude-framework

# 2. Copiar estructura base
# (Desde el análisis que hicimos)
mkdir -p {schema,templates/{agents,commands},plugins/{core,community},scripts,docs}

# 3. Instalar dependencias Python
cat > requirements.txt << 'EOF'
pyyaml>=6.0
jinja2>=3.1.0
jsonschema>=4.17.0
click>=8.1.0
inquirer>=3.1.0
rich>=13.0.0
EOF

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Crear alias global (añadir a ~/.zshrc o ~/.bashrc)
echo 'alias claude-init="python ~/.claude-framework/scripts/init-project.py"' >> ~/.zshrc
echo 'alias claude-plugin="python ~/.claude-framework/scripts/plugin-manager.py"' >> ~/.zshrc
echo 'alias claude-validate="python ~/.claude-framework/scripts/validate-config.py"' >> ~/.zshrc
source ~/.zshrc
```

---

### **Método 2: Git Clone (Cuando esté en repositorio)**

```bash
# Clonar framework
git clone https://github.com/tu-org/claude-code-framework.git ~/.claude-framework

# Instalar
cd ~/.claude-framework
./install.sh

# Verificar
claude-init --version
# → Claude Code Framework v2.0.0
```

---

### **Método 3: Con gestor de paquetes (Futuro)**

```bash
# Con pip (cuando lo publiquemos)
pip install claude-code-framework

# Con npm (versión Node.js)
npm install -g @claude/code-framework

# Con homebrew (macOS)
brew install claude-code-framework
```

---

## 📦 ESTRUCTURA DEL FRAMEWORK GLOBAL

```
~/.claude-framework/
├── VERSION                        # v2.0.0
│
├── schema/                        # ⭐ Schemas de validación
│   ├── v1.0.0.json
│   ├── v2.0.0.json
│   ├── latest.json -> v2.0.0.json
│   └── plugins/
│       └── *.schema.json
│
├── templates/                     # ⭐ Templates parametrizables
│   ├── agents/
│   │   ├── _base-agent.hbs              # Template base
│   │   ├── backend-architect.hbs        # Por framework
│   │   ├── frontend-architect.hbs
│   │   ├── test-engineer.hbs
│   │   └── ...
│   │
│   ├── commands/
│   │   ├── explore-plan.md              # ✅ 100% universal
│   │   ├── implement-feedback.md        # ✅ 100% universal
│   │   ├── start-working-on-issue.md    # ✅ 100% universal
│   │   └── ...
│   │
│   ├── CLAUDE.template.md               # Template CLAUDE.md
│   ├── settings.template.json           # Template settings.json
│   └── project.config.template.json     # Template config
│
├── plugins/                       # ⭐ Sistema de plugins
│   ├── core/                      # Incluidos
│   │   ├── fullstack/
│   │   │   ├── plugin.json
│   │   │   ├── agents/
│   │   │   └── templates/
│   │   │
│   │   ├── python-ui/             # Streamlit/Dash
│   │   ├── mobile/                # React Native/Flutter
│   │   └── desktop/               # Tauri/Electron
│   │
│   └── community/                 # Descargables
│       ├── web3/
│       ├── ai-agents/
│       └── ...
│
├── scripts/                       # ⭐ Scripts del framework
│   ├── init-project.py            # Inicializar proyecto
│   ├── generate-agents.py         # Generar agentes
│   ├── validate-config.py         # Validar config
│   ├── plugin-manager.py          # Gestor plugins
│   ├── migrate-config.py          # Migraciones
│   └── update-framework.py        # Auto-actualización
│
├── docs/                          # Documentación
│   ├── getting-started.md
│   ├── configuration.md
│   ├── plugin-development.md
│   ├── contributing.md
│   └── examples/
│       ├── fullstack-react-fastapi.md
│       ├── streamlit-dashboard.md
│       └── mobile-react-native.md
│
├── install.sh                     # Instalador
├── requirements.txt               # Python deps
└── README.md
```

---

## 🎯 FLUJO DE USO COMPLETO

### **1. Primer Uso: Instalar Framework**

```bash
# Instalar framework global (UNA SOLA VEZ)
git clone https://github.com/tu-org/claude-code-framework.git ~/.claude-framework
cd ~/.claude-framework
./install.sh

# Configurar alias
echo 'alias claude-init="python ~/.claude-framework/scripts/init-project.py"' >> ~/.zshrc
source ~/.zshrc
```

---

### **2. Crear Nuevo Proyecto**

```bash
# Ir a carpeta del proyecto
cd ~/Proyectos/MiNuevoProyecto

# Inicializar con wizard interactivo
claude-init

# O con flags (sin interacción)
claude-init \
  --name "MiProyecto" \
  --type fullstack \
  --backend python:fastapi \
  --frontend typescript:react \
  --database postgresql:supabase

# Resultado:
# → Se crea .claude/ con todo configurado
# → Se genera CLAUDE.md personalizado
# → Se crean agentes específicos
```

---

### **3. Trabajar en el Proyecto**

```bash
# Workflow normal (comandos ya configurados)
/explore-plan nueva_feature

# Consultar agentes generados
ls .claude/agents/
# → fastapi-backend-architect.md
# → react-frontend-architect.md
# → python-test-engineer.md

# Validar configuración
claude-validate

# Instalar plugin adicional
claude-plugin install @community/web3-plugin
```

---

### **4. Actualizar Framework**

```bash
# Actualizar framework global (aplica a TODOS los proyectos futuros)
cd ~/.claude-framework
git pull origin main
./install.sh

# Migrar proyecto existente a nueva versión
cd ~/Proyectos/MiProyecto
claude-migrate --to 2.1.0
```

---

## 📝 ARCHIVO: init-project.py (Pseudocódigo)

```python
#!/usr/bin/env python3
"""
Claude Code Framework - Project Initializer
Ejecutar desde la carpeta del proyecto que quieres inicializar
"""

import os
import sys
import json
import inquirer
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Detectar framework global
FRAMEWORK_HOME = Path.home() / ".claude-framework"

if not FRAMEWORK_HOME.exists():
    print("❌ Framework not found at ~/.claude-framework")
    print("   Please install: https://github.com/.../INSTALL.md")
    sys.exit(1)

# Detectar carpeta actual del proyecto
PROJECT_ROOT = Path.cwd()

def interactive_wizard():
    """Wizard interactivo para configurar proyecto"""

    # Paso 1: Información del proyecto
    project_name = inquirer.text(
        message="Project name",
        default=PROJECT_ROOT.name
    )

    project_type = inquirer.list_input(
        message="Project type",
        choices=[
            "Fullstack (backend + frontend)",
            "Backend only",
            "Frontend only",
            "Python UI App (Streamlit/Dash)",
            "Mobile App",
            "Desktop App"
        ]
    )

    # Paso 2-5: Preguntas según el tipo
    # (Similar al flujo mostrado arriba)

    return {
        "project": {"name": project_name, "type": project_type},
        "stack": {...},
        # ... resto de config
    }

def generate_project_files(config):
    """Genera archivos del proyecto basado en config"""

    # 1. Crear estructura .claude/
    claude_dir = PROJECT_ROOT / ".claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "agents").mkdir(exist_ok=True)
    (claude_dir / "commands").mkdir(exist_ok=True)
    (claude_dir / "sessions").mkdir(exist_ok=True)
    (claude_dir / "doc").mkdir(exist_ok=True)

    # 2. Guardar project.config.json
    config_path = claude_dir / "project.config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # 3. Generar agentes desde templates
    generate_agents(config)

    # 4. Copiar comandos universales
    copy_universal_commands()

    # 5. Generar CLAUDE.md
    generate_claude_md(config)

    # 6. Generar settings.json
    generate_settings_json(config)

    print("✅ Project initialized successfully!")

def generate_agents(config):
    """Genera agentes específicos desde templates"""

    env = Environment(loader=FileSystemLoader(
        str(FRAMEWORK_HOME / "templates/agents")
    ))

    # Según el stack, generar agentes correspondientes
    backend_fw = config["stack"]["backend"]["framework"]
    frontend_fw = config["stack"]["frontend"]["framework"]

    # Renderizar backend-architect
    template = env.get_template("backend-architect.hbs")
    output = template.render(config)

    output_path = PROJECT_ROOT / ".claude/agents" / f"{backend_fw}-backend-architect.md"
    with open(output_path, "w") as f:
        f.write(output)

    # Similar para frontend, test, etc.

def copy_universal_commands():
    """Copia comandos 100% universales"""
    import shutil

    commands_src = FRAMEWORK_HOME / "templates/commands"
    commands_dst = PROJECT_ROOT / ".claude/commands"

    for cmd_file in commands_src.glob("*.md"):
        shutil.copy(cmd_file, commands_dst)

if __name__ == "__main__":
    print("🚀 Claude Code Framework - Project Initialization")
    print("=" * 60)

    # Wizard interactivo
    config = interactive_wizard()

    # Generar archivos
    generate_project_files(config)

    print("\n📚 Next steps:")
    print("  1. Review: .claude/project.config.json")
    print("  2. Start developing: /explore-plan {feature_name}")
    print("  3. Documentation: ~/.claude-framework/docs/")
```

---

## 🔄 ACTUALIZACIÓN DE PROYECTOS EXISTENTES

```bash
# Si ya tienes un proyecto con .claude/ antiguo

cd ~/Proyectos/ProyectoViejo

# Detectar versión actual
cat .claude/project.config.json | grep version
# → "version": "1.0.0"

# Migrar a nueva versión
claude-migrate --to 2.0.0

# El script:
# 1. Hace backup de .claude/
# 2. Migra project.config.json
# 3. Regenera agentes con nuevos templates
# 4. Preserva sessions/ y doc/
```

---

## 🎯 RESUMEN

**Framework Global:**
- Ubicación: `~/.claude-framework/`
- Contiene: Templates, schemas, plugins, scripts
- Se instala UNA VEZ
- Se actualiza con `git pull`

**Proyecto Local:**
- Ubicación: `/tu/proyecto/.claude/`
- Contiene: Config específica, agentes generados, sesiones
- Se crea con: `claude-init`
- Es específico de ese proyecto

**Beneficios:**
✅ Templates globales → Reutilizables en todos los proyectos
✅ Configuración local → Cada proyecto tiene su stack
✅ Actualizaciones fáciles → `git pull` en framework
✅ No duplicar código → Templates en un solo lugar

---

## 📋 CHECKLIST DE INSTALACIÓN

- [ ] Clonar framework en `~/.claude-framework/`
- [ ] Ejecutar `install.sh`
- [ ] Configurar alias en `~/.zshrc`
- [ ] Verificar: `claude-init --version`
- [ ] Probar en proyecto test: `cd ~/test && claude-init`
- [ ] Revisar archivos generados
- [ ] Ejecutar `/explore-plan test_feature`

---

**Última actualización:** 2025-01-18
**Framework Version:** 2.0.0
