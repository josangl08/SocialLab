#!/usr/bin/env bash
# .claude/hooks/on-notification-say.sh
# Hook que lee notificaciones en voz alta (macOS only)
# Copiado de claude-code-demo

set -euo pipefail

payload="$(cat)"
message=$(echo "$payload" | jq -r '.message')

# Speak it (absolute path to avoid PATH issues)
/usr/bin/say "$message"
