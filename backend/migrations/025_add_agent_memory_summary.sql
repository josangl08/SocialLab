-- Migration 025: Persistent cross-session memory (correction summary)

ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS agent_memory_summary TEXT;
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS agent_memory_summary_updated_at TIMESTAMPTZ;

ALTER TABLE agent_memory DROP CONSTRAINT IF EXISTS agent_memory_role_check;
ALTER TABLE agent_memory ADD CONSTRAINT agent_memory_role_check
  CHECK (role IN ('system', 'user', 'model', 'tool', 'correction'));
