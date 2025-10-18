# Claude Code Hooks

Este directorio contiene hooks personalizados para Claude Code.

## Hooks Disponibles

### `on-notification-say.sh`

**Propósito:** Lee notificaciones en voz alta usando el comando `say` de macOS.

**Uso:** Este hook se activa automáticamente cuando Claude Code envía una notificación.

**Configuración en `settings.json`:**
```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/on-notification-say.sh",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

**Nota:** Solo funciona en macOS. En otros sistemas operativos, puedes adaptarlo para usar:
- **Linux:** `espeak` o `festival`
- **Windows:** PowerShell `Add-Type -AssemblyName System.Speech`

## Hooks Configurados en settings.json

Los siguientes hooks están configurados directamente en `.claude/settings.json`:

### `user-prompt-submit`
Bloquea prompts que contengan keywords relacionadas con seguridad.

### `pre-commit`
Ejecuta Flake8 en archivos Python antes de hacer commit.

### `pre-test`
Muestra notificación cuando se ejecutan tests.

## Crear Custom Hooks

Para crear tus propios hooks:

1. Crea un script `.sh` en este directorio
2. Hazlo ejecutable: `chmod +x .claude/hooks/tu-hook.sh`
3. Configúralo en `.claude/settings.json`

### Ejemplo: Hook post-test

```bash
#!/usr/bin/env bash
# .claude/hooks/post-test-notify.sh

set -euo pipefail

payload="$(cat)"
success=$(echo "$payload" | jq -r '.success')

if [ "$success" = "true" ]; then
    /usr/bin/say "Tests passed successfully"
else
    /usr/bin/say "Tests failed, check the results"
fi
```

Luego en `settings.json`:
```json
{
  "hooks": {
    "post-test": {
      "enabled": true,
      "command": ".claude/hooks/post-test-notify.sh",
      "description": "Notificación después de tests"
    }
  }
}
```

## Hooks Disponibles en Claude Code

- `user-prompt-submit`: Antes de enviar un prompt
- `pre-commit`: Antes de hacer commit
- `pre-test`: Antes de ejecutar tests
- `post-test`: Después de ejecutar tests
- `Notification`: Cuando hay notificaciones
- `Stop`: Cuando Claude termina
- `SubagentStop`: Cuando un sub-agente termina

## Referencias

- [Claude Code Hooks Documentation](https://docs.claude.com/claude-code/hooks)
