#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script mejorado para Cloudflare Tunnel con auto-recovery y health checks
Optimizado para Jetson Nano - Fase 1.3 del plan de estabilización
"""

import subprocess
import toml
import os
import re
import sys
import logging
import time
import signal
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Configuración mejorada para Jetson Nano
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'cloudflare_tunnel.log')

# Configuración de logging mejorada
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [CloudflareTunnel] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración del túnel
SECRETS_PATH = os.path.join(os.path.dirname(__file__), 'secrets_tunnel.toml')
CLOUDFLARED_BIN = '/usr/local/bin/cloudflared'
BACKEND_URL = 'http://localhost:8000'  # Puerto FastAPI
API_HEALTH_ENDPOINT = 'http://localhost:8000/health'
API_TUNNEL_UPDATE_ENDPOINT = 'http://localhost:8000/internal/tunnel_url_update'

# Configuración de auto-recovery optimizada para Jetson Nano
HEALTH_CHECK_INTERVAL = 60  # 60 segundos (más conservador, era 45)
MAX_RESTART_ATTEMPTS = 3    # Reducido a 3 para evitar loops
INITIAL_RETRY_DELAY = 15    # 15s delay inicial (más conservador, era 10s)
MAX_RETRY_DELAY = 180       # 3 minutos máximo (era 2 min)
TUNNEL_STARTUP_TIMEOUT = 90 # 90s para detectar URL (más tiempo, era 60s)

# Regex para extraer URL pública
tunnel_url_re = re.compile(r'https://[\w-]+\.trycloudflare\.com')

class CloudflareTunnelManager:
    """Gestor de túnel Cloudflare con auto-recovery y health checks"""
    
    def __init__(self):
        self.process = None
        self.current_url = None
        self.restart_count = 0
        self.last_health_check = None
        self.running = True
        
        # Registrar manejadores de señales
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Manejar señales de terminación gracefully"""
        logger.info(f"🛑 Señal {signum} recibida, terminando túnel...")
        self.running = False
        self._stop_tunnel()
        sys.exit(0)
    
    def _update_secrets_tunnel(self, url: str) -> bool:
        """Actualizar secrets_tunnel.toml con nueva URL"""
        try:
            data = {'cloudflare': {'url': url}}
            with open(SECRETS_PATH, 'w') as f:
                toml.dump(data, f)
            logger.info(f"✅ URL guardada en secrets_tunnel.toml: {url}")
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando URL en secrets: {e}")
            return False
    
    def _notify_api_url_change(self, url: str) -> bool:
        """Notificar a la API sobre cambio de URL del túnel"""
        try:
            response = requests.post(
                API_TUNNEL_UPDATE_ENDPOINT,
                json={"tunnel_url": url, "timestamp": datetime.now().isoformat()},
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"✅ API notificada sobre nueva URL: {url}")
                return True
            else:
                logger.warning(f"⚠️  API respuesta {response.status_code} al notificar URL")
                return False
        except Exception as e:
            logger.warning(f"⚠️  No se pudo notificar API sobre nueva URL: {e}")
            return False
    
    def _check_backend_health(self) -> bool:
        """Verificar que el backend esté respondiendo"""
        try:
            response = requests.get(API_HEALTH_ENDPOINT, timeout=15)  # Increased from 10s
            if response.status_code == 200:
                data = response.json()
                # El endpoint /health retorna {"status": "healthy", ...}
                if data.get('status') == 'healthy':
                    logger.debug(f"💚 Backend healthy")
                    return True
            logger.warning(f"⚠️  Backend health check falló: {response.status_code}")
            return False
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️  Backend health timeout después de 15s")
            return False
        except Exception as e:
            logger.warning(f"⚠️  Backend no disponible: {e}")
            return False
    
    def _check_tunnel_health(self) -> bool:
        """Verificar que el túnel esté funcionando"""
        if not self.current_url:
            return False
        
        try:
            # Verificar que el túnel responda
            tunnel_health_url = f"{self.current_url}/health"
            response = requests.get(tunnel_health_url, timeout=20)  # Increased from 15s
            
            if response.status_code == 200:
                data = response.json()
                # El endpoint /health retorna {"status": "healthy", ...}
                if data.get('status') == 'healthy':
                    logger.debug(f"💚 Túnel healthy: {self.current_url}")
                    return True
            
            logger.warning(f"⚠️  Túnel health check falló: {response.status_code}")
            return False
            
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️  Túnel health timeout después de 20s")
            return False
        except Exception as e:
            logger.warning(f"⚠️  Túnel no accesible: {e}")
            return False
    
    def _start_tunnel(self) -> bool:
        """Iniciar el proceso cloudflared"""
        try:
            logger.info(f"🚀 Iniciando cloudflared (intento {self.restart_count + 1}/{MAX_RESTART_ATTEMPTS})")
            
            self.process = subprocess.Popen(
                [CLOUDFLARED_BIN, 'tunnel', '--url', BACKEND_URL, '--no-autoupdate'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Esperar a que se detecte la URL del túnel
            url_detected = False
            start_time = time.time()
            
            for line in self.process.stdout:
                logger.info(f"📋 Cloudflared: {line.strip()}")
                
                # Buscar URL del túnel
                if not url_detected:
                    match = tunnel_url_re.search(line)
                    if match:
                        new_url = match.group(0)
                        logger.info(f"🎯 URL del túnel detectada: {new_url}")
                        
                        # Actualizar URL y notificar
                        self.current_url = new_url
                        self._update_secrets_tunnel(new_url)
                        self._notify_api_url_change(new_url)
                        url_detected = True
                        
                        # Reset contador de reintentos en éxito
                        self.restart_count = 0
                        break
                
                # Timeout para detección de URL
                if time.time() - start_time > TUNNEL_STARTUP_TIMEOUT:
                    logger.error(f"⏰ Timeout esperando URL del túnel ({TUNNEL_STARTUP_TIMEOUT}s)")
                    break
            
            if url_detected:
                logger.info(f"✅ Túnel Cloudflare iniciado exitosamente")
                return True
            else:
                logger.error(f"❌ No se pudo detectar URL del túnel")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error iniciando túnel: {e}")
            return False
    
    def _stop_tunnel(self):
        """Detener el proceso cloudflared"""
        if self.process:
            try:
                logger.info("🛑 Deteniendo túnel Cloudflare...")
                self.process.terminate()
                
                # Esperar terminación graceful
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("⚠️  Forzando terminación del túnel")
                    self.process.kill()
                    self.process.wait()
                
                logger.info("✅ Túnel Cloudflare detenido")
                
            except Exception as e:
                logger.error(f"❌ Error deteniendo túnel: {e}")
            finally:
                self.process = None
    
    def _calculate_retry_delay(self) -> int:
        """Calcular delay con backoff exponencial"""
        delay = min(INITIAL_RETRY_DELAY * (2 ** self.restart_count), MAX_RETRY_DELAY)
        return delay
    
    def _restart_tunnel(self) -> bool:
        """Reiniciar túnel con backoff exponencial"""
        if self.restart_count >= MAX_RESTART_ATTEMPTS:
            logger.error(f"💥 Máximo de reintentos alcanzado ({MAX_RESTART_ATTEMPTS})")
            return False
        
        # Detener túnel actual
        self._stop_tunnel()
        
        # Calcular delay
        delay = self._calculate_retry_delay()
        logger.info(f"🔄 Reintentando en {delay}s... (intento {self.restart_count + 1}/{MAX_RESTART_ATTEMPTS})")
        time.sleep(delay)
        
        # Incrementar contador
        self.restart_count += 1
        
        # Intentar reiniciar
        return self._start_tunnel()
    
    def run_health_monitor(self):
        """Ejecutar monitoreo de salud en loop principal"""
        logger.info(f"💚 Iniciando monitoreo de salud (cada {HEALTH_CHECK_INTERVAL}s)")
        
        # Dar tiempo para propagación DNS inicial del túnel (60 segundos)
        logger.info("⏳ Esperando 60s para propagación DNS del túnel...")
        time.sleep(60)
        
        while self.running:
            try:
                current_time = time.time()
                
                # Verificar salud del backend
                backend_healthy = self._check_backend_health()
                
                # Verificar salud del túnel
                tunnel_healthy = self._check_tunnel_health() if self.current_url else False
                
                # Verificar si el proceso sigue vivo
                process_alive = self.process and self.process.poll() is None
                
                self.last_health_check = current_time
                
                # Evaluar si necesita restart
                needs_restart = False
                reason = ""
                
                if not process_alive:
                    needs_restart = True
                    reason = "Proceso cloudflared terminó"
                elif not backend_healthy:
                    logger.warning("⚠️  Backend no healthy, pero continuando túnel")
                elif not tunnel_healthy:
                    needs_restart = True
                    reason = "Túnel no accesible desde exterior"
                
                if needs_restart:
                    logger.warning(f"⚠️  Reinicio necesario: {reason}")
                    if not self._restart_tunnel():
                        logger.error("💥 No se pudo reiniciar túnel, saliendo")
                        break
                
                # Esperar hasta próximo health check
                time.sleep(HEALTH_CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("🛑 Interrupción de usuario")
                break
            except Exception as e:
                logger.error(f"❌ Error en monitoreo de salud: {e}")
                time.sleep(HEALTH_CHECK_INTERVAL)
    
    def run(self):
        """Ejecutar el gestor del túnel"""
        logger.info("🚀 INICIANDO CLOUDFLARE TUNNEL MANAGER v2.0")
        logger.info(f"📋 Configuración:")
        logger.info(f"   - Backend: {BACKEND_URL}")
        logger.info(f"   - Health check: cada {HEALTH_CHECK_INTERVAL}s")
        logger.info(f"   - Max reintentos: {MAX_RESTART_ATTEMPTS}")
        logger.info(f"   - Backoff: {INITIAL_RETRY_DELAY}s - {MAX_RETRY_DELAY}s")
        
        # Verificar que backend esté disponible antes de iniciar túnel
        if not self._check_backend_health():
            logger.warning("⚠️  Backend no disponible, pero iniciando túnel de todas formas")
        
        # Iniciar túnel
        if self._start_tunnel():
            # Ejecutar monitoreo de salud
            self.run_health_monitor()
        else:
            logger.error("💥 No se pudo iniciar túnel Cloudflare")
            sys.exit(1)
        
        # Cleanup al terminar
        self._stop_tunnel()
        logger.info("👋 Cloudflare Tunnel Manager terminado")

def main():
    """Función principal"""
    tunnel_manager = CloudflareTunnelManager()
    tunnel_manager.run()

if __name__ == "__main__":
    main()