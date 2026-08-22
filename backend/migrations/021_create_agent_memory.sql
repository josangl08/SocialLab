CREATE TABLE agent_memory (
  id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES instagram_accounts(id),
  session_id UUID NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('system', 'user', 'model', 'tool')),
  content JSONB,
  tool_name TEXT,
  tool_args JSONB,
  tool_result JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_agent_memory_account_session ON agent_memory(account_id, session_id);

ALTER TABLE agent_memory ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_memory_user_access ON agent_memory
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);
