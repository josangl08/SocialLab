-- Migración 042: métricas de Stories y guardia de cuota de publicación (AD-2, AD-3). Idempotente.
-- La miniatura de las Stories usa posts.thumbnail_url_base (persistent-thumbnails).

ALTER TABLE post_performance
  ADD COLUMN IF NOT EXISTS views INTEGER,
  ADD COLUMN IF NOT EXISTS replies INTEGER,
  ADD COLUMN IF NOT EXISTS link_clicks INTEGER,
  ADD COLUMN IF NOT EXISTS story_navigation JSONB;   -- {tap_forward, tap_back, tap_exit, swipe_forward}

ALTER TABLE scheduled_jobs
  ADD COLUMN IF NOT EXISTS quota_deferrals INTEGER NOT NULL DEFAULT 0;

-- Actualizar constraint check_scheduled_jobs_status para incluir 'deferred_quota'
ALTER TABLE scheduled_jobs
  DROP CONSTRAINT IF EXISTS check_scheduled_jobs_status;

ALTER TABLE scheduled_jobs
  ADD CONSTRAINT check_scheduled_jobs_status
  CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'retrying', 'deferred_quota'));
