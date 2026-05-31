#!/usr/bin/env python3
"""
Script para iniciar simultáneamente el backend (FastAPI) y frontend (React/Vite)
de SocialLab con logging en tiempo real.

Uso: python start.py
"""
import subprocess
import os
import sys
import signal
import threading
import queue
import time


# ANSI color codes para terminal
class Colors:
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


backend_process = None
frontend_process = None
ngrok_process = None
stop_event = threading.Event()


def signal_handler(sig, frame):
    """Manejar Ctrl+C para detener ambos procesos."""
    print(f"\n\n{Colors.RED}🛑 Deteniendo aplicación...{Colors.RESET}")
    stop_event.set()
    cleanup()
    sys.exit(0)


def cleanup():
    """Terminar procesos de backend, frontend y ngrok."""
    global backend_process, frontend_process, ngrok_process

    for proc in [backend_process, frontend_process, ngrok_process]:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


def stream_output(process, prefix, color, output_queue):
    """
    Lee output de un proceso y lo añade a la cola con prefijo de color.
    Se ejecuta en un thread separado para no bloquear.
    """
    try:
        for line in iter(process.stdout.readline, ''):
            if stop_event.is_set():
                break
            if line:
                output_queue.put((prefix, color, line.rstrip()))

        # Cuando el proceso termina
        return_code = process.poll()
        if return_code is not None and return_code != 0:
            output_queue.put((
                prefix,
                Colors.RED,
                f"Proceso terminó con código {return_code}"
            ))
    except Exception as e:
        output_queue.put((prefix, Colors.RED, f"Error leyendo output: {e}"))


def print_output(output_queue):
    """
    Imprime output de la cola en tiempo real.
    Se ejecuta en el thread principal.
    """
    while not stop_event.is_set():
        try:
            prefix, color, line = output_queue.get(timeout=0.1)
            print(f"{color}{prefix}{Colors.RESET} {line}")
            output_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"{Colors.RED}Error imprimiendo: {e}{Colors.RESET}")


def load_env(backend_dir: str) -> dict:
    """Lee variables de .env del backend."""
    env_path = os.path.join(backend_dir, ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    value = value.split(" #")[0].split("\t#")[0].strip()
                    env[key.strip()] = value
    return env


def main():
    global backend_process, frontend_process, ngrok_process

    print(f"{Colors.BOLD}{Colors.GREEN}🚀 Iniciando SocialLab...{Colors.RESET}\n")

    # Rutas
    backend_dir = os.path.join(os.path.dirname(__file__), "backend")
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

    # Activar entorno virtual de Python
    venv_python = os.path.join(backend_dir, "venv", "bin", "python")

    if not os.path.exists(venv_python):
        print(f"{Colors.YELLOW}⚠️  No se encontró el entorno virtual del backend.{Colors.RESET}")
        print("   Ejecuta: cd backend && python -m venv venv")
        sys.exit(1)

    # Registrar handler para Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Cola para output de todos los procesos
    output_queue = queue.Queue()

    # Leer TELEGRAM_WEBHOOK_URL del .env
    env_vars = load_env(backend_dir)
    webhook_url = env_vars.get("TELEGRAM_WEBHOOK_URL", "")
    ngrok_domain = webhook_url.replace("https://", "").replace("http://", "").strip("/ ") if webhook_url else ""

    try:
        # Iniciar ngrok si hay dominio configurado
        if ngrok_domain:
            print(f"{Colors.YELLOW}🔗 Iniciando ngrok en {webhook_url}...{Colors.RESET}")
            ngrok_process = subprocess.Popen(
                ["ngrok", "http", f"--url={ngrok_domain}", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            time.sleep(2)  # Esperar a que el túnel esté listo
        else:
            print(f"{Colors.YELLOW}⚠️  TELEGRAM_WEBHOOK_URL no configurado — ngrok omitido{Colors.RESET}")

        # Iniciar backend
        print(f"{Colors.BLUE}📦 Iniciando Backend (FastAPI) en puerto 8000...{Colors.RESET}")
        backend_process = subprocess.Popen(
            [venv_python, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
            cwd=backend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Iniciar frontend
        print(f"{Colors.CYAN}⚛️  Iniciando Frontend (React/Vite) en puerto 5173...{Colors.RESET}\n")
        frontend_process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        time.sleep(1)

        print(f"{Colors.GREEN}✅ Aplicación iniciada correctamente!{Colors.RESET}\n")
        print(f"   {Colors.CYAN}🌐 Frontend:{Colors.RESET} http://localhost:5173")
        print(f"   {Colors.BLUE}🔧 Backend: {Colors.RESET} http://localhost:8000")
        print(f"   {Colors.YELLOW}📚 API Docs:{Colors.RESET} http://localhost:8000/docs")
        if ngrok_domain:
            print(f"   {Colors.YELLOW}🔗 Ngrok:   {Colors.RESET} {webhook_url}")
        print(f"\n   {Colors.BOLD}Presiona Ctrl+C para detener...{Colors.RESET}\n")
        print("-" * 70)

        # Crear threads para leer output de cada proceso
        backend_thread = threading.Thread(
            target=stream_output,
            args=(backend_process, "[BACKEND] ", Colors.BLUE, output_queue),
            daemon=True
        )
        frontend_thread = threading.Thread(
            target=stream_output,
            args=(frontend_process, "[FRONTEND]", Colors.CYAN, output_queue),
            daemon=True
        )
        threads = [backend_thread, frontend_thread]

        if ngrok_process:
            ngrok_thread = threading.Thread(
                target=stream_output,
                args=(ngrok_process, "[NGROK]   ", Colors.YELLOW, output_queue),
                daemon=True
            )
            threads.append(ngrok_thread)

        for t in threads:
            t.start()

        # Loop principal: imprimir output y monitorear procesos
        while not stop_event.is_set():
            try:
                prefix, color, line = output_queue.get(timeout=0.1)
                print(f"{color}{prefix}{Colors.RESET} {line}")
                output_queue.task_done()
            except queue.Empty:
                pass

            if backend_process.poll() is not None and not stop_event.is_set():
                print(f"\n{Colors.RED}❌ Backend se detuvo inesperadamente{Colors.RESET}")
                stop_event.set()
                cleanup()
                break

            if frontend_process.poll() is not None and not stop_event.is_set():
                print(f"\n{Colors.RED}❌ Frontend se detuvo inesperadamente{Colors.RESET}")
                stop_event.set()
                cleanup()
                break

    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}🛑 Deteniendo aplicación...{Colors.RESET}")
        stop_event.set()
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error inesperado: {e}{Colors.RESET}")
        stop_event.set()
    finally:
        cleanup()
        print(f"{Colors.GREEN}👋 Aplicación detenida correctamente{Colors.RESET}")


if __name__ == "__main__":
    main()
