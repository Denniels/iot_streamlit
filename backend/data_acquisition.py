"""
Adquisición y formateo de datos de todos los dispositivos
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List
from backend.config import get_logger
from backend.db_writer import LocalPostgresClient
from backend.arduino_detector import ArduinoDetector
from backend.device_scanner import DeviceScanner
from backend.modbus_scanner import ModbusScanner

logger = get_logger(__name__)

class DataAcquisition:
    """Coordinador principal para adquisición de datos"""
    
    def __init__(self):
        self.db_client = LocalPostgresClient()
        self.arduino_detector = ArduinoDetector(self.db_client)
        self.device_scanner = DeviceScanner(self.db_client)
        self.modbus_scanner = ModbusScanner(self.db_client)
        self.running = False
        self.data_cache = {}
    
    def initialize_devices(self):
        """Inicializar y detectar todos los dispositivos - SOLO RED, NO USB"""
        logger.info("Iniciando detección de dispositivos de red...")
        
        # Solo escanear red para dispositivos (incluye ESP32 WiFi y Arduino Ethernet)
        try:
            discovered_devices = self.device_scanner.scan_network()
            logger.info(f"{len(discovered_devices)} dispositivos de red encontrados")
        except Exception as e:
            logger.error(f"Error escaneando red: {e}")
            discovered_devices = []
        
        # Detectar Arduinos Ethernet específicamente
        logger.info("🔍 Iniciando detección específica de Arduinos Ethernet...")
        try:
            ethernet_arduinos = self.arduino_detector.detect_ethernet_arduinos()
            logger.info(f"✅ {len(ethernet_arduinos)} Arduinos Ethernet encontrados")
            for arduino in ethernet_arduinos:
                logger.info(f"  📡 Arduino Ethernet: {arduino.get('device_id')} en {arduino.get('ip_address')}")
        except Exception as e:
            logger.error(f"❌ Error detectando Arduinos Ethernet: {e}")
        
        # Detectar dispositivos ESP32 WiFi específicamente
        logger.info("🔍 Iniciando detección específica de ESP32 WiFi...")
        try:
            esp32_devices = self.arduino_detector.detect_esp32_wifi()
            logger.info(f"✅ {len(esp32_devices)} ESP32 WiFi encontrados")
            for esp32 in esp32_devices:
                logger.info(f"  📡 ESP32 WiFi: {esp32.get('device_id')} en {esp32.get('ip_address')}")
        except Exception as e:
            logger.error(f"❌ Error detectando ESP32 WiFi: {e}")
        
        # Detectar dispositivos Modbus
        try:
            # Obtener IPs de dispositivos descubiertos para escaneo Modbus
            ip_list = [device.get('ip_address') for device in discovered_devices 
                      if device.get('ip_address')]
            
            if ip_list:
                modbus_devices = self.modbus_scanner.scan_modbus_tcp(ip_list)
                logger.info(f"{len(modbus_devices)} dispositivos Modbus encontrados")
        except Exception as e:
            logger.error(f"Error detectando dispositivos Modbus: {e}")
        
        logger.info("Inicialización de dispositivos completada")
    
    def collect_all_data(self) -> Dict[str, Any]:
        """Recopilar datos de todos los dispositivos - SOLO RED, NO USB"""
        collected_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),  # Siempre UTC ISO8601
            'network_devices': [],
            'modbus_devices': {},
            'errors': []
        }
        
        # Leer datos de dispositivos de red (Arduino Ethernet y ESP32 WiFi)
        try:
            devices = self.db_client.get_devices()
            network_devices = [d for d in devices if d.get('device_type') in ['arduino_ethernet', 'esp32_wifi']]
            
            for device in network_devices:
                try:
                    device_id = device.get('device_id')
                    device_type = device.get('device_type')
                    ip = device.get('ip_address')
                    
                    # Fallback: si no hay IP guardada, intentar encontrar por device_id conocido
                    if not ip:
                        if device_id == 'esp32_wifi_001':
                            ip = '192.168.0.110'  # IP conocida del ESP32
                        elif device_id == 'arduino_eth_001':
                            ip = '192.168.0.109'  # IP conocida del Arduino Ethernet
                    
                    if ip:
                        # Usar método genérico para leer datos de red
                        if device_type == 'esp32_wifi':
                            data = self.arduino_detector.read_esp32_data(ip)
                        else:
                            port = device.get('port', 80)
                            data = self.arduino_detector.read_ethernet_data(ip, port)
                        
                        if data:
                            collected_data['network_devices'].append({
                                'device_id': device_id,
                                'device_type': device_type,
                                'data': data
                            })
                    else:
                        logger.warning(f"Dispositivo {device_id} sin IP configurada")
                        
                except Exception as e:
                    error = f"Error leyendo {device.get('device_id')}: {e}"
                    logger.error(error)
                    collected_data['errors'].append(error)
        
        except Exception as e:
            error = f"Error procesando dispositivos de red: {e}"
            logger.error(error)
            collected_data['errors'].append(error)
        
        # Leer datos dispositivos Modbus
        try:
            modbus_data = self.modbus_scanner.read_all_modbus_devices()
            collected_data['modbus_devices'] = modbus_data
        except Exception as e:
            error = f"Error leyendo dispositivos Modbus: {e}"
            logger.error(error)
            collected_data['errors'].append(error)
        
        # Actualizar cache
        self.data_cache = collected_data
        
        # Log resumen
        total_points = len(collected_data['network_devices'])
        total_points += sum(len(data) for data in collected_data['modbus_devices'].values())
        
        logger.debug(f"Datos recopilados: {total_points} puntos de datos")
        
        return collected_data
    
    def start_continuous_acquisition(self, interval: int = 10):
        """Iniciar adquisición continua de datos"""
        logger.info(f"Iniciando adquisición continua cada {interval} segundos")
        self.running = True
        
        while self.running:
            try:
                start_time = time.time()
                
                # Recopilar datos
                data = self.collect_all_data()
                
                # Log evento del sistema si hay errores
                if data['errors']:
                    self.db_client.log_system_event(
                        'acquisition_errors',
                        None,
                        f"{len(data['errors'])} errores en adquisición",
                        {'errors': data['errors']}
                    )
                
                # Calcular tiempo de procesamiento
                processing_time = time.time() - start_time
                sleep_time = max(0, interval - processing_time)
                
                logger.debug(f"Ciclo completado en {processing_time:.2f}s, esperando {sleep_time:.2f}s")
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("Adquisición detenida por usuario")
                self.stop_acquisition()
                break
            except Exception as e:
                logger.error(f"Error en ciclo de adquisición: {e}")
                self.db_client.log_system_event(
                    'acquisition_error',
                    None,
                    f"Error crítico en adquisición: {str(e)}"
                )
                time.sleep(5)  # Esperar antes de reintentar
    
    def stop_acquisition(self):
        """Detener adquisición continua y liberar recursos de forma robusta"""
        logger.info("[SHUTDOWN] Deteniendo adquisición de datos...")
        self.running = False

        # Cerrar conexiones Arduino
        try:
            logger.info("[SHUTDOWN] Cerrando conexiones Arduino...")
            self.arduino_detector.close_connections()
            logger.info("[SHUTDOWN] Conexiones Arduino cerradas.")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error cerrando conexiones Arduino: {e}")

        # Cerrar conexiones Modbus
        try:
            logger.info("[SHUTDOWN] Cerrando conexiones Modbus...")
            self.modbus_scanner.close_all_connections()
            logger.info("[SHUTDOWN] Conexiones Modbus cerradas.")
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error cerrando conexiones Modbus: {e}")

        # Log evento
        try:
            self.db_client.log_system_event(
                'acquisition_stopped',
                None,
                'Adquisición de datos detenida'
            )
        except Exception as e:
            logger.error(f"[SHUTDOWN] Error logueando evento de apagado: {e}")

        logger.info("[SHUTDOWN] Apagado de adquisición completado.")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Obtener estado actual del sistema"""
        devices = self.db_client.get_devices()
        
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),  # Siempre UTC ISO8601
            'running': self.running,
            'devices': {
                'total': len(devices),
                'online': len([d for d in devices if d.get('status') == 'online']),
                'offline': len([d for d in devices if d.get('status') == 'offline']),
                'error': len([d for d in devices if d.get('status') == 'error'])
            },
            'last_data': self.data_cache.get('timestamp'),
            'errors': self.data_cache.get('errors', [])
        }
        
        return status
    
    def get_latest_data(self) -> Dict[str, Any]:
        """Obtener los datos más recientes"""
        return self.data_cache if self.data_cache else {
            'timestamp': datetime.now(timezone.utc).isoformat(),  # Siempre UTC ISO8601
            'message': 'No hay datos disponibles'
        }
