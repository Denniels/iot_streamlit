"""
Detección y comunicación con Arduinos (USB y Ethernet)
"""
import serial
import serial.tools.list_ports
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
        self.auto_detected_port = None
    
    def auto_detect_arduino_port(self) -> Optional[str]:
        """Detectar automáticamente el puerto del Arduino"""
        logger.info("🔍 Detectando puerto Arduino automáticamente...")
        
        # Buscar puertos Arduino
        ports = serial.tools.list_ports.comports()
        arduino_ports = []
        
        for port in ports:
            # Buscar Arduino por VID/PID o descripción
            if (port.vid == 0x2341 or  # Arduino VID oficial
                'arduino' in port.description.lower() or
                'uno' in port.description.lower() or
                'acm' in port.device.lower()):
                
                arduino_ports.append(port.device)
                logger.info(f"📍 Puerto Arduino encontrado: {port.device} - {port.description}")
        
        # Probar cada puerto encontrado
        for port_device in arduino_ports:
            if self._test_arduino_communication(port_device):
                logger.info(f"✅ Arduino funcionando en: {port_device}")
                return port_device
        
        # Si no encuentra automáticamente, usar configuración
        config_port = Config.USB_PORT
        if self._test_arduino_communication(config_port):
            logger.info(f"✅ Arduino funcionando en puerto configurado: {config_port}")
            return config_port
        
        logger.error("❌ No se pudo detectar Arduino en ningún puerto")
        return None
    
    def _test_arduino_communication(self, port_device: str) -> bool:
        """Probar comunicación con Arduino en un puerto específico"""
        try:
            # Intentar conexión
            test_serial = serial.Serial(port_device, Config.USB_BAUDRATE, timeout=2)
            time.sleep(2)  # Esperar reset del Arduino
            
            # Limpiar buffer
            test_serial.flushInput()
            test_serial.flushOutput()
            
            # Enviar comando STATUS (que sabemos que funciona)
            test_serial.write(b'STATUS\n')
            time.sleep(1)
            
            # Leer respuesta
            if test_serial.in_waiting > 0:
                response = test_serial.readline().decode('utf-8').strip()
                test_serial.close()
                
                # Verificar si es una respuesta JSON válida del Arduino
                try:
                    data = json.loads(response)
                    if data.get('device_id') and 'arduino' in str(data.get('device_id')):
                        return True
                except json.JSONDecodeError:
                    pass
            
            test_serial.close()
            return False
            
        except Exception as e:
            logger.debug(f"Puerto {port_device} no disponible: {e}")
            return False

    def detect_usb_arduino(self) -> bool:
        """Detectar Arduino conectado por USB con detección automática"""
        try:
            # Cerrar conexión anterior si existe
            if self.usb_connection and self.usb_connection.is_open:
                self.usb_connection.close()
            
            # Detectar puerto automáticamente
            detected_port = self.auto_detect_arduino_port()
            if not detected_port:
                return False
            
            self.auto_detected_port = detected_port
            
            # Establecer conexión
            self.usb_connection = serial.Serial(
                detected_port, 
                Config.USB_BAUDRATE, 
                timeout=2
            )
            time.sleep(2)  # Esperar reset del Arduino
            
            # Enviar comando de estado para verificar
            self.usb_connection.write(b'STATUS\n')
            time.sleep(1)
            
            if self.usb_connection.in_waiting > 0:
                response = self.usb_connection.readline().decode().strip()
                
                try:
                    data = json.loads(response)
                    if data.get('status') == 'ok':
                        # Registrar dispositivo
                        device_data = {
                            'device_id': data.get('device_id', 'arduino_usb'),
                            'device_type': 'arduino_usb',
                            'name': 'Arduino USB',
                            'port': detected_port,
                            'status': 'online',
                            'metadata': {
                                'baudrate': Config.USB_BAUDRATE,
                                'device_id': data.get('device_id'),
                                'uptime': data.get('uptime')
                            }
                        }
                        
                        self.db_client.register_device(device_data)
                        self.db_client.log_system_event('device_connected', device_data['device_id'], f'Arduino USB conectado en {detected_port}')
                        
                        logger.info(f"✅ Arduino USB detectado y registrado en {detected_port}")
                        return True
                except json.JSONDecodeError:
                    logger.error("❌ Respuesta no válida del Arduino")
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error detectando Arduino USB: {e}")
            if self.usb_connection:
                self.usb_connection.close()
            return False
    
    def read_usb_data(self) -> Optional[Dict[str, Any]]:
        """Leer datos del Arduino USB con manejo robusto de errores"""
        # Verificar conexión y reconectar si es necesario
        reconnection_attempts = 0
        while not self.usb_connection or not self.usb_connection.is_open:
            logger.warning("🔄 Conexión USB perdida, intentando reconectar...")
            if self.detect_usb_arduino():
                logger.info("✅ Reconexión exitosa a %s", self.auto_detected_port)
                break
            else:
                reconnection_attempts += 1
                logger.error(f"❌ No se pudo reconectar (intento {reconnection_attempts})")
                time.sleep(2)
                if reconnection_attempts > 10:
                    logger.critical("❌ No se pudo reconectar después de 10 intentos. Abortando lectura USB.")
                    return None

        try:
            # Verificar si hay datos disponibles
            if self.usb_connection.in_waiting > 0:
                raw_data = self.usb_connection.readline().decode('utf-8').strip()

                if not raw_data:
                    return None

                # Parsear JSON del Arduino
                try:
                    data = json.loads(raw_data)

                    # Verificar que sea datos de sensores
                    if data.get('message_type') == 'sensor_data' and 'sensors' in data:
                        # Procesar datos de sensores
                        sensors = data['sensors']
                        device_id = data.get('device_id', 'arduino_usb')

                        # Insertar cada sensor por separado
                        for sensor_name, value in sensors.items():
                            if sensor_name != 'temperature_avg':  # Evitar duplicar el promedio
                                sensor_data = {
                                    'device_id': device_id,
                                    'sensor_type': sensor_name,
                                    'value': float(value) if isinstance(value, (int, float)) else value,
                                    'unit': self._get_sensor_unit(sensor_name),
                                    'raw_data': data,
                                    'timestamp': datetime.now().isoformat()
                                }
                                self.db_client.insert_sensor_data(sensor_data)

                        logger.debug(f"📊 Datos recibidos: Temp1={sensors.get('temperature_1')}°C, Luz={sensors.get('light_level')}%")
                        return data

                    elif data.get('message_type') == 'command_response':
                        # Log de respuestas a comandos
                        logger.debug(f"📝 Respuesta comando: {data.get('command')} -> {data.get('status')}")
                        return data

                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Datos no JSON recibidos: {raw_data[:100]}...")
                    return None

            return None

        except serial.SerialException as e:
            logger.error(f"❌ Error de conexión serial: {e}")
            # Intentar reconectar en el siguiente ciclo
            if self.usb_connection:
                self.usb_connection.close()
            self.usb_connection = None
            return None

        except Exception as e:
            logger.error(f"❌ Error inesperado leyendo datos USB: {e}")
            return None
    
    def _get_sensor_unit(self, sensor_name: str) -> str:
        """Obtener unidad para un tipo de sensor"""
        unit_map = {
            'temperature_1': '°C',
            'temperature_2': '°C', 
            'temperature_3': '°C',
            'temperature_avg': '°C',
            'light_level': '%',
            'humidity': '%',
            'pressure': 'hPa'
        }
        return unit_map.get(sensor_name, '')
    
    def send_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Enviar comando al Arduino y esperar respuesta"""
        if not self.usb_connection or not self.usb_connection.is_open:
            logger.warning("❌ No hay conexión USB disponible")
            return None
        
        try:
            # Enviar comando
            cmd_bytes = f"{command}\n".encode('utf-8')
            self.usb_connection.write(cmd_bytes)
            logger.debug(f"📤 Comando enviado: {command}")
            
            # Esperar respuesta
            time.sleep(0.5)
            
            if self.usb_connection.in_waiting > 0:
                response = self.usb_connection.readline().decode('utf-8').strip()
                try:
                    data = json.loads(response)
                    logger.debug(f"📥 Respuesta: {data}")
                    return data
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ Respuesta no JSON: {response}")
                    return {'raw_response': response}
            
            logger.warning("⚠️ Sin respuesta al comando")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error enviando comando '{command}': {e}")
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
