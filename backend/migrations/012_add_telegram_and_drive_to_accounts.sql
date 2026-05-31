-- Fase 3: Añadir campos de integración Telegram y Google Drive a instagram_accounts
ALTER TABLE instagram_accounts
  ADD COLUMN IF NOT EXISTS telegram_chat_id TEXT,
  ADD COLUMN IF NOT EXISTS drive_folder_id TEXT;
