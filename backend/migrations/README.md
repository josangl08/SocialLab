# Migraciones de Base de Datos

## Orden de Ejecución

Las migraciones deben ejecutarse en orden cronológico:

1. `001_add_instagram_post_id.sql` - Columna para IDs de Instagram
2. `002_ensure_instagram_columns.sql` - Columnas adicionales para posts
3. `003_create_instagram_accounts_table.sql` - Tabla de cuentas Instagram
4. `004_add_media_product_type.sql` - Tipo de contenido (FEED, REELS, STORY)
5. `005_add_scheduled_publish_time.sql` - Programación de publicaciones
6. `006_add_missing_ids_and_schema.sql` - **Schema completo** (templates, ai_strategy, etc.)
20. `020_db_indices_faltantes.sql` - Índices faltantes en content_proposals, visual_analyses, y agent_logs
32. `032_backfill_hermes_posts_user_id.sql` - Rellena posts.user_id NULL (posts de Hermes creados sin user_id)
33. `033_content_studio.sql` - Columnas content_format, content_structure, quality_report, matrix_role en posts y humanizer_enabled, banned_phrases en instagram_accounts
34. `034_trial_reels.sql` - Columnas posts.trial_graduation y post_performance.reels_skip_rate para Trial Reels (AD-10)
35. `035_account_growth.sql` - Columnas follows, unfollows y profile_links_taps en instagram_account_snapshots (AD-9)
36. `036_posts_bucket_limits.sql` - Bucket `posts`: límite 300 MB y vídeos MP4/MOV (Reels y Stories)
37. `037_account_timezones.sql` - Opciones de zona horaria por cuenta (primary, secondary, detected) (AD-1)
38. `038_persistent_thumbnails.sql` - Bucket público `thumbnails`, columna posts.thumbnail_url_base y trigger que la anula al cambiar la imagen
39. `039_thumbnail_ignore_url_signature.sql` - El trigger de miniaturas ignora la query (firma) de media_url: el sync de Instagram ya no las invalida

## Cómo Ejecutar

### Opción 1: Supabase Dashboard (Recomendado)

1. Ve a: https://supabase.com/dashboard
2. Selecciona tu proyecto
3. SQL Editor → New Query
4. Copia el contenido de la migración
5. Ejecuta (Run)

### Opción 2: Script Automatizado

```bash
cd backend
python scripts/apply_migrations.py
```

## Estado Actual

- ✅ Todas las migraciones aplicadas en producción
- ✅ Schema completo funcional
- ✅ 17 tablas creadas
- ✅ RLS policies configuradas

## Próximas Migraciones

Cuando necesites crear una nueva migración:

1. Crear archivo: `00X_descripcion.sql`
2. Seguir numeración secuencial
3. Incluir verificación `DO $$ IF NOT EXISTS...`
4. Documentar en este README
5. Ejecutar en Supabase
6. Actualizar estado
