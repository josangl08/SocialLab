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

-- Caché de Business Discovery por referente (AD-10)
CREATE TABLE IF NOT EXISTS reference_account_snapshots (
  id BIGSERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  username TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('ok', 'not_professional', 'not_found', 'error')),
  error_message TEXT,
  payload JSONB,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (account_id, username)
);
ALTER TABLE reference_account_snapshots ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS reference_account_snapshots_owner_read ON reference_account_snapshots;
CREATE POLICY reference_account_snapshots_owner_read ON reference_account_snapshots
FOR SELECT USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);
