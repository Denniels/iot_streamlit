#!/usr/bin/env python3
"""
Script de sincronización automática de URL de Cloudflare
Monitorea cambios en backend/secrets_tunnel.toml y actualiza frontend/app.py automáticamente

Autor: Sistema IoT - Automatización URL Cloudflare
Fecha: Octubre 2025
"""
import os
import sys
import toml
import subprocess
import re
from datetime import datetime
from pathlib import Path


def get_project_root():
    """Obtiene la ruta raíz del proyecto"""
    script_dir = Path(__file__).parent
    return script_dir.parent  # Subir un nivel desde scripts/


def read_current_url():
    """Lee la URL actual del archivo secrets_tunnel.toml"""
    project_root = get_project_root()
    secrets_file = project_root / "backend" / "secrets_tunnel.toml"
    
    try:
        with open(secrets_file, 'r') as f:
            secrets = toml.load(f)
            return secrets.get('cloudflare', {}).get('url', '')
    except Exception as e:
        print(f"Error leyendo secrets_tunnel.toml: {e}")
        return None


def get_current_frontend_url():
    """Obtiene la primera URL (actual) del frontend/app.py"""
    project_root = get_project_root()
    frontend_file = project_root / "frontend" / "app.py"
    
    try:
        with open(frontend_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Buscar la primera URL en KNOWN_CF_URLS
        pattern = r'KNOWN_CF_URLS = \[\s*"([^"]+)"'
        match = re.search(pattern, content)
        
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"Error leyendo frontend/app.py: {e}")
        return None


def update_frontend_url(new_url):
    """Actualiza la URL en frontend/app.py agregándola al inicio de KNOWN_CF_URLS"""
    project_root = get_project_root()
    frontend_file = project_root / "frontend" / "app.py"
    
    try:
        with open(frontend_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Crear timestamp para el comentario
        timestamp = datetime.now().strftime("%b %d, %Y - %H:%M")
        
        # Patrón para encontrar KNOWN_CF_URLS
        pattern = r'(KNOWN_CF_URLS = \[\s*\n)(    ".*?".*?\n)'
        
        # Nueva primera línea con timestamp
        new_first_line = f'    "{new_url}",  # URL actual {timestamp} (auto-sync)\n'
        
        def replace_func(match):
            array_start = match.group(1)
            old_first_line = match.group(2)
            # Si la URL ya está en la primera posición, no hacer nada
            if new_url in old_first_line:
                return match.group(0)
            # Agregar nueva URL al inicio y mover la anterior
            return array_start + new_first_line + old_first_line
        
        new_content = re.sub(pattern, replace_func, content)
        
        # Verificar que se hizo el cambio
        if new_content == content:
            print(f"URL ya está actualizada: {new_url}")
            return False
        
        # Escribir el archivo actualizado
        with open(frontend_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print(f"✅ Frontend actualizado con nueva URL: {new_url}")
        return True
        
    except Exception as e:
        print(f"❌ Error actualizando frontend/app.py: {e}")
        return False


def git_commit_and_push(url):
    """Hace commit y push automático con la nueva URL"""
    project_root = get_project_root()
    
    try:
        # Cambiar al directorio del proyecto
        os.chdir(project_root)
        
        # Agregar cambios
        subprocess.run(['git', 'add', 'frontend/app.py'], check=True, capture_output=True)
        
        # Commit con mensaje descriptivo
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_msg = f"feat(auto-sync): Actualizar URL Cloudflare automáticamente\n\nNueva URL: {url}\nTimestamp: {timestamp}\nAuto-generado por servicio url_sync"
        
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)
        
        # Push a GitHub
        result = subprocess.run(['git', 'push'], check=True, capture_output=True, text=True)
        
        print(f"✅ Git commit y push exitoso")
        print(f"📤 Streamlit Cloud recibirá la actualización automáticamente")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en git: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado en git: {e}")
        return False


def main():
    """Función principal del script"""
    print("🔄 Iniciando sincronización de URL Cloudflare...")
    
    # Leer URL actual del backend
    new_url = read_current_url()
    if not new_url:
        print("❌ No se pudo leer la URL de secrets_tunnel.toml")
        sys.exit(1)
    
    # Obtener URL actual del frontend
    current_frontend_url = get_current_frontend_url()
    
    # Verificar si hay cambio
    if new_url == current_frontend_url:
        print(f"ℹ️  URL sin cambios: {new_url}")
        sys.exit(0)
    
    print(f"🔄 URL cambió:")
    print(f"   Anterior: {current_frontend_url}")
    print(f"   Nueva:    {new_url}")
    
    # Actualizar frontend
    if not update_frontend_url(new_url):
        print("❌ Falló la actualización del frontend")
        sys.exit(1)
    
    # Hacer commit y push
    if not git_commit_and_push(new_url):
        print("❌ Falló el commit/push a GitHub")
        sys.exit(1)
    
    print("🎉 Sincronización completada exitosamente!")
    print(f"🌐 Nueva URL activa: {new_url}")


if __name__ == "__main__":
    main()