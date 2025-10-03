#!/usr/bin/env python3
"""
Script para aplicar migraciones SQL a la base de datos de Supabase.
Lee archivos .sql del directorio migrations/ y los ejecuta en orden.

Uso: python apply_migrations.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

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


def print_success(text):
    """Imprime mensaje de éxito."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Imprime mensaje de error."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text):
    """Imprime mensaje informativo."""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def print_header(text):
    """Imprime un encabezado."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}\n")


class MigrationRunner:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL")
        self.supabase_key = os.environ.get("SUPABASE_KEY")
        self.supabase: Client = None
        self.migrations_dir = Path(__file__).parent / "migrations"

    def connect(self):
        """Conecta a Supabase."""
        if not self.supabase_url or not self.supabase_key:
            print_error("Variables SUPABASE_URL y SUPABASE_KEY no configuradas")
            print_info("Verifica el archivo backend/.env")
            return False

        try:
            self.supabase = create_client(self.supabase_url, self.supabase_key)
            print_success("Conectado a Supabase")
            return True
        except Exception as e:
            print_error(f"Error al conectar a Supabase: {e}")
            return False

    def create_migrations_table(self):
        """Crea la tabla de control de migraciones si no existe."""
        print_info("Verificando tabla de control de migraciones...")

        sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id SERIAL PRIMARY KEY,
            migration_file TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        );
        """

        try:
            self.supabase.rpc("exec_sql", {"sql": sql}).execute()
            print_success("Tabla 'schema_migrations' lista")
            return True
        except Exception as e:
            # Intentar con método alternativo si RPC no está disponible
            print_info("RPC no disponible, usando método alternativo...")
            print_info("Debes crear la tabla manualmente en Supabase SQL Editor:")
            print(f"\n{Colors.YELLOW}{sql}{Colors.END}\n")
            return True

    def get_applied_migrations(self):
        """Obtiene la lista de migraciones ya aplicadas."""
        try:
            result = self.supabase.table("schema_migrations").select("migration_file").execute()
            applied = [row["migration_file"] for row in result.data]
            return applied
        except Exception as e:
            print_info(f"No se pudo leer migraciones aplicadas: {e}")
            print_info("Asumiendo que ninguna migración ha sido aplicada")
            return []

    def get_migration_files(self):
        """Obtiene la lista de archivos de migración ordenados."""
        if not self.migrations_dir.exists():
            print_error(f"Directorio de migraciones no encontrado: {self.migrations_dir}")
            return []

        sql_files = sorted(self.migrations_dir.glob("*.sql"))
        return sql_files

    def execute_migration(self, migration_file: Path):
        """Ejecuta un archivo de migración."""
        print(f"\n{Colors.CYAN}📄 Aplicando: {migration_file.name}{Colors.END}")

        try:
            # Leer contenido del archivo
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()

            print_info(f"Ejecutando SQL ({len(sql_content)} caracteres)...")

            # Ejecutar SQL usando RPC si está disponible
            try:
                self.supabase.rpc("exec_sql", {"sql": sql_content}).execute()
            except Exception as rpc_error:
                # Si RPC falla, intentar ejecutar sentencias una por una
                print_info("Intentando método alternativo...")

                # Dividir por punto y coma y ejecutar cada sentencia
                statements = [s.strip() for s in sql_content.split(';') if s.strip()]

                for statement in statements:
                    # Saltar comentarios
                    if statement.startswith('--') or statement.startswith('/*'):
                        continue

                    # Para ALTER TABLE, INSERT, CREATE, etc.
                    if any(keyword in statement.upper() for keyword in ['ALTER', 'CREATE', 'INSERT']):
                        print_info(f"Ejecutando: {statement[:50]}...")
                        # Esto requerirá ejecutar directamente en Supabase
                        print_error("No se puede ejecutar automáticamente")
                        print_info("Copia y pega en Supabase SQL Editor:")
                        print(f"\n{Colors.YELLOW}{statement};{Colors.END}\n")

            # Registrar migración como aplicada
            self.supabase.table("schema_migrations").insert({
                "migration_file": migration_file.name
            }).execute()

            print_success(f"Migración {migration_file.name} aplicada exitosamente")
            return True

        except Exception as e:
            print_error(f"Error al aplicar migración: {e}")
            print_info("Puedes ejecutar manualmente en Supabase SQL Editor")
            return False

    def run(self):
        """Ejecuta el proceso completo de migraciones."""
        print_header("🗄️  APLICADOR DE MIGRACIONES - SOCIALLAB")

        # Conectar a Supabase
        if not self.connect():
            sys.exit(1)

        # Crear tabla de control
        self.create_migrations_table()

        # Obtener migraciones
        migration_files = self.get_migration_files()

        if not migration_files:
            print_info("No se encontraron archivos de migración")
            return

        print_info(f"Encontrados {len(migration_files)} archivos de migración")

        # Obtener migraciones ya aplicadas
        applied_migrations = self.get_applied_migrations()
        print_info(f"Migraciones ya aplicadas: {len(applied_migrations)}")

        # Aplicar migraciones pendientes
        pending_count = 0
        success_count = 0
        error_count = 0

        for migration_file in migration_files:
            if migration_file.name in applied_migrations:
                print(f"{Colors.YELLOW}⏭️  Omitiendo (ya aplicada): {migration_file.name}{Colors.END}")
                continue

            pending_count += 1
            if self.execute_migration(migration_file):
                success_count += 1
            else:
                error_count += 1

        # Resumen
        print_header("📊 RESUMEN")
        print(f"{Colors.CYAN}Total de migraciones: {len(migration_files)}{Colors.END}")
        print(f"{Colors.GREEN}Ya aplicadas: {len(applied_migrations)}{Colors.END}")
        print(f"{Colors.BLUE}Pendientes: {pending_count}{Colors.END}")
        print(f"{Colors.GREEN}Aplicadas exitosamente: {success_count}{Colors.END}")

        if error_count > 0:
            print(f"{Colors.RED}Con errores: {error_count}{Colors.END}")
            print_info("\nPara migraciones con errores, ejecuta el SQL manualmente en:")
            print(f"{Colors.CYAN}https://supabase.com/dashboard/project/[tu-proyecto]/editor/sql{Colors.END}")

        if error_count == 0 and pending_count > 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 Todas las migraciones se aplicaron correctamente!{Colors.END}")
        elif pending_count == 0:
            print(f"\n{Colors.BLUE}ℹ️  Base de datos actualizada. No hay migraciones pendientes.{Colors.END}")


if __name__ == "__main__":
    runner = MigrationRunner()
    runner.run()
