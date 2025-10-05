# Migraciones de Base de Datos

## Orden de Ejecución

Las migraciones deben ejecutarse en orden cronológico:

1. `001_add_instagram_post_id.sql` - Columna para IDs de Instagram
2. `002_ensure_instagram_columns.sql` - Columnas adicionales para posts
3. `003_create_instagram_accounts_table.sql` - Tabla de cuentas Instagram
4. `004_add_media_product_type.sql` - Tipo de contenido (FEED, REELS, STORY)
5. `005_add_scheduled_publish_time.sql` - Programación de publicaciones
6. `006_add_missing_ids_and_schema.sql` - **Schema completo** (templates, ai_strategy, etc.)

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
