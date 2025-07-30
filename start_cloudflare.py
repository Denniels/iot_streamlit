#!/usr/bin/env python3
"""
Script para iniciar cloudflared, detectar la URL pública y actualizar secrets_tunnel.toml automáticamente.
"""
import subprocess
import toml
import os
import re
import sys

SECRETS_PATH = os.path.join(os.path.dirname(__file__), 'secrets_tunnel.toml')
CLOUDFLARED_BIN = '/usr/local/bin/cloudflared'
BACKEND_URL = 'http://localhost:8000'

# Regex para extraer la URL pública de cloudflared
tunnel_url_re = re.compile(r'https://[\w-]+\.trycloudflare\.com')

def update_secrets_tunnel(url):
    data = {'cloudflare': {'url': url}}
    with open(SECRETS_PATH, 'w') as f:
        toml.dump(data, f)
    print(f"[INFO] URL pública guardada en secrets_tunnel.toml: {url}")

def main():
    # Iniciar cloudflared y capturar la salida
    process = subprocess.Popen(
        [CLOUDFLARED_BIN, 'tunnel', '--url', BACKEND_URL, '--no-autoupdate'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    url_found = False
    try:
        for line in process.stdout:
            print(line, end='')  # Log en tiempo real
            if not url_found:
                match = tunnel_url_re.search(line)
                if match:
                    url = match.group(0)
                    update_secrets_tunnel(url)
                    url_found = True
        process.wait()
    except KeyboardInterrupt:
        print("[INFO] Terminando cloudflared...")
        process.terminate()
        process.wait()
        sys.exit(0)

if __name__ == "__main__":
    main()
