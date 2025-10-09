#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare Tunnel Manager Resiliente - Fase 1.3
Optimizado para Jetson Nano con mejores timeouts y health checks
Resuelve: statement timeouts BD, timeouts health checks, auto-recovery mejorado
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
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Configuración optimizada para Jetson Nano
LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, 'cloudflare_tunnel_resilient.log')

# Configuración de logging con rotación
from logging.handlers import RotatingFileHandler
logger = logging.getLogger('CloudflareTunnelResilient')
logger.setLevel(logging.INFO)

# Handler para archivo con rotación (max 5MB, 3 archivos)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [CloudflareTunnel] %(message)s')
file_handler.setFormatter(file_formatter)

# Handler para consola
console_handler = logging.StreamHandler()
console_formatter = logging.Formatter('%(asctime)s - [CloudflareTunnel] %(message)s')
console_handler.setFormatter(console_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Configuración del túnel optimizada para Jetson Nano
SECRETS_PATH = os.path.join(os.path.dirname(__file__), 'secrets_tunnel.toml')
CLOUDFLARED_BIN = '/usr/local/bin/cloudflared'
BACKEND_URL = 'http://localhost:8000'
API_HEALTH_ENDPOINT = 'http://localhost:8000/health'
API_TUNNEL_UPDATE_ENDPOINT = 'http://localhost:8000/internal/tunnel_url_update'

# Configuración optimizada basada en análisis de logs
HEALTH_CHECK_INTERVAL = 60      # 60 segundos (más conservador para Jetson)
BACKEND_TIMEOUT = 15            # 15s timeout para backend (era 10s)
TUNNEL_TIMEOUT = 20             # 20s timeout para túnel (era 15s)
MAX_RESTART_ATTEMPTS = 3        # Reducido a 3 para evitar loops
INITIAL_RETRY_DELAY = 15        # 15s delay inicial (más conservador)
MAX_RETRY_DELAY = 180           # 3 minutos máximo
TUNNEL_STARTUP_TIMEOUT = 90     # 90s para detectar URL (más tiempo)
CONSECUTIVE_FAILURES_THRESHOLD = 3  # Failures antes de restart (era 5)

# Regex para extraer URL pública
tunnel_url_re = re.compile(r'https://[\w-]+\.trycloudflare\.com')

class ResilientCloudflareManager:
    """Manager resiliente de Cloudflare Tunnel optimizado para Jetson Nano"""
    
    def __init__(self):
        self.process = None
        self.current_url = None
        self.restart_count = 0
        self.last_health_check = None
        self.running = True
        self.consecutive_failures = 0
        self.last_restart = None
        self.health_monitor_thread = None
        
        # Estadísticas para debugging
        self.stats = {
            'total_restarts': 0,
            'health_checks_performed': 0,
            'health_checks_successful': 0,
            'backend_failures': 0,
            'tunnel_failures': 0,
            'start_time': datetime.now()
        }
        
        # Registrar manejadores de señales para systemd
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("ResilientCloudflareManager inicializado para Jetson Nano")
    
    def _signal_handler(self, signum, frame):
        """Manejar señales de terminación gracefully"""
        logger.info(f"Señal {signum} recibida, terminando túnel gracefully...")
        self.running = False
        self._stop_tunnel()
        self._log_final_stats()
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
        """Notificar a la API sobre cambio de URL del túnel con retry"""
        for attempt in range(2):  # Máximo 2 intentos
            try:
                # Payload compatible con el modelo TunnelUrlUpdate
                payload = {
                    "tunnel_url": url,  # Usar 'tunnel_url' según el modelo
                    "timestamp": datetime.now().isoformat()
                }
                
                response = requests.post(
                    API_TUNNEL_UPDATE_ENDPOINT,
                    json=payload,
                    timeout=8  # Timeout más generoso
                )
                if response.status_code == 200:
                    logger.info(f"✅ API notificada sobre nueva URL: {url}")
                    return True
                else:
                    logger.warning(f"⚠️  API respuesta {response.status_code} al notificar URL")
                    # Log del response para debugging
                    try:
                        logger.debug(f"Response: {response.text}")
                    except:
                        pass
            except Exception as e:
                logger.warning(f"⚠️  Intento {attempt+1} - No se pudo notificar API: {e}")
                if attempt < 1:  # Si no es el último intento
                    time.sleep(3)
        
        logger.error("❌ No se pudo notificar API después de 2 intentos")
        return False
    
    def _check_backend_health(self) -> bool:
        """Verificar que el backend esté respondiendo con timeout optimizado"""
        try:
            response = requests.get(API_HEALTH_ENDPOINT, timeout=BACKEND_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    self.stats['health_checks_successful'] += 1
                    logger.debug(f"💚 Backend healthy")
                    return True
                else:
                    logger.warning(f"⚠️  Backend health status: {data.get('status', 'unknown')}")
                    self.stats['backend_failures'] += 1
                    return False
            else:
                logger.warning(f"⚠️  Backend health check falló: {response.status_code}")
                self.stats['backend_failures'] += 1
                return False
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️  Backend health check timeout después de {BACKEND_TIMEOUT}s")
            self.stats['backend_failures'] += 1
            return False
        except Exception as e:
            logger.warning(f"⚠️  Backend no disponible: {e}")
            self.stats['backend_failures'] += 1
            return False
    
    def _check_tunnel_health(self) -> bool:
        """Verificar que el túnel esté funcionando con timeout optimizado"""
        if not self.current_url:
            logger.debug("⚠️  No hay URL de túnel para verificar")
            return False
        
        try:
            tunnel_health_url = f"{self.current_url}/health"
            response = requests.get(tunnel_health_url, timeout=TUNNEL_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    logger.debug(f"💚 Túnel healthy: {self.current_url}")
                    return True
                else:
                    logger.warning(f"⚠️  Túnel health status: {data.get('status', 'unknown')}")
                    self.stats['tunnel_failures'] += 1
                    return False
            else:
                logger.warning(f"⚠️  Túnel health check falló: {response.status_code}")
                self.stats['tunnel_failures'] += 1
                return False
                
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️  Túnel health check timeout después de {TUNNEL_TIMEOUT}s")
            self.stats['tunnel_failures'] += 1
            return False
        except Exception as e:
            logger.warning(f"⚠️  Túnel no accesible: {e}")
            self.stats['tunnel_failures'] += 1
            return False
    
    def _start_tunnel(self) -> bool:
        """Iniciar el proceso cloudflared con configuración optimizada"""
        try:
            logger.info(f"🚀 Iniciando cloudflared (intento {self.restart_count + 1}/{MAX_RESTART_ATTEMPTS})")
            
            # Comando optimizado para Jetson Nano
            cmd = [
                CLOUDFLARED_BIN, 'tunnel', 
                '--url', BACKEND_URL, 
                '--no-autoupdate',
                '--retries', '2',           # Reintentos internos de cloudflared
                '--retry-backoff', '10s'    # Backoff interno
            ]
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Esperar a que se detecte la URL del túnel
            url_detected = False
            start_time = time.time()
            
            logger.info(f"⏳ Esperando detección de URL del túnel (timeout: {TUNNEL_STARTUP_TIMEOUT}s)...")
            
            for line in self.process.stdout:
                logger.debug(f"📋 Cloudflared: {line.strip()}")
                
                # Buscar URL del túnel
                if not url_detected:
                    match = tunnel_url_re.search(line)
                    if match:
                        new_url = match.group(0)
                        logger.info(f"🎯 URL del túnel detectada: {new_url}")
                        
                        # Actualizar URL y notificar
                        old_url = self.current_url
                        self.current_url = new_url
                        
                        # Solo actualizar archivos si la URL cambió
                        if old_url != new_url:
                            self._update_secrets_tunnel(new_url)
                            self._notify_api_url_change(new_url)
                            logger.info(f"🔄 URL actualizada de {old_url} a {new_url}")
                        
                        url_detected = True
                        
                        # Reset contador de reintentos en éxito
                        self.restart_count = 0
                        break
                
                # Timeout para detección de URL
                if time.time() - start_time > TUNNEL_STARTUP_TIMEOUT:
                    logger.error(f"⏰ Timeout esperando URL del túnel ({TUNNEL_STARTUP_TIMEOUT}s)")
                    break
            
            if url_detected:
                logger.info(f"✅ Túnel Cloudflare iniciado exitosamente: {self.current_url}")
                self.consecutive_failures = 0  # Reset failures
                return True
            else:
                logger.error(f"❌ No se pudo detectar URL del túnel")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error iniciando túnel: {e}")
            return False
    
    def _stop_tunnel(self):
        """Detener el proceso cloudflared de manera segura"""
        if self.process:
            try:
                logger.info("🛑 Deteniendo túnel Cloudflare...")
                self.process.terminate()
                
                # Esperar terminación graceful
                try:
                    self.process.wait(timeout=15)  # Timeout más generoso
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
        """Calcular delay con backoff exponencial optimizado"""
        delay = min(INITIAL_RETRY_DELAY * (2 ** self.restart_count), MAX_RETRY_DELAY)
        return delay
    
    def _restart_tunnel(self) -> bool:
        """Reiniciar túnel con backoff exponencial y limits"""
        if self.restart_count >= MAX_RESTART_ATTEMPTS:
            logger.error(f"💥 Máximo de reintentos alcanzado ({MAX_RESTART_ATTEMPTS})")
            return False
        
        # Verificar si no estamos restarting demasiado frecuentemente
        if self.last_restart:
            time_since_last = (datetime.now() - self.last_restart).total_seconds()
            if time_since_last < 60:  # Menos de 1 minuto desde último restart
                logger.warning(f"⚠️  Restart muy frecuente, esperando más tiempo...")
                time.sleep(60 - time_since_last)
        
        # Detener túnel actual
        self._stop_tunnel()
        
        # Calcular delay
        delay = self._calculate_retry_delay()
        logger.info(f"🔄 Reintentando en {delay}s... (intento {self.restart_count + 1}/{MAX_RESTART_ATTEMPTS})")
        time.sleep(delay)
        
        # Incrementar contador y registrar timestamp
        self.restart_count += 1
        self.last_restart = datetime.now()
        self.stats['total_restarts'] += 1
        
        # Intentar reiniciar
        return self._start_tunnel()
    
    def run_health_monitor(self):
        """Ejecutar monitoreo de salud en loop principal optimizado"""
        logger.info(f"💚 Iniciando monitoreo de salud optimizado (cada {HEALTH_CHECK_INTERVAL}s)")
        
        # Dar tiempo para propagación DNS inicial del túnel
        initial_wait = 90  # 90 segundos para Jetson Nano
        logger.info(f"⏳ Esperando {initial_wait}s para propagación DNS del túnel...")
        time.sleep(initial_wait)
        
        while self.running:
            try:
                current_time = time.time()
                self.stats['health_checks_performed'] += 1
                
                # Verificar salud del backend (más tolerante)
                backend_healthy = self._check_backend_health()
                
                # Verificar salud del túnel
                tunnel_healthy = self._check_tunnel_health() if self.current_url else False
                
                # Verificar si el proceso sigue vivo
                process_alive = self.process and self.process.poll() is None
                
                self.last_health_check = current_time
                
                # Evaluar si necesita restart (lógica más inteligente)
                needs_restart = False
                reason = ""
                
                if not process_alive:
                    needs_restart = True
                    reason = "Proceso cloudflared terminó"
                    self.consecutive_failures += 1
                elif not tunnel_healthy:
                    self.consecutive_failures += 1
                    if self.consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                        needs_restart = True
                        reason = f"Túnel inaccesible ({self.consecutive_failures} failures consecutivas)"
                    else:
                        logger.warning(f"⚠️  Túnel unhealthy ({self.consecutive_failures}/{CONSECUTIVE_FAILURES_THRESHOLD})")
                else:
                    # Todo está bien, reset failures
                    if self.consecutive_failures > 0:
                        logger.info(f"✅ Túnel recuperado después de {self.consecutive_failures} failures")
                        self.consecutive_failures = 0
                
                # Log periódico de estadísticas (cada 10 checks)
                if self.stats['health_checks_performed'] % 10 == 0:
                    self._log_stats()
                
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
    
    def _log_stats(self):
        """Log de estadísticas del manager"""
        uptime = datetime.now() - self.stats['start_time']
        success_rate = (self.stats['health_checks_successful'] / max(1, self.stats['health_checks_performed'])) * 100
        
        logger.info(f"📊 Stats - Uptime: {uptime}, Health success: {success_rate:.1f}%, "
                   f"Restarts: {self.stats['total_restarts']}, "
                   f"Backend failures: {self.stats['backend_failures']}, "
                   f"Tunnel failures: {self.stats['tunnel_failures']}")
    
    def _log_final_stats(self):
        """Log de estadísticas finales al terminar"""
        logger.info("📊 ESTADÍSTICAS FINALES:")
        self._log_stats()
        logger.info(f"   - Consecutive failures at exit: {self.consecutive_failures}")
        logger.info(f"   - Current URL: {self.current_url}")
    
    def run(self):
        """Ejecutar el gestor del túnel resiliente"""
        logger.info("🚀 INICIANDO RESILIENT CLOUDFLARE TUNNEL MANAGER v2.0")
        logger.info(f"📋 Configuración optimizada para Jetson Nano:")
        logger.info(f"   - Backend: {BACKEND_URL}")
        logger.info(f"   - Health check: cada {HEALTH_CHECK_INTERVAL}s")
        logger.info(f"   - Backend timeout: {BACKEND_TIMEOUT}s")
        logger.info(f"   - Tunnel timeout: {TUNNEL_TIMEOUT}s")
        logger.info(f"   - Max reintentos: {MAX_RESTART_ATTEMPTS}")
        logger.info(f"   - Backoff: {INITIAL_RETRY_DELAY}s - {MAX_RETRY_DELAY}s")
        logger.info(f"   - Failures threshold: {CONSECUTIVE_FAILURES_THRESHOLD}")
        
        # Verificar que backend esté disponible antes de iniciar túnel
        if not self._check_backend_health():
            logger.warning("⚠️  Backend no disponible, pero iniciando túnel de todas formas")
        
        # Iniciar túnel
        if self._start_tunnel():
            # Iniciar health monitor en thread separado
            self.health_monitor_thread = threading.Thread(target=self.run_health_monitor, daemon=False)
            self.health_monitor_thread.start()
            
            # Mantener hilo principal vivo para systemd
            try:
                self.health_monitor_thread.join()
            except KeyboardInterrupt:
                logger.info("🛑 Interrupción recibida")
        else:
            logger.error("💥 No se pudo iniciar túnel Cloudflare")
            sys.exit(1)
        
        # Cleanup al terminar
        self._stop_tunnel()
        self._log_final_stats()
        logger.info("👋 Resilient Cloudflare Tunnel Manager terminado")

def main():
    """Función principal"""
    manager = ResilientCloudflareManager()
    manager.run()

if __name__ == "__main__":
    main()