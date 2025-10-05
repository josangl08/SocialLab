-- ============================================================
-- MIGRACIÓN 006: Agregar IDs faltantes y Schema Completo
-- Fecha: Octubre 2025
-- Descripción: Corregir tablas base y crear nuevas tablas
-- ============================================================

-- ============================================================
-- PASO 1: AGREGAR COLUMNA ID A INSTAGRAM_ACCOUNTS
-- ============================================================

-- Agregar columna id a instagram_accounts si no existe
DO $$
BEGIN
    -- Verificar si ya existe
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'instagram_accounts' AND column_name = 'id'
    ) THEN
        -- Agregar columna id
        ALTER TABLE instagram_accounts ADD COLUMN id SERIAL;

        -- Establecerla como PRIMARY KEY
        -- Primero eliminar constraint existente si hay
        ALTER TABLE instagram_accounts DROP CONSTRAINT IF EXISTS instagram_accounts_pkey;

        -- Agregar nueva PRIMARY KEY
        ALTER TABLE instagram_accounts ADD PRIMARY KEY (id);

        RAISE NOTICE 'Columna id agregada a instagram_accounts';
    ELSE
        RAISE NOTICE 'Columna id ya existe en instagram_accounts';
    END IF;
END $$;

-- ============================================================
-- PASO 2: ACTUALIZAR TABLAS EXISTENTES
-- ============================================================

-- Actualizar instagram_accounts para múltiples cuentas
ALTER TABLE instagram_accounts
DROP CONSTRAINT IF EXISTS unique_user_instagram;

ALTER TABLE instagram_accounts
ADD COLUMN IF NOT EXISTS account_name TEXT,
ADD COLUMN IF NOT EXISTS username TEXT,
ADD COLUMN IF NOT EXISTS profile_picture_url TEXT,
ADD COLUMN IF NOT EXISTS followers_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true,
ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;

-- Índices para instagram_accounts
CREATE UNIQUE INDEX IF NOT EXISTS idx_instagram_accounts_user_business
ON instagram_accounts(user_id, instagram_business_account_id);

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_active
ON instagram_accounts(is_active) WHERE is_active = true;

CREATE INDEX IF NOT EXISTS idx_instagram_accounts_username
ON instagram_accounts(username);

-- Actualizar posts para referencias externas
ALTER TABLE posts
ADD COLUMN IF NOT EXISTS instagram_account_id INTEGER,
ADD COLUMN IF NOT EXISTS source_data_id TEXT,
ADD COLUMN IF NOT EXISTS source_data_url TEXT,
ADD COLUMN IF NOT EXISTS template_id INTEGER,
ADD COLUMN IF NOT EXISTS ai_caption_raw TEXT,
ADD COLUMN IF NOT EXISTS ai_metadata JSONB,
ADD COLUMN IF NOT EXISTS is_ai_generated BOOLEAN DEFAULT false;

-- Índices para posts
CREATE INDEX IF NOT EXISTS idx_posts_instagram_account
ON posts(instagram_account_id);

CREATE INDEX IF NOT EXISTS idx_posts_source_data
ON posts(source_data_id) WHERE source_data_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_posts_template
ON posts(template_id) WHERE template_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_posts_ai_generated
ON posts(is_ai_generated) WHERE is_ai_generated = true;

-- ============================================================
-- PASO 3: CREAR NUEVAS TABLAS
-- ============================================================

-- Tabla: template_categories
CREATE TABLE IF NOT EXISTS template_categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    icon TEXT,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_template_categories_order
ON template_categories(display_order);

-- Datos iniciales
INSERT INTO template_categories (name, description, display_order) VALUES
    ('Player Stats', 'Templates para estadísticas de jugadores', 1),
    ('Team Performance', 'Templates para estadísticas de equipos', 2),
    ('Match Preview', 'Templates para previews de partidos', 3),
    ('Match Result', 'Templates para resultados de partidos', 4),
    ('League Table', 'Templates para tablas de clasificación', 5),
    ('Story', 'Templates para Instagram Stories (9:16)', 6),
    ('Carousel', 'Templates para posts carousel', 7),
    ('Generic', 'Templates genéricos reutilizables', 99)
ON CONFLICT (name) DO NOTHING;

-- Tabla: templates
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    category_id INTEGER REFERENCES template_categories(id) ON DELETE SET NULL,
    image_url TEXT,
    selection_rules JSONB DEFAULT '{}'::jsonb,
    template_config JSONB DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 50,
    use_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_templates_user ON templates(user_id);
