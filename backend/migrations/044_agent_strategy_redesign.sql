-- Migración 044: agent-strategy-redesign. Idempotente.

-- "Usar mis datos" como valor por defecto para cuentas nuevas (AD-4).
-- best_times es JSONB; las cuentas existentes conservan su valor.
ALTER TABLE instagram_accounts
  ALTER COLUMN best_times SET DEFAULT '[]'::jsonb;
