-- Migración 032: rellenar posts.user_id NULL.
--
-- Los posts creados por Hermes vía supabase_create_post (cliente service-role,
-- salta RLS) se insertaban sin user_id. /api/posts lee con el cliente del usuario
-- (RLS: user_id = auth.uid()), así que esos posts eran invisibles en el calendario
-- aunque existían. A partir de la corrección en supabase_create_post el user_id se
-- resuelve desde la cuenta; esta migración arregla las filas ya creadas.
--
-- Idempotente: solo toca filas con user_id IS NULL.

UPDATE posts p
SET user_id = ia.user_id
FROM instagram_accounts ia
WHERE p.instagram_account_id = ia.id
  AND p.user_id IS NULL;
