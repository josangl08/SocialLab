-- Migración 043: login_type por cuenta (facebook | instagram) para migración a Instagram Login (AD-1). Idempotente.

ALTER TABLE instagram_accounts
  ADD COLUMN IF NOT EXISTS login_type TEXT NOT NULL DEFAULT 'facebook';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'instagram_accounts_login_type_check'
  ) THEN
    ALTER TABLE instagram_accounts
      ADD CONSTRAINT instagram_accounts_login_type_check
      CHECK (login_type IN ('facebook', 'instagram'));
  END IF;
END $$;
