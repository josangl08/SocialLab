CREATE TABLE monthly_campaigns (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    month_date   DATE NOT NULL,
    strategy_mode TEXT NOT NULL CHECK (strategy_mode IN ('commercial_campaign', 'personal_storyline')),
    title        TEXT NOT NULL,
    description  TEXT,
    milestones   JSONB DEFAULT '[]'::jsonb,
    weekly_focus JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (account_id, month_date)
);

ALTER TABLE monthly_campaigns ENABLE ROW LEVEL SECURITY;
-- Política: acceso solo si el account_id pertenece a un instagram_accounts.user_id = auth.uid()
CREATE POLICY monthly_campaigns_owner ON monthly_campaigns
    FOR ALL USING (
        account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
    );
