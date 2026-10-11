-- Migración 035: crecimiento de seguidores y toques en botones de contacto (AD-9)
-- Valores de las últimas 24 h en el momento del sync; la serie diaria se reconstruye por fecha.

ALTER TABLE instagram_account_snapshots
  ADD COLUMN IF NOT EXISTS follows INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS unfollows INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS profile_links_taps INTEGER NOT NULL DEFAULT 0;
