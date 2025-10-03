#!/usr/bin/env python3
"""
Script de diagnóstico para SocialLab - Instagram Integration
Verifica configuración de Supabase, Meta API y tokens de Instagram.

Uso: python diagnostic.py
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
import requests

# Cargar variables de entorno
load_dotenv()

# Colores para terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(text):
    """Imprime un encabezado destacado."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}\n")


def print_success(text):
    """Imprime mensaje de éxito."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Imprime mensaje de error."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text):
    """Imprime mensaje de advertencia."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text):
    """Imprime mensaje informativo."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def print_solution(text):
    """Imprime una solución sugerida."""
    print(f"{Colors.YELLOW}💡 SOLUCIÓN:{Colors.END}")
    for line in text.split('\n'):
        print(f"   {line}")


class Diagnostic:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        self.instagram_app_id = os.environ.get("INSTAGRAM_APP_ID")
        self.instagram_app_secret = os.environ.get("INSTAGRAM_APP_SECRET")
        self.supabase: Client = None
        self.success_count = 0
        self.error_count = 0
        self.warning_count = 0

    def check_env_variables(self):
        """Verifica que las variables de entorno estén configuradas."""
        print_header("🔐 VERIFICANDO VARIABLES DE ENTORNO")

        vars_to_check = {
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_KEY": self.supabase_key,
            "INSTAGRAM_APP_ID": self.instagram_app_id,
            "INSTAGRAM_APP_SECRET": self.instagram_app_secret,
        }

        all_ok = True
        for var_name, var_value in vars_to_check.items():
            if var_value:
                print_success(f"{var_name} configurado")
                self.success_count += 1
            else:
                print_error(f"{var_name} NO configurado")
                self.error_count += 1
                all_ok = False

        if not all_ok:
            print_solution(
                "Verifica que el archivo backend/.env exista y contenga:\n"
                "SUPABASE_URL=tu_url\n"
                "SUPABASE_KEY=tu_key\n"
                "INSTAGRAM_APP_ID=tu_app_id\n"
                "INSTAGRAM_APP_SECRET=tu_secret"
            )
            return False
        return True

    def connect_supabase(self):
        """Conecta a Supabase."""
        print_header("🗄️  VERIFICANDO CONEXIÓN A SUPABASE")

        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            print_success("Conexión a Supabase exitosa")
            self.success_count += 1
            return True
        except Exception as e:
            print_error(f"Error al conectar a Supabase: {e}")
            self.error_count += 1
            return False

    def check_tables(self):
        """Verifica que las tablas necesarias existan."""
        print_header("📊 VERIFICANDO TABLAS DE BASE DE DATOS")

        tables_to_check = ["posts", "instagram_accounts"]

        for table_name in tables_to_check:
            try:
                result = self.supabase.table(table_name).select("*").limit(1).execute()
                print_success(f"Tabla '{table_name}' existe")
                self.success_count += 1
            except Exception as e:
                print_error(f"Tabla '{table_name}' NO existe o no es accesible")
                print_info(f"Error: {e}")
                self.error_count += 1

                if table_name == "instagram_accounts":
                    print_solution(
                        "Ejecuta la migración para crear la tabla:\n"
                        "python backend/apply_migrations.py"
                    )

    def check_posts_columns(self):
        """Verifica que la tabla posts tenga las columnas necesarias."""
        print_header("🔍 VERIFICANDO COLUMNAS DE TABLA 'posts'")

        required_columns = [
            "instagram_post_id",
            "publication_date"
        ]

        try:
            # Obtener un registro para inspeccionar columnas
            result = self.supabase.table("posts").select("*").limit(1).execute()

            if result.data and len(result.data) > 0:
                existing_columns = result.data[0].keys()

                for col in required_columns:
                    if col in existing_columns:
                        print_success(f"Columna '{col}' existe")
                        self.success_count += 1
                    else:
                        print_error(f"Columna '{col}' NO existe")
                        self.error_count += 1
            else:
                print_warning("Tabla 'posts' está vacía, no se pueden verificar columnas")
                print_info("Crea un post de prueba o ejecuta migraciones")
                self.warning_count += 1

        except Exception as e:
            print_error(f"Error al verificar columnas: {e}")
            self.error_count += 1
            print_solution(
                "Ejecuta las migraciones para agregar columnas faltantes:\n"
                "python backend/apply_migrations.py"
            )

    def check_users(self):
        """Lista usuarios registrados y verifica sus tokens de Instagram."""
        print_header("👤 VERIFICANDO USUARIOS Y TOKENS DE INSTAGRAM")

        try:
            # Intentar obtener usuarios de la tabla de autenticación
            # Nota: Supabase auth requiere permisos especiales
            posts_result = self.supabase.table("posts").select("user_id").execute()

            if not posts_result.data:
                print_warning("No hay posts en la base de datos")
                print_info("Registra un usuario y crea posts para continuar")
                self.warning_count += 1
                return

            # Obtener user_ids únicos
            user_ids = list(set([post["user_id"] for post in posts_result.data]))
            print_info(f"Usuarios encontrados: {len(user_ids)}")

            for user_id in user_ids:
                print(f"\n{Colors.BOLD}Usuario ID: {user_id}{Colors.END}")
                self.check_user_instagram_token(user_id)

        except Exception as e:
            print_error(f"Error al obtener usuarios: {e}")
            self.error_count += 1

    def check_user_instagram_token(self, user_id):
        """Verifica el token de Instagram de un usuario específico."""
        try:
            result = self.supabase.table("instagram_accounts").select("*").eq("user_id", user_id).execute()

            if not result.data or len(result.data) == 0:
                print_error("No tiene token de Instagram guardado")
                self.error_count += 1
                print_solution(
                    "El usuario debe conectar su cuenta de Instagram:\n"
                    "1. Iniciar sesión en SocialLab\n"
                    "2. Ir al Dashboard\n"
                    "3. Hacer clic en 'Conectar Instagram'"
                )
                return

            account_data = result.data[0]
            token = account_data.get("long_lived_access_token")
            expires_at = account_data.get("expires_at")
            ig_business_id = account_data.get("instagram_business_account_id")

            print_success("Token de Instagram encontrado")
            self.success_count += 1

            # Verificar expiración
            if expires_at:
                expires_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                days_remaining = (expires_date - datetime.now(expires_date.tzinfo)).days

                if days_remaining > 0:
                    print_success(f"Token válido hasta: {expires_at} ({days_remaining} días restantes)")
                    self.success_count += 1
                else:
                    print_error(f"Token EXPIRADO desde: {expires_at}")
                    self.error_count += 1
                    print_solution(
                        "El token ha expirado. Vuelve a conectar Instagram:\n"
                        "Dashboard → Conectar Instagram"
                    )
                    return

            # Verificar token con Meta API
            print_info("Verificando token con Meta Graph API...")
            self.verify_token_with_meta(token, ig_business_id)

        except Exception as e:
            print_error(f"Error al verificar token: {e}")
            self.error_count += 1

    def verify_token_with_meta(self, token, ig_business_id):
        """Verifica el token directamente con Meta Graph API."""
        print(f"\n  {Colors.CYAN}→ Probando token con Meta API...{Colors.END}")

        try:
            # Probar token obteniendo info del usuario
            debug_url = f"https://graph.facebook.com/v19.0/debug_token?input_token={token}&access_token={token}"
            debug_response = requests.get(debug_url)

            if debug_response.status_code == 200:
                debug_data = debug_response.json()
                if debug_data.get("data", {}).get("is_valid"):
                    print_success("  Token es válido según Meta")
                    self.success_count += 1
                else:
                    print_error("  Token es inválido según Meta")
                    print_info(f"  Respuesta: {debug_data}")
                    self.error_count += 1
                    return
            else:
                print_warning(f"  No se pudo validar token (código {debug_response.status_code})")
                self.warning_count += 1

            # Obtener páginas de Facebook
            print(f"\n  {Colors.CYAN}→ Obteniendo páginas de Facebook...{Colors.END}")
            pages_url = f"https://graph.facebook.com/v19.0/me/accounts?access_token={token}"
            pages_response = requests.get(pages_url)

            if pages_response.status_code != 200:
                print_error(f"  Error al obtener páginas: {pages_response.status_code}")
                print_info(f"  Respuesta: {pages_response.text}")
                self.error_count += 1
                return

            pages_data = pages_response.json()
            pages = pages_data.get("data", [])

            if not pages:
                print_error("  No se encontraron páginas de Facebook")
                self.error_count += 1
                print_solution(
                    "Debes crear una Página de Facebook y vincularla:\n"
                    "1. Crea una página en facebook.com/pages/create\n"
                    "2. Vincula tu Instagram Business a esa página"
                )
                return

            print_success(f"  Páginas encontradas: {len(pages)}")
            for page in pages:
                print(f"    • {page.get('name')} (ID: {page.get('id')})")
            self.success_count += 1

            # Obtener cuenta de Instagram Business
            print(f"\n  {Colors.CYAN}→ Obteniendo cuenta de Instagram Business...{Colors.END}")
            facebook_page_id = pages[0]["id"]
            ig_url = f"https://graph.facebook.com/v19.0/{facebook_page_id}?fields=instagram_business_account&access_token={token}"
            ig_response = requests.get(ig_url)

            if ig_response.status_code != 200:
                print_error(f"  Error al obtener cuenta IG: {ig_response.status_code}")
                print_info(f"  Respuesta: {ig_response.text}")
                self.error_count += 1
                return

            ig_data = ig_response.json()
            ig_account = ig_data.get("instagram_business_account")

            if not ig_account:
                print_error("  No se encontró instagram_business_account vinculada")
                self.error_count += 1
                print_solution(
                    "Tu cuenta de Instagram debe ser Business y estar vinculada:\n"
                    "1. Abre Instagram → Perfil → Menú (≡) → Configuración\n"
                    "2. Cuenta → Cambiar tipo de cuenta → Empresa\n"
                    "3. Vincular con la Página de Facebook\n"
                    "4. Verifica en: Configuración → Empresa → Página vinculada"
                )
                return

            ig_business_id_api = ig_account.get("id")
            print_success(f"  Instagram Business Account encontrada: {ig_business_id_api}")
            self.success_count += 1

            # Obtener media de Instagram
            print(f"\n  {Colors.CYAN}→ Obteniendo publicaciones de Instagram...{Colors.END}")
            media_url = f"https://graph.facebook.com/v19.0/{ig_business_id_api}/media?fields=id,caption,media_type,media_url,timestamp&limit=5&access_token={token}"
            media_response = requests.get(media_url)

            if media_response.status_code != 200:
                print_error(f"  Error al obtener media: {media_response.status_code}")
                print_info(f"  Respuesta: {media_response.text}")
                self.error_count += 1
                return

            media_data = media_response.json()
            posts = media_data.get("data", [])

            if not posts:
                print_warning("  No se encontraron publicaciones")
                print_info("  Si tienes posts en Instagram, verifica permisos de la app")
                self.warning_count += 1
            else:
                print_success(f"  Publicaciones encontradas: {len(posts)}")
                self.success_count += 1
                print(f"\n  {Colors.BOLD}Últimas publicaciones:{Colors.END}")
                for post in posts[:3]:
                    caption = post.get("caption", "Sin caption")[:50]
                    print(f"    • {post.get('media_type')} - {caption}...")

        except requests.exceptions.RequestException as e:
            print_error(f"  Error de red al comunicarse con Meta: {e}")
            self.error_count += 1
        except Exception as e:
            print_error(f"  Error inesperado: {e}")
            self.error_count += 1

    def print_summary(self):
        """Imprime un resumen del diagnóstico."""
        print_header("📊 RESUMEN DEL DIAGNÓSTICO")

        print(f"{Colors.GREEN}✅ Checks exitosos: {self.success_count}{Colors.END}")
        print(f"{Colors.RED}❌ Errores encontrados: {self.error_count}{Colors.END}")
        print(f"{Colors.YELLOW}⚠️  Advertencias: {self.warning_count}{Colors.END}")

        if self.error_count == 0 and self.warning_count == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ¡Todo está configurado correctamente!{Colors.END}")
        elif self.error_count > 0:
            print(f"\n{Colors.YELLOW}Revisa las soluciones sugeridas arriba ↑{Colors.END}")

    def run(self):
        """Ejecuta el diagnóstico completo."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}")
        print("🔍 DIAGNÓSTICO SOCIALLAB - INTEGRACIÓN INSTAGRAM")
        print(f"{'=' * 60}{Colors.END}\n")

        if not self.check_env_variables():
            print_error("Configuración incompleta. Corrige los errores antes de continuar.")
            sys.exit(1)

        if not self.connect_supabase():
            print_error("No se pudo conectar a Supabase. Verifica las credenciales.")
            sys.exit(1)

        self.check_tables()
        self.check_posts_columns()
        self.check_users()
        self.print_summary()

        print(f"\n{Colors.CYAN}📄 Para más información, consulta: DIAGNOSTIC_REPORT.md{Colors.END}\n")


if __name__ == "__main__":
    diagnostic = Diagnostic()
    diagnostic.run()
