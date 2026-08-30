-- Hermes Mind: aceptar una sugerencia de horario/mix aplica el valor a la
-- configuración de la cuenta y marca la decisión como 'accepted'.

ALTER TABLE agent_decisions
  DROP CONSTRAINT IF EXISTS agent_decisions_status_check,
  ADD CONSTRAINT agent_decisions_status_check
    CHECK (status IN ('active', 'overridden', 'suggested', 'accepted'));

ALTER TABLE agent_decisions
  ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;
