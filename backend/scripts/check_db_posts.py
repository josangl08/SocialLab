"""Script para verificar posts en la base de datos"""
import os
import sys

# Añadir el directorio padre al sys.path para poder importar el módulo database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import supabase
from datetime import datetime, timedelta

print("🔍 Verificando posts en la base de datos...\n")

# 1. Obtener cuenta de Instagram
accounts_result = supabase.table('instagram_accounts')\
    .select('id, username, account_name, followers_count, last_sync_at')\
    .eq('is_active', True)\
    .execute()

if not accounts_result.data or len(accounts_result.data) == 0:
    print("❌ No se encontró ninguna cuenta de Instagram activa")
    exit(1)

account = accounts_result.data[0]
print(f"📱 Cuenta de Instagram encontrada:")
print(f"   - ID: {account['id']}")
print(f"   - Username: {account['username']}")
print(f"   - Account Name: {account['account_name']}")
print(f"   - Followers: {account['followers_count']}")
print(f"   - Last Sync: {account['last_sync_at']}\n")

instagram_account_id = account['id']

# 2. Contar todos los posts
total_posts = supabase.table('posts')\
    .select('id', count='exact')\
    .eq('instagram_account_id', instagram_account_id)\
    .execute()

print(f"📊 Total de posts en DB: {total_posts.count}\n")

# 3. Contar posts por status
for status in ['published', 'scheduled', 'draft', 'failed']:
    count_result = supabase.table('posts')\
        .select('id', count='exact')\
        .eq('instagram_account_id', instagram_account_id)\
        .eq('status', status)\
        .execute()
    print(f"   - {status.capitalize()}: {count_result.count}")

# 4. Verificar posts de los últimos 7 días
cutoff_date = datetime.utcnow() - timedelta(days=7)
print(f"\n📅 Posts de los últimos 7 días (desde {cutoff_date.date()}):")

posts_7d = supabase.table('posts')\
    .select('id, publication_date', count='exact')\
    .eq('instagram_account_id', instagram_account_id)\
    .eq('status', 'published')\
    .gte('publication_date', cutoff_date.isoformat())\
    .execute()

print(f"   - Count: {posts_7d.count}")

# 5. Verificar posts con performance data
posts_with_perf = supabase.table('posts')\
    .select(
        'id, content, publication_date, '
        'post_performance(likes, comments, reach, impressions)',
        count='exact'
    )\
    .eq('instagram_account_id', instagram_account_id)\
    .eq('status', 'published')\
    .limit(5)\
    .execute()

print(f"\n📈 Muestra de posts (primeros 5):")
if posts_with_perf.data:
    for post in posts_with_perf.data:
        perf = post.get('post_performance') or {}
        pub_date = post.get('publication_date', 'N/A')[:10] if post.get('publication_date') else 'N/A'
        print(f"\n   Post ID: {post['id']}")
        print(f"   - Date: {pub_date}")
        print(f"   - Content: {post.get('content', '')[:50]}...")
        print(f"   - Likes: {perf.get('likes', 0)}, Comments: {perf.get('comments', 0)}")
else:
    print("   ⚠️  No hay posts con datos de performance")

# 6. Verificar rango de fechas de publicación
date_range = supabase.table('posts')\
    .select('publication_date')\
    .eq('instagram_account_id', instagram_account_id)\
    .eq('status', 'published')\
    .order('publication_date', desc=False)\
    .limit(1)\
    .execute()

if date_range.data and len(date_range.data) > 0:
    oldest = date_range.data[0]['publication_date'][:10] if date_range.data[0].get('publication_date') else 'N/A'
    print(f"\n%s" % "📆 Rango de fechas:")
    print(f"   - Post más antiguo: {oldest}")

    newest_result = supabase.table('posts')\
        .select('publication_date')\
        .eq('instagram_account_id', instagram_account_id)\
        .eq('status', 'published')\
        .order('publication_date', desc=True)\
        .limit(1)\
        .execute()

    if newest_result.data and len(newest_result.data) > 0:
        newest = newest_result.data[0]['publication_date'][:10] if newest_result.data[0].get('publication_date') else 'N/A'
        print(f"   - Post más reciente: {newest}")
