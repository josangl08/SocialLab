-- Migración 020: Índices faltantes en content_proposals, visual_analyses, agent_logs
-- Estas tablas se filtran por account_id (RLS de la migración 019 y queries de la app)
-- sin índice de soporte, forzando sequential scans.

CREATE INDEX IF NOT EXISTS idx_content_proposals_account_status
  ON content_proposals(account_id, status);

CREATE INDEX IF NOT EXISTS idx_content_proposals_status
  ON content_proposals(status);

CREATE INDEX IF NOT EXISTS idx_visual_analyses_account_id
  ON visual_analyses(account_id);

CREATE INDEX IF NOT EXISTS idx_agent_logs_account_id
  ON agent_logs(account_id);

DO $$
BEGIN
  RAISE NOTICE 'Migración 020 aplicada: índices creados en content_proposals, visual_analyses, agent_logs';
END $$;
