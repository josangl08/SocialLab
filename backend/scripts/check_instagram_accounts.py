"""Script para verificar cuentas de Instagram en DB"""
import os
import sys

# Añadir el directorio padre al sys.path para poder importar el módulo database
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import supabase

print("🔍 Verificando cuentas de Instagram en la base de datos...\n")

# Obtener TODAS las cuentas (activas e inactivas)
all_accounts = supabase.table('instagram_accounts')\
    .select('*')\
    .execute()

if not all_accounts.data or len(all_accounts.data) == 0:
    print("❌ No se encontró NINGUNA cuenta de Instagram en la base de datos")
    exit(1)

print(f"📱 Se encontraron {len(all_accounts.data)} cuenta(s) de Instagram:\n")

for i, account in enumerate(all_accounts.data, 1):
    print(f"Cuenta #{i}:")
    print(f"  - ID: {account.get('id')}")
    print(f"  - User ID: {account.get('user_id')}")
    print(f"  - Username: {account.get('username', 'N/A')}")
    print(f"  - Account Name: {account.get('account_name', 'N/A')}")
    print(f"  - Instagram Business Account ID: {account.get('instagram_business_account_id', 'N/A')}")
    print(f"  - Followers: {account.get('followers_count', 0)}")
    print(f"  - Is Active: {account.get('is_active')} 👈")
    print(f"  - Last Sync: {account.get('last_sync_at', 'Nunca')}")
    print(f"  - Expires At: {account.get('expires_at', 'N/A')}")
    print()

# Si hay cuentas inactivas, mostrar advertencia
inactive_count = sum(1 for acc in all_accounts.data if not acc.get('is_active'))
if inactive_count > 0:
    print(f"⚠️  PROBLEMA ENCONTRADO: Hay {inactive_count} cuenta(s) marcadas como is_active=False")
    print(f"   Esto impide que el dashboard muestre datos.\n")
    print(f"   Solución: Activar la cuenta con:")
    print(f"   UPDATE instagram_accounts SET is_active = TRUE WHERE id = <account_id>\n")
