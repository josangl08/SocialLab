-- Migration 023: Decouple caption voice from account_type

ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS caption_voice TEXT DEFAULT NULL;
