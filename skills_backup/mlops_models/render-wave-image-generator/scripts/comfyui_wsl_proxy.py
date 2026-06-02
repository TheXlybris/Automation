#!/usr/bin/env python3
"""
THE RENDER WAVE — ComfyUI WSL Proxy

Escuta em 192.168.144.1:8188 (interface virtual WSL) e redireciona
todo o tráfego para 127.0.0.1:8188 (ComfyUI no Windows localhost).

Isto permite que scripts no WSL liguem ao ComfyUI SEM expor o ComfyUI
para a rede externa (0.0.0.0).

Uso:
    python comfyui_wsl_proxy.py

Para correr em background no Windows:
    pythonw comfyui_wsl_proxy.py

Para parar: Ctrl+C ou fechar a janela.
"""

import socket
import threading
import sys

WSL_HOST = "192.168.144.1"
WSL_PORT = 8188
COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
BUFFER_SIZE = 65536


def handle_client(client_conn, client_addr):
    try:
        backend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend.connect((COMFY_HOST, COMFY_PORT))

        def forward_backend():
            try:
                while True:
                    data = backend.recv(BUFFER_SIZE)
                    if not data:
                        break
                    client_conn.sendall(data)
            except Exception:
                pass
            finally:
                backend.close()
                client_conn.close()

        t = threading.Thread(target=forward_backend, daemon=True)
        t.start()

        while True:
            data = client_conn.recv(BUFFER_SIZE)
            if not data:
                break
            backend.sendall(data)

    except Exception as e:
        print(f"[ERRO] Ligação de {client_addr}: {e}")
    finally:
        try: client_conn.close()
        except: pass
        try: backend.close()
        except: pass


def main():
    listen_host = WSL_HOST
    try:
        import subprocess
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like '*WSL*'}).IPAddress"],
            capture_output=True, text=True, timeout=5
        )
        ip = result.stdout.strip()
        if ip:
            listen_host = ip
            print(f"[INFO] Interface WSL detetada: {listen_host}")
    except Exception:
        print(f"[INFO] A usar IP fixo: {listen_host}")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((listen_host, WSL_PORT))
    except OSError as e:
        print(f"[ERRO] Nao consegui ligar a {listen_host}:{WSL_PORT}")
        print(f"        Causa provavel: ja existe outro processo nesta porta.")
        sys.exit(1)

    server.listen(100)
    print("=" * 55)
    print("  THE RENDER WAVE — ComfyUI WSL Proxy")
    print("=" * 55)
    print(f"  Escuta em:    http://{listen_host}:{WSL_PORT}")
    print(f"  Redireciona para: http://{COMFY_HOST}:{COMFY_PORT}")
    print("=" * 55)
    print("  Pronto para receber ligações do WSL.")
    print("  Para parar: Ctrl+C")
    print("=" * 55)

    try:
        while True:
            client_conn, client_addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_conn, client_addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[INFO] A encerrar proxy...")
    finally:
        server.close()
        print("[INFO] Proxy encerrado.")


if __name__ == "__main__":
    main()
