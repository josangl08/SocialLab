"""Script para verificar posts en la base de datos"""
import os
import sys

# Añadir el directorio padre al sys.path para poder importar el módulo database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import supabase
from datetime import timedelta
from utils.timezones import utc_now_naive

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
cutoff_date = utc_now_naive() - timedelta(days=7)
print(f"\n📅 Posts de los últimos 7 días (desde {cutoff_date.date()}):")

posts_7d = supabase.table('posts')\
    .select('id, publication_date', count='exact')\
    .eq('instagram_account_id', instagram_account_id)\
    .eq('status', 'published')\
    .gte('publication_date', cutoff_date.isoformat())\
    .execute()

print(f"   - Count: {posts_7d.count}")

# 5. Diagnóstico de los 5 posts más recientes (los que muestran "Sin datos aún")
recent_posts_check = supabase.table('posts')\
    .select(
        'id, content, publication_date, instagram_post_id, '
        'post_performance(likes, comments, reach, impressions)'
    )\
    .eq('instagram_account_id', instagram_account_id)\
    .eq('status', 'published')\
    .order('publication_date', desc=True)\
    .limit(5)\
    .execute()

print(f"\n📈 5 posts más recientes (diagnóstico):")
if recent_posts_check.data:
    for post in recent_posts_check.data:
        raw_perf = post.get('post_performance')
        perf = raw_perf if isinstance(raw_perf, dict) else {}
        pub_date = post.get('publication_date', 'N/A')[:10] if post.get('publication_date') else 'N/A'
        ig_id = post.get('instagram_post_id') or '❌ NULL'
        has_perf = '✅' if raw_perf else '❌ Sin datos'
        print(f"\n   Post DB ID: {post['id']}")
        print(f"   - Fecha:          {pub_date}")
        print(f"   - instagram_post_id: {ig_id}")
        print(f"   - post_performance:  {has_perf}")
        if raw_perf:
            print(f"   - Likes: {perf.get('likes', 0)}, Comments: {perf.get('comments', 0)}")
        print(f"   - Contenido: {post.get('content', '')[:60]}...")
else:
    print("   ⚠️  No hay posts publicados")

# 6. Posts con instagram_post_id = NULL (publicados via stub, no en Instagram real)
null_id_posts = supabase.table('posts')\
    .select('id, publication_date, content')\
    .eq('instagram_account_id', instagram_account_id)\
    .eq('status', 'published')\
    .is_('instagram_post_id', 'null')\
    .execute()

print(f"\n⚠️  Posts con instagram_post_id=NULL (no están en Instagram real): {len(null_id_posts.data or [])}")
for p in (null_id_posts.data or [])[:3]:
    pub_date = (p.get('publication_date') or 'N/A')[:10]
    print(f"   - DB ID {p['id']} | {pub_date} | {p.get('content', '')[:50]}...")

print(f"\n✅ Diagnóstico completado.")
