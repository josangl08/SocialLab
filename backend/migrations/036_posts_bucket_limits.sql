-- 036: el bucket 'posts' admite vídeos de Reels/Stories y el tamaño máximo de Instagram
-- Graph API: Reels hasta 300 MB (MP4/MOV); imágenes JPEG hasta 8 MB. Idempotente.
UPDATE storage.buckets
SET file_size_limit = 314572800,  -- 300 MB
    allowed_mime_types = ARRAY['image/png', 'image/jpeg', 'image/jpg', 'video/mp4', 'video/quicktime']
WHERE id = 'posts';
