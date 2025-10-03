-- Migración 003: Crear tabla 'instagram_accounts'
-- Esta tabla almacena las credenciales de Instagram Business de cada usuario

CREATE TABLE IF NOT EXISTS instagram_accounts (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    instagram_business_account_id TEXT NOT NULL,
    long_lived_access_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraint para asegurar un solo registro por usuario
    CONSTRAINT unique_user_instagram UNIQUE(user_id)
);

-- Crear índice para búsquedas rápidas por user_id
CREATE INDEX IF NOT EXISTS idx_instagram_accounts_user_id
ON instagram_accounts(user_id);

-- Crear índice para verificar tokens próximos a expirar
CREATE INDEX IF NOT EXISTS idx_instagram_accounts_expires_at
ON instagram_accounts(expires_at);

-- Comentarios descriptivos
COMMENT ON TABLE instagram_accounts IS 'Almacena credenciales de Instagram Business de usuarios';
COMMENT ON COLUMN instagram_accounts.user_id IS 'UUID del usuario en Supabase Auth';
COMMENT ON COLUMN instagram_accounts.instagram_business_account_id IS 'ID de la cuenta Instagram Business';
COMMENT ON COLUMN instagram_accounts.long_lived_access_token IS 'Token de larga duración (60 días)';
COMMENT ON COLUMN instagram_accounts.expires_at IS 'Fecha de expiración del token';
