"""
Detección y comunicación con Arduinos (USB y Ethernet)
"""
import serial
import socket
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import time
from backend.config import Config, get_logger
from backend.db_writer import SupabaseClient

logger = get_logger(__name__)

class ArduinoDetector:
    """Detector y comunicador para Arduinos USB y Ethernet"""
    
    def __init__(self, db_client: SupabaseClient):
        self.db_client = db_client
        self.usb_connection = None
        self.detected_devices = []
    
    def detect_usb_arduino(self) -> bool:
        """Detectar Arduino conectado por USB"""
        try:
            self.usb_connection = serial.Serial(
                Config.USB_PORT, 
                Config.USB_BAUDRATE, 
                timeout=1
            )
            
            # Enviar comando de prueba
            self.usb_connection.write(b'ping\n')
            time.sleep(0.5)
            
            if self.usb_connection.in_waiting > 0:
                response = self.usb_connection.readline().decode().strip()
                if 'pong' in response.lower():
                    # Registrar dispositivo
                    device_data = {
                        'device_id': 'arduino_usb',
                        'device_type': 'arduino_usb',
                        'name': 'Arduino USB',
                        'port': Config.USB_PORT,
                        'status': 'online',
                        'metadata': {'baudrate': Config.USB_BAUDRATE}
                    }
                    
                    self.db_client.register_device(device_data)
                    self.db_client.log_system_event('device_connected', 'arduino_usb', 'Arduino USB conectado')
                    
                    logger.info("Arduino USB detectado y registrado")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error detectando Arduino USB: {e}")
            if self.usb_connection:
                self.usb_connection.close()
            return False
    
    def read_usb_data(self) -> Optional[Dict[str, Any]]:
        """Leer datos del Arduino USB"""
        if not self.usb_connection or not self.usb_connection.is_open:
            return None
        
        try:
            if self.usb_connection.in_waiting > 0:
                raw_data = self.usb_connection.readline().decode().strip()
                
                # Parsear datos (formato esperado: "sensor:value,sensor2:value2")
                data = self._parse_arduino_data(raw_data)
                
                if data:
                    # Preparar para inserción en BD
                    sensor_data = {
                        'device_id': 'arduino_usb',
                        'sensor_type': data.get('sensor_type', 'unknown'),
                        'value': data.get('value'),
                        'unit': data.get('unit', ''),
                        'raw_data': data,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.db_client.insert_sensor_data(sensor_data)
                    return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error leyendo datos USB: {e}")
            return None
    
    def detect_ethernet_arduinos(self, network_range: str = "192.168.1") -> List[Dict]:
        """Detectar Arduinos conectados por Ethernet"""
        detected = []
        
        try:
            # Escanear puertos comunes para Arduinos con Ethernet Shield
            common_ports = [80, 8080, 23, 1883]  # HTTP, HTTP-alt, Telnet, MQTT
            
            for i in range(1, 255):
                ip = f"{network_range}.{i}"
                
                for port in common_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex((ip, port))
                        
                        if result == 0:
                            # Intentar comunicación básica
                            if self._test_arduino_ethernet(ip, port):
                                device_id = f"arduino_eth_{ip}_{port}"
                                device_data = {
                                    'device_id': device_id,
                                    'device_type': 'arduino_ethernet',
                                    'name': f'Arduino Ethernet {ip}',
                                    'ip_address': ip,
                                    'port': port,
                                    'status': 'online',
                                    'metadata': {'protocol': 'tcp'}
                                }
                                
                                self.db_client.register_device(device_data)
                                self.db_client.log_system_event('device_connected', device_id, f'Arduino Ethernet detectado en {ip}:{port}')
                                
                                detected.append(device_data)
                                logger.info(f"Arduino Ethernet detectado: {ip}:{port}")
                        
                        sock.close()
                        
                    except Exception as e:
                        if sock:
                            sock.close()
                        continue
            
            return detected
            
        except Exception as e:
            logger.error(f"Error escaneando Arduinos Ethernet: {e}")
            return []
    
    def read_ethernet_data(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """Leer datos de Arduino Ethernet"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((ip, port))
            
            # Enviar comando de lectura
            sock.send(b'GET_DATA\n')
            response = sock.recv(1024).decode().strip()
            
            sock.close()
            
            if response:
                data = self._parse_arduino_data(response)
                
                if data:
                    device_id = f"arduino_eth_{ip}_{port}"
                    sensor_data = {
                        'device_id': device_id,
                        'sensor_type': data.get('sensor_type', 'unknown'),
                        'value': data.get('value'),
                        'unit': data.get('unit', ''),
                        'raw_data': data,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    self.db_client.insert_sensor_data(sensor_data)
                    return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error leyendo datos Ethernet {ip}:{port}: {e}")
            return None
    
    def _test_arduino_ethernet(self, ip: str, port: int) -> bool:
        """Probar si hay un Arduino en la IP/puerto especificado"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((ip, port))
            
            # Enviar comando de identificación
            sock.send(b'WHO\n')
            response = sock.recv(1024).decode().strip()
            
            sock.close()
            
            return 'arduino' in response.lower()
            
        except:
            return False
    
    def _parse_arduino_data(self, raw_data: str) -> Optional[Dict[str, Any]]:
        """Parsear datos del Arduino"""
        try:
            # Formato esperado: "temp:25.5,humid:60.2" o JSON
            if raw_data.startswith('{'):
                return json.loads(raw_data)
            
            # Formato clave:valor separado por comas
            data = {}
            pairs = raw_data.split(',')
            
            for pair in pairs:
                if ':' in pair:
                    key, value = pair.split(':', 1)
                    try:
                        data[key.strip()] = float(value.strip())
                    except ValueError:
                        data[key.strip()] = value.strip()
            
            if data:
                # Asignar primer valor como principal
                first_key = list(data.keys())[0]
                return {
                    'sensor_type': first_key,
                    'value': data[first_key],
                    'raw_data': data
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parseando datos Arduino: {e}")
            return None
    
    def close_connections(self):
        """Cerrar todas las conexiones"""
        if self.usb_connection and self.usb_connection.is_open:
            self.usb_connection.close()
            logger.info("Conexión USB cerrada")
