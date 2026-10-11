-- Migración 034: Trial Reels (AD-10)
-- Soporte para Trial Reels (publicación solo a no seguidores con graduación manual o automática)
-- y métrica reels_skip_rate en post_performance.

ALTER TABLE posts
  ADD COLUMN IF NOT EXISTS trial_graduation TEXT
    CHECK (trial_graduation IN ('MANUAL', 'SS_PERFORMANCE'));

ALTER TABLE post_performance
  ADD COLUMN IF NOT EXISTS reels_skip_rate NUMERIC;
