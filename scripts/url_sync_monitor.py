#!/usr/bin/env python3
"""
Monitor de URL de Cloudflare - Servicio systemd
Monitorea cambios en backend/secrets_tunnel.toml usando inotify
y ejecuta sync_frontend_url.py cuando detecta modificaciones

Autor: Sistema IoT - Automatización URL Cloudflare
Fecha: Octubre 2025
"""
import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class TunnelConfigHandler(FileSystemEventHandler):
    """Manejador de eventos para cambios en secrets_tunnel.toml"""
    
    def __init__(self, script_path):
        self.script_path = script_path
        self.last_sync = 0
        self.debounce_seconds = 2  # Evitar múltiples ejecuciones rápidas
        
    def on_modified(self, event):
        """Se ejecuta cuando se modifica el archivo"""
        if event.is_directory:
            return
            
        # Solo procesar secrets_tunnel.toml
        if not event.src_path.endswith('secrets_tunnel.toml'):
            return
            
        current_time = time.time()
        
        # Debounce para evitar ejecuciones múltiples
        if current_time - self.last_sync < self.debounce_seconds:
            return
            
        self.last_sync = current_time
        
        print(f"🔄 Detectado cambio en secrets_tunnel.toml - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Ejecutar script de sincronización
        try:
            result = subprocess.run([
                sys.executable, self.script_path
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ Sincronización exitosa")
                if result.stdout:
                    print(result.stdout)
            else:
                print(f"❌ Error en sincronización (código {result.returncode})")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            print("❌ Timeout en script de sincronización")
        except Exception as e:
            print(f"❌ Error ejecutando script: {e}")


class URLSyncService:
    """Servicio principal de monitoreo de URL"""
    
    def __init__(self):
        self.observer = None
        self.running = False
        
        # Obtener rutas del proyecto
        self.project_root = Path(__file__).parent.parent
        self.backend_dir = self.project_root / "backend"
        self.script_path = self.project_root / "scripts" / "sync_frontend_url.py"
        
        # Validar que existan los archivos necesarios
        if not self.backend_dir.exists():
            raise FileNotFoundError(f"Directorio backend no encontrado: {self.backend_dir}")
            
        if not self.script_path.exists():
            raise FileNotFoundError(f"Script de sync no encontrado: {self.script_path}")
            
        # Configurar manejador de señales
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Manejador de señales para parada limpia"""
        print(f"\n🛑 Recibida señal {signum}. Deteniendo servicio...")
        self.stop()
        
    def start(self):
        """Inicia el servicio de monitoreo"""
        print("🚀 Iniciando servicio de monitoreo URL Cloudflare...")
        print(f"📂 Monitoreando: {self.backend_dir}")
        print(f"🔧 Script sync: {self.script_path}")
        
        # Ejecutar sincronización inicial
        print("🔄 Ejecutando sincronización inicial...")
        try:
            result = subprocess.run([
                sys.executable, str(self.script_path)
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ Sincronización inicial completada")
            else:
                print("⚠️  Sincronización inicial sin cambios o con advertencias")
                
        except Exception as e:
            print(f"⚠️  Error en sincronización inicial: {e}")
        
        # Configurar observer
        event_handler = TunnelConfigHandler(str(self.script_path))
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.backend_dir), recursive=False)
        
        # Iniciar monitoreo
        self.observer.start()
        self.running = True
        
        print("👀 Servicio activo. Monitoreando cambios en secrets_tunnel.toml...")
        print("📡 Presiona Ctrl+C para detener el servicio")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)
            
    def stop(self):
        """Detiene el servicio de monitoreo"""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            
        self.running = False
        print("✅ Servicio detenido correctamente")


def main():
    """Función principal del servicio"""
    try:
        service = URLSyncService()
        service.start()
    except KeyboardInterrupt:
        print("\n🛑 Servicio interrumpido por usuario")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error fatal en servicio: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()