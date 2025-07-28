"""
Adquisición y formateo de datos de todos los dispositivos
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List
from backend.config import get_logger
from backend.db_writer import SupabaseClient
from backend.arduino_detector import ArduinoDetector
from backend.device_scanner import DeviceScanner
from backend.modbus_scanner import ModbusScanner

logger = get_logger(__name__)

class DataAcquisition:
    """Coordinador principal para adquisición de datos"""
    
    def __init__(self):
        self.db_client = SupabaseClient()
        self.arduino_detector = ArduinoDetector(self.db_client)
        self.device_scanner = DeviceScanner(self.db_client)
        self.modbus_scanner = ModbusScanner(self.db_client)
        self.running = False
        self.data_cache = {}
    
    def initialize_devices(self):
        """Inicializar y detectar todos los dispositivos"""
        logger.info("Iniciando detección de dispositivos...")
        
        # 1. Detectar Arduino USB
        try:
            if self.arduino_detector.detect_usb_arduino():
                logger.info("Arduino USB inicializado")
        except Exception as e:
            logger.error(f"Error inicializando Arduino USB: {e}")
        
        # 2. Escanear red para dispositivos generales
        try:
            discovered_devices = self.device_scanner.scan_network()
            logger.info(f"{len(discovered_devices)} dispositivos de red encontrados")
        except Exception as e:
            logger.error(f"Error escaneando red: {e}")
            discovered_devices = []
        
        # 3. Detectar Arduinos Ethernet
        try:
            ethernet_arduinos = self.arduino_detector.detect_ethernet_arduinos()
            logger.info(f"{len(ethernet_arduinos)} Arduinos Ethernet encontrados")
        except Exception as e:
            logger.error(f"Error detectando Arduinos Ethernet: {e}")
        
        # 4. Detectar dispositivos Modbus
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
        """Recopilar datos de todos los dispositivos"""
        collected_data = {
            'timestamp': datetime.now().isoformat(),
            'arduino_usb': None,
            'arduino_ethernet': [],
            'modbus_devices': {},
            'errors': []
        }
        
        # 1. Leer datos Arduino USB
        try:
            usb_data = self.arduino_detector.read_usb_data()
            if usb_data:
                collected_data['arduino_usb'] = usb_data
        except Exception as e:
            error = f"Error leyendo Arduino USB: {e}"
            logger.error(error)
            collected_data['errors'].append(error)
        
        # 2. Leer datos Arduinos Ethernet
        try:
            devices = self.db_client.get_devices()
            ethernet_devices = [d for d in devices if d.get('device_type') == 'arduino_ethernet']
            
            for device in ethernet_devices:
                try:
                    ip = device.get('ip_address')
                    port = device.get('port')
                    
                    if ip and port:
                        data = self.arduino_detector.read_ethernet_data(ip, port)
                        if data:
                            collected_data['arduino_ethernet'].append({
                                'device_id': device['device_id'],
                                'data': data
                            })
                except Exception as e:
                    error = f"Error leyendo {device.get('device_id')}: {e}"
                    logger.error(error)
                    collected_data['errors'].append(error)
        
        except Exception as e:
            error = f"Error procesando Arduinos Ethernet: {e}"
            logger.error(error)
            collected_data['errors'].append(error)
        
        # 3. Leer datos dispositivos Modbus
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
        total_points = 0
        if collected_data['arduino_usb']:
            total_points += 1
        total_points += len(collected_data['arduino_ethernet'])
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
            'timestamp': datetime.now().isoformat(),
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
            'timestamp': datetime.now().isoformat(),
            'message': 'No hay datos disponibles'
        }
