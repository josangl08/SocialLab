-- Fase 4: Añadir campos de token de vinculación Telegram a instagram_accounts
ALTER TABLE instagram_accounts
  ADD COLUMN IF NOT EXISTS telegram_link_token UUID,
  ADD COLUMN IF NOT EXISTS telegram_link_token_expires_at TIMESTAMPTZ;
