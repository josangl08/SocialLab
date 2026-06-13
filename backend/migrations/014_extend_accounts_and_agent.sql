-- Migration 014

-- Strategy fields on instagram_accounts
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS account_type TEXT DEFAULT 'personal';
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS sector TEXT;
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS purpose TEXT;
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS target_audience TEXT;
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS style_guide TEXT;
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS last_agent_sync TIMESTAMPTZ;

-- Image analysis cache
CREATE TABLE IF NOT EXISTS visual_analyses (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id     INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  drive_file_id  TEXT NOT NULL UNIQUE,
  file_name      TEXT,
  gemini_description JSONB,
  suggested_caption  TEXT,
  processed_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Weekly proposals
CREATE TABLE IF NOT EXISTS content_proposals (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id          INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  week_start          DATE NOT NULL,
  slots               JSONB NOT NULL,
  status              TEXT NOT NULL DEFAULT 'pending_approval',
  telegram_message_id TEXT,
  created_at          TIMESTAMPTZ DEFAULT NOW(),
  resolved_at         TIMESTAMPTZ
);

-- Agent execution log
CREATE TABLE IF NOT EXISTS agent_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id       INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
  run_at           TIMESTAMPTZ DEFAULT NOW(),
  images_scanned   INT DEFAULT 0,
  images_analyzed  INT DEFAULT 0,
  posts_drafted    INT DEFAULT 0,
  error            TEXT,
  duration_ms      INT
);
