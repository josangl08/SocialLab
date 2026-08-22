-- Migration 024: Track real Instagram token validity independent of expires_at

ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS token_invalid BOOLEAN DEFAULT FALSE;
