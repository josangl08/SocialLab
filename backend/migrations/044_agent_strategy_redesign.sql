-- Migración 044: agent-strategy-redesign. Idempotente.

-- "Usar mis datos" como valor por defecto para cuentas nuevas (AD-4).
-- best_times es JSONB; las cuentas existentes conservan su valor.
ALTER TABLE instagram_accounts
  ALTER COLUMN best_times SET DEFAULT '[]'::jsonb;

-- Respuestas del asistente "Generar con IA" (AD-8)
ALTER TABLE instagram_accounts
  ADD COLUMN IF NOT EXISTS strategy_wizard_answers JSONB;

-- Descartar sugerencias (AD-11)
ALTER TABLE agent_decisions
  DROP CONSTRAINT IF EXISTS agent_decisions_status_check,
  ADD CONSTRAINT agent_decisions_status_check
    CHECK (status IN ('active', 'overridden', 'suggested', 'accepted', 'dismissed'));
ALTER TABLE agent_decisions
  ADD COLUMN IF NOT EXISTS dismissed_at TIMESTAMPTZ;