CREATE INDEX IF NOT EXISTS idx_templates_account ON templates(instagram_account_id);
CREATE INDEX IF NOT EXISTS idx_templates_category ON templates(category_id);
CREATE INDEX IF NOT EXISTS idx_templates_active ON templates(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_templates_priority ON templates(priority DESC);

-- Tabla: ai_strategy
CREATE TABLE IF NOT EXISTS ai_strategy (
    id SERIAL PRIMARY KEY,
    instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE UNIQUE,
    tone TEXT DEFAULT 'energetic',
    language TEXT DEFAULT 'es',
    emoji_usage TEXT DEFAULT 'moderate',
    content_preferences JSONB DEFAULT '{}'::jsonb,
    hashtag_strategy JSONB DEFAULT '{"max": 7}'::jsonb,
    ai_model TEXT DEFAULT 'gemini-1.5-flash-latest',
    custom_instructions TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_strategy_account ON ai_strategy(instagram_account_id);

-- Tabla: content_generation_queue
CREATE TABLE IF NOT EXISTS content_generation_queue (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    instagram_account_id INTEGER REFERENCES instagram_accounts(id) ON DELETE CASCADE,
    export_id TEXT NOT NULL,
    export_metadata JSONB,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    status TEXT DEFAULT 'pending',
    post_id INTEGER REFERENCES posts(id) ON DELETE SET NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_queue_status ON content_generation_queue(status);
CREATE INDEX IF NOT EXISTS idx_queue_user ON content_generation_queue(user_id);

-- Tabla: content_generation_history
CREATE TABLE IF NOT EXISTS content_generation_history (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    post_id INTEGER REFERENCES posts(id) ON DELETE SET NULL,
    export_id TEXT NOT NULL,
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    generation_metadata JSONB,
    status TEXT DEFAULT 'completed',
    error_message TEXT,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_generation_history_user ON content_generation_history(user_id);

-- Tabla: post_performance
CREATE TABLE IF NOT EXISTS post_performance (
    id SERIAL PRIMARY KEY,
    post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE UNIQUE,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    reach INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5,2),
    template_id INTEGER REFERENCES templates(id) ON DELETE SET NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_performance_post ON post_performance(post_id);
CREATE INDEX IF NOT EXISTS idx_performance_engagement ON post_performance(engagement_rate DESC NULLS LAST);

-- Tabla: scheduled_jobs
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT NOT NULL,
    job_data JSONB NOT NULL,
    scheduled_for TIMESTAMPTZ NOT NULL,
    executed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_type ON scheduled_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status ON scheduled_jobs(status);

-- ============================================================
-- PASO 4: FOREIGN KEYS PARA POSTS
-- ============================================================

ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_instagram_account_id_fkey;
ALTER TABLE posts ADD CONSTRAINT posts_instagram_account_id_fkey
FOREIGN KEY (instagram_account_id) REFERENCES instagram_accounts(id) ON DELETE CASCADE;

ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_template_id_fkey;
ALTER TABLE posts ADD CONSTRAINT posts_template_id_fkey
FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL;

-- ============================================================
-- PASO 5: TRIGGERS
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_templates_updated_at ON templates;
CREATE TRIGGER update_templates_updated_at
BEFORE UPDATE ON templates
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_ai_strategy_updated_at ON ai_strategy;
CREATE TRIGGER update_ai_strategy_updated_at
BEFORE UPDATE ON ai_strategy
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Engagement rate
CREATE OR REPLACE FUNCTION calculate_engagement_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.reach > 0 THEN
        NEW.engagement_rate := (
            (NEW.likes + NEW.comments + NEW.shares + NEW.saves)::DECIMAL / NEW.reach * 100
        );
    ELSE
        NEW.engagement_rate := 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS calculate_engagement_on_update ON post_performance;
CREATE TRIGGER calculate_engagement_on_update
BEFORE INSERT OR UPDATE ON post_performance
FOR EACH ROW EXECUTE FUNCTION calculate_engagement_rate();

-- ============================================================
-- PASO 6: RLS
-- ============================================================

ALTER TABLE templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_strategy ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_generation_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS templates_user_access ON templates;
CREATE POLICY templates_user_access ON templates
FOR ALL USING (user_id = auth.uid());

DROP POLICY IF EXISTS ai_strategy_user_access ON ai_strategy;
CREATE POLICY ai_strategy_user_access ON ai_strategy
FOR ALL USING (
    instagram_account_id IN (
        SELECT id FROM instagram_accounts WHERE user_id = auth.uid()
    )
);

DROP POLICY IF EXISTS queue_user_access ON content_generation_queue;
CREATE POLICY queue_user_access ON content_generation_queue
FOR ALL USING (user_id = auth.uid());

-- ============================================================
-- VERIFICACIÓN
-- ============================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Migración 006 completada';
    RAISE NOTICE '   - instagram_accounts: id agregado';
    RAISE NOTICE '   - 7 tablas nuevas creadas';
    RAISE NOTICE '   - Foreign keys establecidas';
    RAISE NOTICE '   - Triggers y RLS configurados';
END $$;
