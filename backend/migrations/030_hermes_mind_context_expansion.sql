ALTER TABLE account_brand_rules
  ADD COLUMN previous_version_id BIGINT REFERENCES account_brand_rules(id),
  ADD COLUMN conflicts_with_id BIGINT REFERENCES account_brand_rules(id);

ALTER TABLE agent_decisions
  ADD COLUMN campaign_id UUID REFERENCES monthly_campaigns(id) ON DELETE SET NULL;

-- Constraint update for suggested status
ALTER TABLE agent_decisions
  DROP CONSTRAINT IF EXISTS agent_decisions_status_check,
  ADD CONSTRAINT agent_decisions_status_check
    CHECK (status IN ('active', 'overridden', 'suggested'));

CREATE INDEX IF NOT EXISTS idx_account_brand_rules_previous_version ON account_brand_rules(previous_version_id);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_campaign ON agent_decisions(campaign_id);
