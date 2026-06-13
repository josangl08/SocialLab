-- Migration 015: Extend agent strategy fields on instagram_accounts

ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS default_tone       TEXT DEFAULT 'energetic';
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS default_language   TEXT DEFAULT 'es';
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS posting_frequency  TEXT DEFAULT 'few_times_week';
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS best_times         JSONB DEFAULT '["09:00","18:00"]';
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS content_pillars    JSONB DEFAULT '[]';
ALTER TABLE instagram_accounts ADD COLUMN IF NOT EXISTS hashtag_strategy   TEXT DEFAULT 'moderate';
