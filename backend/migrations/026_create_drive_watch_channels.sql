-- Migration 026: Reactive Drive webhook analysis (Push Notification channels)

CREATE TABLE IF NOT EXISTS drive_watch_channels (
  id BIGSERIAL PRIMARY KEY,
  account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  channel_id TEXT NOT NULL UNIQUE,
  resource_id TEXT NOT NULL,
  folder_id TEXT NOT NULL,
  channel_token TEXT NOT NULL,
  expiration TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_drive_watch_channels_expiration ON drive_watch_channels(expiration);
CREATE INDEX IF NOT EXISTS idx_drive_watch_channels_account_id ON drive_watch_channels(account_id);

ALTER TABLE drive_watch_channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY drive_watch_channels_user_access ON drive_watch_channels
FOR ALL USING (
  account_id IN (SELECT id FROM instagram_accounts WHERE user_id = auth.uid())
);
