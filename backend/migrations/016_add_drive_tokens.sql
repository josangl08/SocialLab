-- Migration: Create drive_tokens table for per-user Google Drive credentials.
-- Auth: Antigravity CLI

CREATE TABLE IF NOT EXISTS drive_tokens (
  user_id       UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  access_token  TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  token_expiry  TIMESTAMPTZ NOT NULL,
  scopes        TEXT[] NOT NULL DEFAULT '{}',
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Only the service role can read/write tokens (no RLS exposure to frontend)
ALTER TABLE drive_tokens ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service role only" ON drive_tokens
  USING (false) WITH CHECK (false);
