-- ============================================================
-- MIGRACIÓN 011: Tablas de Analytics Avanzado de Audiencia
-- Fecha: Octubre 2025
-- Descripción: Crear tablas para métricas de audiencia según
--              plan de Dashboard de Analytics Avanzado
-- ============================================================

-- ============================================================
-- TABLA 1: instagram_account_snapshots
-- Propósito: Histórico diario de métricas de cuenta
-- Uso: Gráficos de crecimiento de seguidores, reach, etc.
-- ============================================================

CREATE TABLE IF NOT EXISTS instagram_account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    follower_count INTEGER NOT NULL DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    media_count INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    profile_views INTEGER DEFAULT 0,
    website_clicks INTEGER DEFAULT 0,
    email_contacts INTEGER DEFAULT 0,
    phone_call_clicks INTEGER DEFAULT 0,
    text_message_clicks INTEGER DEFAULT 0,
    get_directions_clicks INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instagram_account_id, date)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_account_date
ON instagram_account_snapshots(instagram_account_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_date
ON instagram_account_snapshots(date DESC);

-- ============================================================
-- TABLA 2: audience_demographics
-- Propósito: Demografía de audiencia (género, edad, ubicación)
-- Uso: Gráficos de demografía, top ubicaciones
-- ============================================================

CREATE TABLE IF NOT EXISTS audience_demographics (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    sync_date DATE NOT NULL,
    metric_type TEXT NOT NULL,  -- 'audience_gender_age', 'audience_country', 'audience_city', 'audience_locale'
    data JSONB NOT NULL,         -- Datos crudos del API de Instagram
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instagram_account_id, metric_type)
);

CREATE INDEX IF NOT EXISTS idx_demographics_account
ON audience_demographics(instagram_account_id);

CREATE INDEX IF NOT EXISTS idx_demographics_type
ON audience_demographics(metric_type);

CREATE INDEX IF NOT EXISTS idx_demographics_sync_date
ON audience_demographics(sync_date DESC);

-- ============================================================
-- TABLA 3: online_followers_data
-- Propósito: Horas en las que los seguidores están online
-- Uso: Mapa de calor de actividad, recomendaciones de horario
-- ============================================================

CREATE TABLE IF NOT EXISTS online_followers_data (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    sync_date DATE NOT NULL,
    hour_data JSONB NOT NULL,  -- {"0": 125, "1": 98, ..., "23": 156}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instagram_account_id, sync_date)
);

CREATE INDEX IF NOT EXISTS idx_online_followers_account_date
ON online_followers_data(instagram_account_id, sync_date DESC);

-- ============================================================
-- TABLA 4: daily_account_metrics
-- Propósito: Métricas diarias agregadas de la cuenta
-- Uso: Análisis de crecimiento, tendencias
-- ============================================================

CREATE TABLE IF NOT EXISTS daily_account_metrics (
    id BIGSERIAL PRIMARY KEY,
    instagram_account_id INTEGER NOT NULL REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    new_followers INTEGER DEFAULT 0,
    followers_lost INTEGER DEFAULT 0,
    net_follower_change INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    profile_views INTEGER DEFAULT 0,
    website_clicks INTEGER DEFAULT 0,
    posts_published INTEGER DEFAULT 0,
    total_engagement INTEGER DEFAULT 0,  -- likes + comments + saves del día
    online_followers_by_hour JSONB,      -- Snapshot de actividad del día
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(instagram_account_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_account_date
ON daily_account_metrics(instagram_account_id, date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_metrics_date
ON daily_account_metrics(date DESC);

-- ============================================================
-- TRIGGERS
-- ============================================================

-- Trigger para actualizar updated_at en audience_demographics
DROP TRIGGER IF EXISTS update_audience_demographics_updated_at ON audience_demographics;
CREATE TRIGGER update_audience_demographics_updated_at
BEFORE UPDATE ON audience_demographics
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger para actualizar updated_at en daily_account_metrics
DROP TRIGGER IF EXISTS update_daily_metrics_updated_at ON daily_account_metrics;
CREATE TRIGGER update_daily_metrics_updated_at
BEFORE UPDATE ON daily_account_metrics
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================

ALTER TABLE instagram_account_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE audience_demographics ENABLE ROW LEVEL SECURITY;
ALTER TABLE online_followers_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_account_metrics ENABLE ROW LEVEL SECURITY;

-- Políticas: Solo el dueño de la cuenta puede ver sus datos
DROP POLICY IF EXISTS snapshots_user_access ON instagram_account_snapshots;
CREATE POLICY snapshots_user_access ON instagram_account_snapshots
FOR ALL USING (
    instagram_account_id IN (
        SELECT id FROM instagram_accounts WHERE user_id = auth.uid() AND is_active = true
    )
);

DROP POLICY IF EXISTS demographics_user_access ON audience_demographics;
CREATE POLICY demographics_user_access ON audience_demographics
FOR ALL USING (
    instagram_account_id IN (
        SELECT id FROM instagram_accounts WHERE user_id = auth.uid() AND is_active = true
    )
);

DROP POLICY IF EXISTS online_followers_user_access ON online_followers_data;
CREATE POLICY online_followers_user_access ON online_followers_data
FOR ALL USING (
    instagram_account_id IN (
        SELECT id FROM instagram_accounts WHERE user_id = auth.uid() AND is_active = true
    )
);

DROP POLICY IF EXISTS daily_metrics_user_access ON daily_account_metrics;
CREATE POLICY daily_metrics_user_access ON daily_account_metrics
FOR ALL USING (
    instagram_account_id IN (
        SELECT id FROM instagram_accounts WHERE user_id = auth.uid() AND is_active = true
    )
);

-- ============================================================
-- VERIFICACIÓN
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Migración 011 completada';
    RAISE NOTICE '   - instagram_account_snapshots: Histórico de métricas';
    RAISE NOTICE '   - audience_demographics: Datos demográficos';
    RAISE NOTICE '   - online_followers_data: Actividad de seguidores';
    RAISE NOTICE '   - daily_account_metrics: Métricas diarias agregadas';
    RAISE NOTICE '   - Triggers y RLS configurados';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Listo para Analytics Avanzado!';
END $$;
