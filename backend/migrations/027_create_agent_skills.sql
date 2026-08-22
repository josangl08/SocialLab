-- Migration 027: Dynamic skill #1 — visual-content-vs-performance correlation

CREATE TABLE IF NOT EXISTS agent_skills (
  id BIGSERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  generated_code TEXT,
  last_result_summary TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (account_id, name)
);

ALTER TABLE agent_skills ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_skills_user_access ON agent_skills
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);
