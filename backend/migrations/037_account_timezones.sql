-- 037: opciones de zona horaria por cuenta de Instagram (AD-1)
-- primary_timezone: zona de referencia de la cuenta (null = navegador)
-- secondary_timezone: zona secundaria solo lectura (null = ninguna)
-- detected_timezone: zona del navegador reportada por el frontend (null si aún no reportada)

ALTER TABLE instagram_accounts
  ADD COLUMN IF NOT EXISTS primary_timezone   text,
  ADD COLUMN IF NOT EXISTS secondary_timezone text,
  ADD COLUMN IF NOT EXISTS detected_timezone  text;
