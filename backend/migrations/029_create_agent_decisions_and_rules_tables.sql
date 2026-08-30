-- Migration 029: Create account_brand_rules and agent_decisions tables for Hermes Mind

CREATE TABLE IF NOT EXISTS account_brand_rules (
  id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  rule_type TEXT NOT NULL CHECK (rule_type IN ('tone', 'frequency', 'format', 'topic', 'brand_safety', 'other')),
  rule_text TEXT NOT NULL,
  source_correction_id BIGINT REFERENCES agent_memory(id) ON DELETE SET NULL,
  confidence FLOAT NOT NULL DEFAULT 1.0,
  is_active BOOLEAN NOT NULL DEFAULT true,
  times_applied INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_decisions (
  id BIGSERIAL PRIMARY KEY,
  account_id BIGINT NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  session_id UUID,
  decision_type TEXT NOT NULL,
  related_post_id BIGINT REFERENCES posts(id) ON DELETE SET NULL,
  related_proposal_id TEXT,
  applied_rule_ids BIGINT[] DEFAULT '{}',
  applied_rule_labels JSONB DEFAULT '[]',
  confidence_score FLOAT NOT NULL DEFAULT 0.5,
  rationale TEXT,
  tool_args JSONB,
  tool_result JSONB,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'overridden')),
  overridden_at TIMESTAMPTZ,
  override_correction_id BIGINT REFERENCES agent_memory(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_account_brand_rules_account ON account_brand_rules(account_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_account ON agent_decisions(account_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_session ON agent_decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_post ON agent_decisions(related_post_id);

-- RLS Policies
ALTER TABLE account_brand_rules ENABLE ROW LEVEL SECURITY;

CREATE POLICY account_brand_rules_user_access ON account_brand_rules
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);

ALTER TABLE agent_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_decisions_user_access ON agent_decisions
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);
