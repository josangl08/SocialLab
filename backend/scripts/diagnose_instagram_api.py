"""
Script de diagnóstico para Instagram API
Verifica permisos, scopes y disponibilidad de métricas
"""
import requests
import sys
import json
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database.supabase_client import get_supabase_client, get_supabase_admin_client, SUPABASE_URL


def diagnose_instagram_api():
    """Diagnostica problemas con Instagram API."""
    print("=" * 70)
    print("🔍 DIAGNÓSTICO DE INSTAGRAM API")
    print(f"   CONECTANDO A SUPABASE URL: {SUPABASE_URL}")
    print("=" * 70)
    print()

    # 1. Obtener access token de la BD
    print("📋 Paso 1: Obteniendo access token de la base de datos...")
    supabase = get_supabase_admin_client()

    try:
        # Obtener todas las cuentas
        result = supabase.table('instagram_accounts').select('*').execute()

        if not result.data or len(result.data) == 0:
            print("❌ No se encontró ninguna cuenta de Instagram en la base de datos")
            return

        # Buscar cuenta activa (is_active puede ser True, TRUE, true, 1, etc.)
        account = None
        for acc in result.data:
            is_active = acc.get('is_active')
            if is_active in [True, 'TRUE', 'true', 't', 1]:
                account = acc
                break

        if not account:
            print("⚠️  No hay cuentas activas, usando la primera disponible...")
            account = result.data[0]
        print(f"✅ Cuenta encontrada: @{account.get('username', 'N/A')}")
        print(f"   - Database ID: {account['id']}")
        print(f"   - Account Name: {account.get('account_name', 'N/A')}")
        print(f"   - Followers: {account.get('followers_count', 'N/A')}")

        # Intentar diferentes nombres de columnas para Instagram User ID
        ig_user_id = None
        for possible_name in ['instagram_business_account_id', 'instagram_user_id', 'instagram_id', 'ig_user_id']:
            if possible_name in account and account[possible_name]:
                ig_user_id = account[possible_name]
                print(f"   - Instagram Business ID: {ig_user_id}")
                break

        if not ig_user_id:
            print("   ⚠️  Instagram ID no encontrado en BD")
            print(f"   Columnas disponibles: {list(account.keys())}")

        # Intentar diferentes nombres para access token
        access_token = None
        for possible_token in ['long_lived_access_token', 'access_token', 'token']:
            if possible_token in account and account[possible_token]:
                access_token = account[possible_token]
                print(f"   - Token encontrado: {possible_token}")
                break

        if not access_token:
            print("❌ No se encontró access_token en la base de datos")
            print(f"   Columnas disponibles: {list(account.keys())}")
            return

        print(f"   - Token (primeros 30 chars): {access_token[:30]}...")

        # Verificar expiración
        if 'expires_at' in account and account['expires_at']:
            print(f"   - Expira: {account['expires_at']}")

        print()

    except Exception as e:
        print(f"❌ Error obteniendo datos de BD: {e}")
        return

    # 2. Verificar información básica de la cuenta
    print("📋 Paso 2: Verificando información básica de la cuenta...")

    # Si no tenemos ig_user_id, intentar obtenerlo del token
    if not ig_user_id:
        print("   Intentando obtener Instagram ID desde el token...")
        try:
            me_url = "https://graph.facebook.com/v24.0/me/accounts"
            me_params = {'access_token': access_token}
            me_response = requests.get(me_url, params=me_params)

            if me_response.status_code == 200:
                pages = me_response.json().get('data', [])
                if pages:
                    # Intentar obtener Instagram Business Account de la página
                    page_id = pages[0]['id']
                    page_token = pages[0].get('access_token', access_token)

                    ig_url = f"https://graph.facebook.com/v24.0/{page_id}"
                    ig_params = {
                        'fields': 'instagram_business_account',
                        'access_token': page_token
                    }
                    ig_response = requests.get(ig_url, params=ig_params)

                    if ig_response.status_code == 200:
                        ig_data = ig_response.json()
                        if 'instagram_business_account' in ig_data:
                            ig_user_id = ig_data['instagram_business_account']['id']
                            print(f"   ✅ Instagram ID obtenido del token: {ig_user_id}")
        except Exception as e:
            print(f"   ⚠️  No se pudo obtener Instagram ID automáticamente: {e}")

    if not ig_user_id:
        print("❌ No se puede continuar sin Instagram User ID")
        print("   Por favor, verifica que la cuenta esté correctamente conectada")
        return

    try:
        url = f"https://graph.facebook.com/v24.0/{ig_user_id}"
        params = {
            'fields': 'id,username,name,media_count,followers_count',
            'access_token': access_token
        }
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Información básica obtenida exitosamente:")
            print(f"   - Username: {data.get('username', 'N/A')}")
            print(f"   - Name: {data.get('name', 'N/A')}")
            print(f"   - Followers: {data.get('followers_count', 'N/A')}")
            print(f"   - Media Count: {data.get('media_count', 'N/A')}")
            print()
        else:
            print(f"❌ Error obteniendo info básica: {response.status_code}")
            print(f"   Response: {response.text}")
            return

    except Exception as e:
        print(f"❌ Error en petición básica: {e}")
        return

    # 3. Probar métricas account-level UNA POR UNA
    print("📋 Paso 3: Probando métricas account-level (insights)...")
    print()

    # Lista de métricas a probar
    metrics_to_test = [
        {'name': 'total_interactions', 'period': 'day', 'extra_params': {'metric_type': 'total_value'}},
        {'name': 'reach', 'period': 'days_28'},
        {'name': 'profile_views', 'period': 'day', 'extra_params': {'metric_type': 'total_value'}},
        {'name': 'follower_count', 'period': 'day'},
        {'name': 'website_clicks', 'period': 'day', 'extra_params': {'metric_type': 'total_value'}},
    ]

    available_metrics = []
    unavailable_metrics = []

    for metric_info in metrics_to_test:
        metric = metric_info['name']
        period = metric_info['period']
        print(f"   Probando: {metric} (period={period})...")

        try:
            url = f"https://graph.facebook.com/v24.0/{ig_user_id}/insights"
            params = {
                'metric': metric,
                'period': period,
                'access_token': access_token
            }
            # Añadir parámetros extra si existen
            if 'extra_params' in metric_info:
                params.update(metric_info['extra_params'])

            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    value = data['data'][0].get('values', [{}])[0].get('value', 'N/A')
                    print(f"   ✅ {metric}: {value}")
                    available_metrics.append(metric)
                else:
                    print(f"   ⚠️  {metric}: Sin datos")
                    unavailable_metrics.append((metric, "Sin datos"))
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', response.text)
                print(f"   ❌ {metric}: {response.status_code} - {error_message}")
                unavailable_metrics.append((metric, f"{response.status_code}: {error_message}"))

        except Exception as e:
            print(f"   ❌ {metric}: Error - {e}")
            unavailable_metrics.append((metric, str(e)))

    print()

    # 4. Probar métricas lifetime (demografía y actividad)
    print("📋 Paso 4: Probando métricas lifetime (demografía y actividad)...")
    print()

    # Métrica de actividad de seguidores
    lifetime_metrics = [{'name': 'online_followers'}]

    # Métricas demográficas que requieren 'breakdown'
    demographic_breakdowns = {
        'audience_city': 'city',
        'audience_country': 'country',
        'audience_gender_age': 'gender,age'
    }

    # Probar las métricas de lifetime que no necesitan breakdown (solo online_followers por ahora)
    for metric_info in lifetime_metrics:
        metric = metric_info['name']
        print(f"   Probando: {metric}...")
        try:
            url = f"https://graph.facebook.com/v24.0/{ig_user_id}/insights"
            params = {
                'metric': metric,
                'period': 'lifetime',
                'access_token': access_token
            }
            if 'extra_params' in metric_info:
                params.update(metric_info['extra_params'])

            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    value = data['data'][0].get('values', [{}])[0].get('value', {})
                    sample = str(value)[:100] + '...' if len(str(value)) > 100 else str(value)
                    print(f"   ✅ {metric}: {sample}")
                    available_metrics.append(metric)
                else:
                    print(f"   ⚠️  {metric}: Sin datos")
                    unavailable_metrics.append((metric, "Sin datos"))
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', response.text)
                print(f"   ❌ {metric}: {response.status_code} - {error_message}")
                unavailable_metrics.append((metric, f"{response.status_code}: {error_message}"))
        except Exception as e:
            print(f"   ❌ {metric}: Error - {e}")
            unavailable_metrics.append((metric, str(e)))

    # Probar las métricas de demografía con breakdown
    for friendly_name, breakdown in demographic_breakdowns.items():
        metric = 'follower_demographics'
        print(f"   Probando: {friendly_name} (via '{metric}' con breakdown '{breakdown}')...")
        try:
            url = f"https://graph.facebook.com/v24.0/{ig_user_id}/insights"
            params = {
                'metric': metric,
                'period': 'lifetime',
                'breakdown': breakdown,
                'metric_type': 'total_value',
                'access_token': access_token
            }

            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                if data.get('data') and len(data['data']) > 0:
                    value = data['data'][0].get('values', [{}])[0].get('value', {})
                    sample = str(value)[:100] + '...' if len(str(value)) > 100 else str(value)
                    print(f"   ✅ {friendly_name}: {sample}")
                    available_metrics.append(friendly_name)
                else:
                    print(f"   ⚠️  {friendly_name}: Sin datos")
                    unavailable_metrics.append((friendly_name, "Sin datos"))
            else:
                error_data = response.json()
                error_message = error_data.get('error', {}).get('message', response.text)
                print(f"   ❌ {friendly_name}: {response.status_code} - {error_message}")
                unavailable_metrics.append((friendly_name, f"{response.status_code}: {error_message}"))
        except Exception as e:
            print(f"   ❌ {friendly_name}: Error - {e}")
            unavailable_metrics.append((friendly_name, str(e)))

    print()

    # 5. Probar métricas media-level
    print("📋 Paso 5: Probando métricas media-level (insights de posts)...")
    print()

    try:
        # Obtener el último post
        media_url = f"https://graph.facebook.com/v24.0/{ig_user_id}/media"
        media_params = {'access_token': access_token, 'limit': 1}
        media_response = requests.get(media_url, params=media_params)

        if media_response.status_code == 200 and media_response.json().get('data'):
            media_id = media_response.json()['data'][0]['id']
            print(f"   ✅ Último post encontrado. Media ID: {media_id}")

            media_metrics_to_test = ['total_interactions', 'reach', 'saved']
            for metric in media_metrics_to_test:
                print(f"      Probando: {metric}...")
                insights_url = f"https://graph.facebook.com/v24.0/{media_id}/insights"
                insights_params = {
                    'metric': metric,
                    'access_token': access_token
                }
                insights_response = requests.get(insights_url, params=insights_params)

                if insights_response.status_code == 200:
                    data = insights_response.json()
                    if data.get('data') and len(data['data']) > 0:
                        value = data['data'][0].get('values', [{}])[0].get('value', 'N/A')
                        print(f"      ✅ {metric}: {value}")
                        available_metrics.append(f"media_{metric}")
                    else:
                        print(f"      ⚠️  {metric}: Sin datos")
                        unavailable_metrics.append((f"media_{metric}", "Sin datos"))
                else:
                    error_data = insights_response.json()
                    error_message = error_data.get('error', {}).get('message', insights_response.text)
                    print(f"      ❌ {metric}: {insights_response.status_code} - {error_message}")
                    unavailable_metrics.append((f"media_{metric}", f"{insights_response.status_code}: {error_message}"))
        else:
            print("   ❌ No se pudieron obtener posts para probar métricas media-level.")
            print(f"      Response: {media_response.text}")

    except Exception as e:
        print(f"   ❌ Error probando métricas de post: {e}")

    print()

    # 6. Resumen
    print("=" * 70)
    print("📊 RESUMEN DEL DIAGNÓSTICO")
    print("=" * 70)
    print()
    print(f"✅ Métricas disponibles: {len(available_metrics)}")
    for m in available_metrics:
        print(f"   - {m}")
    print()
    print(f"❌ Métricas NO disponibles: {len(unavailable_metrics)}")
    for m, error in unavailable_metrics:
        print(f"   - {m}: {error}")
    print()

    # 7. Diagnóstico y recomendaciones
    print("=" * 70)
    print("💡 DIAGNÓSTICO Y RECOMENDACIONES")
    print("=" * 70)
    print()

    if len(unavailable_metrics) == 0:
        print("✅ ¡Todas las métricas están disponibles! El problema debe ser del código.")
        print()
    elif len(available_metrics) == 0:
        print("❌ NINGUNA métrica está disponible. Posibles causas:")
        print()
        print("1. 🔐 Token sin permisos correctos:")
        print("   - Necesitas scopes: instagram_basic, instagram_manage_insights")
        print("   - Revisa los permisos en Facebook App Dashboard")
        print()
        print("2. 👤 Tipo de cuenta incorrecto:")
        print("   - Debe ser BUSINESS o CREATOR")
        print("   - Verifica en Instagram > Settings > Account > Switch to Professional Account")
        print()
        print("3. 🔗 Conexión Instagram-Facebook incorrecta:")
        print("   - La cuenta de Instagram debe estar conectada a una Facebook Page")
        print("   - Verifica en Facebook Page Settings > Instagram")
        print()
    else:
        print(f"⚠️  ALGUNAS métricas funcionan ({len(available_metrics)}) pero otras NO ({len(unavailable_metrics)})")
        print()
        print("Esto puede indicar:")
        print("1. Permisos parciales del token")
        print("2. Algunas métricas requieren requisitos adicionales:")
        print("   - website_clicks: Requiere link en bio")
        print("   - email_contacts: Requiere email configurado")
        print("   - Demografía: Requiere >100 seguidores en algunas versiones")
        print()
        print("Solución sugerida:")
        print("- Usa solo las métricas disponibles en tu código")
        print("- Implementa fallbacks para métricas no disponibles")
        print()

    print("🔗 Para revisar permisos:")
    print("   1. Ve a: https://developers.facebook.com/apps/")
    print(f"   2. Busca tu app y ve a: App Review > Permissions and Features")
    print("   3. Verifica que tengas aprobado: instagram_basic, instagram_manage_insights")
    print()


if __name__ == "__main__":
    diagnose_instagram_api()
