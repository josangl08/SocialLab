#!/usr/bin/env python3
"""
Script para iniciar simultáneamente el backend (FastAPI) y frontend (React/Vite)
de SocialLab.

Uso: python start.py
"""
import subprocess
import os
import sys
import signal


def signal_handler(sig, frame):
    """Manejar Ctrl+C para detener ambos procesos."""
    print("\n\n🛑 Deteniendo aplicación...")
    sys.exit(0)


def main():
    print("🚀 Iniciando SocialLab...\n")

    # Rutas
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

    # Activar entorno virtual de Python
    venv_python = os.path.join(backend_dir, "venv", "bin", "python")

    if not os.path.exists(venv_python):
        print("⚠️  No se encontró el entorno virtual del backend.")
        print("   Ejecuta: cd backend && python -m venv venv")
        sys.exit(1)

    # Registrar handler para Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Iniciar backend
        print("📦 Iniciando Backend (FastAPI) en puerto 8000...")
        backend_process = subprocess.Popen(
            [venv_python, "-m", "uvicorn", "main:app", "--reload", "--port", "8000", "--log-level", "info"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1  # Line buffered para ver logs inmediatamente
        )

        # Iniciar frontend
        print("⚛️  Iniciando Frontend (React/Vite) en puerto 5173...\n")
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1  # Line buffered para ver logs inmediatamente
        )

        print("✅ Aplicación iniciada correctamente!\n")
        print("   🌐 Frontend: http://localhost:5173")
        print("   🔧 Backend:  http://localhost:8000")
        print("   📚 API Docs: http://localhost:8000/docs\n")
        print("   Presiona Ctrl+C para detener...\n")
        print("-" * 60)

        # Mostrar logs de ambos procesos
        while True:
            backend_output = backend_process.stdout.readline()
            if backend_output:
                print(f"[BACKEND] {backend_output.strip()}")

            frontend_output = frontend_process.stdout.readline()
            if frontend_output:
                print(f"[FRONTEND] {frontend_output.strip()}")

            # Verificar si algún proceso terminó
            if backend_process.poll() is not None:
                print("❌ Backend se detuvo inesperadamente")
                frontend_process.terminate()
                break

            if frontend_process.poll() is not None:
                print("❌ Frontend se detuvo inesperadamente")
                backend_process.terminate()
                break

    except KeyboardInterrupt:
        print("\n\n🛑 Deteniendo aplicación...")
    finally:
        # Asegurar que ambos procesos se detengan
        try:
            backend_process.terminate()
            frontend_process.terminate()
        except:
            pass
        print("👋 Aplicación detenida correctamente")


if __name__ == "__main__":
    main()
