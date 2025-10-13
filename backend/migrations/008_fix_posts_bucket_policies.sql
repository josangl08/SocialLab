-- ========================================
-- Migración 008: Políticas RLS para bucket posts
-- ========================================
-- Esta migración configura las políticas de seguridad para el bucket 'posts'
-- que contiene las imágenes generadas de posts de Instagram.
--
-- Estructura de carpetas:
--   posts/
--     ├── drafts/      (posts con status='draft')
--     ├── scheduled/   (posts con status='scheduled')
--     └── published/   (posts con status='published')
-- ========================================

-- Política: Permitir a usuarios autenticados subir archivos al bucket posts
CREATE POLICY "Usuarios autenticados pueden subir a posts"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'posts');

-- Política: Permitir a usuarios autenticados actualizar archivos en posts
CREATE POLICY "Usuarios autenticados pueden actualizar en posts"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'posts');

-- Política: Permitir a usuarios autenticados eliminar archivos en posts
CREATE POLICY "Usuarios autenticados pueden eliminar en posts"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'posts');

-- Política: Permitir a todos leer archivos del bucket posts
CREATE POLICY "Todos pueden leer archivos de posts"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'posts');
