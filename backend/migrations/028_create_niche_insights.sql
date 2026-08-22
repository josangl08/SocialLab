-- Migration 028: Dynamic skill #2 — niche trend/best-practices research

CREATE TABLE IF NOT EXISTS niche_insights (
  id BIGSERIAL PRIMARY KEY,
  niche TEXT NOT NULL UNIQUE,
  brief TEXT,
  sources JSONB DEFAULT '[]',
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL
);

-- No RLS por cuenta: el brief de un nicho es compartido entre todas las cuentas
-- de ese nicho, no contiene datos específicos de ninguna cuenta.
