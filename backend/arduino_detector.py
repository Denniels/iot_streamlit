"""
Detección y comunicación con Arduinos (USB y Ethernet)
"""
import serial
import serial.tools.list_ports
import socket
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import time
import subprocess
from backend.config import Config, get_logger
from backend.db_writer import LocalPostgresClient

logger = get_logger(__name__)

class ArduinoDetector:
    def start_dashboard_update(self, dashboard_callback):
        """Inicia la actualización periódica del dashboard con datos USB y Ethernet"""
        import threading
        collected_usb = []
        collected_eth = []
        last_dashboard_send = time.time()

        def update_loop():
            nonlocal last_dashboard_send
            while True:
                # Leer USB
                usb_data = self.read_usb_data()
                if usb_data:
                    collected_usb.append(usb_data)
                # Leer Ethernet (puedes ajustar IP/puerto según tu red)
                eth_devices = self.detect_ethernet_arduinos()
                for dev in eth_devices:
                    ip = dev.get('ip_address')
                    # Normalizar metadata (puede venir como dict o como JSON string)
                    metadata = dev.get('metadata') or {}
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}

                    # Obtener puerto de forma segura (por defecto 80)
                    port = None
                    if isinstance(metadata, dict):
                        port = metadata.get('port')
                    # Coercionar a int y manejar None/valores inválidos
                    try:
                        port = int(port) if port is not None else 80
                    except Exception:
                        port = 80

                    eth_data = self.read_ethernet_data(ip, port)
                    if eth_data:
                        collected_eth.append(eth_data)
                # Enviar al dashboard cada 10 seg
                if dashboard_callback and (time.time() - last_dashboard_send) >= 10:
                    dashboard_callback({
                        'usb': collected_usb,
                        'ethernet': collected_eth
                    })
                    collected_usb.clear()
                    collected_eth.clear()
                    last_dashboard_send = time.time()
                time.sleep(5)

        t = threading.Thread(target=update_loop, daemon=True)
        t.start()
        self.logger.info("⏳ Actualización periódica de dashboard iniciada (USB y Ethernet)")
    def run_periodic_usb_reader(self, dashboard_callback=None):
        """Lee datos del Arduino cada 5 seg y envía al dashboard cada 10 seg (por lotes)"""
        import threading
        collected_data = []
        last_dashboard_send = time.time()

        def reader_loop():
            nonlocal last_dashboard_send
            while True:
                data = self.read_usb_data()
                if data:
                    collected_data.append(data)
                # Enviar al dashboard cada 10 seg
                if dashboard_callback and (time.time() - last_dashboard_send) >= 10:
                    if collected_data:
                        dashboard_callback(collected_data)
                        collected_data.clear()
                    last_dashboard_send = time.time()
                time.sleep(5)

        t = threading.Thread(target=reader_loop, daemon=True)
        t.start()
        self.logger.info("⏳ Lectura periódica USB iniciada (cada 5s, envío dashboard cada 10s)")
    """Detector y comunicador para Arduinos USB y Ethernet"""
    
    def __init__(self, db_client: LocalPostgresClient):
        self.db_client = db_client
        self.logger = logger  # Usar el logger del módulo
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
            test_serial = serial.Serial(port_device, Config.USB_BAUDRATE, timeout=2)
            time.sleep(2)  # Esperar reset del Arduino

            test_serial.flushInput()
            test_serial.flushOutput()

            test_serial.write(b'STATUS\n')
            time.sleep(2)  # Espera extendida

            # Intentar leer varias veces si no hay datos
            response = None
            for _ in range(3):
                if test_serial.in_waiting > 0:
                    response = test_serial.readline().decode('utf-8').strip()
                    break
                time.sleep(1)

            test_serial.close()

            if response:
                logger.debug(f"Respuesta cruda Arduino: {response}")
                try:
                    data = json.loads(response)
                    # Aceptar si tiene status ok o device_id
                    if (data.get('status') == 'ok' or
                        (data.get('device_id') and 'arduino' in str(data.get('device_id')))):
                        return True
                except json.JSONDecodeError:
                    logger.warning(f"Respuesta no JSON: {response}")
                    # Aceptar si contiene 'ok' o 'arduino' en texto
                    if 'ok' in response.lower() or 'arduino' in response.lower():
                        return True
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
            time.sleep(5)  # Espera extendida

            # Intentar leer varias veces si no hay datos
            response = None
            for _ in range(3):
                if self.usb_connection.in_waiting > 0:
                    response = self.usb_connection.readline().decode().strip()
                    break
                time.sleep(1)

            if response:
                logger.debug(f"Respuesta cruda Arduino: {response}")
                try:
                    data = json.loads(response)
                    # Aceptar si status es ok, o si message_type es command_response y status ok
                    if (data.get('status') == 'ok' or
                        (data.get('message_type') == 'command_response' and data.get('status') == 'ok') or
                        (data.get('device_id') and 'arduino' in str(data.get('device_id')))):
                        device_data = {
                            'device_id': data.get('device_id', 'arduino_usb'),
                            'device_type': 'arduino_usb',
                            'name': 'Arduino USB',
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
                    logger.warning(f"Respuesta no JSON: {response}")
                    if 'ok' in response.lower() or 'arduino' in response.lower():
                        device_data = {
                            'device_id': 'arduino_usb',
                            'device_type': 'arduino_usb',
                            'name': 'Arduino USB',
                            'status': 'online',
                            'metadata': {
                                'baudrate': Config.USB_BAUDRATE
                            }
                        }
                        self.db_client.register_device(device_data)
                        self.db_client.log_system_event('device_connected', device_data['device_id'], f'Arduino USB conectado en {detected_port}')
                        logger.info(f"✅ Arduino USB detectado y registrado en {detected_port}")
                        return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Error detectando Arduino USB: {e}")
            if self.usb_connection:
                self.usb_connection.close()
            return False
    
    def read_usb_data(self) -> Optional[Dict[str, Any]]:
        """Leer datos del Arduino USB con manejo robusto de errores"""
        # Verificar conexión
        if not self.usb_connection or not self.usb_connection.is_open:
            logger.warning("🔄 Conexión USB perdida, intentando reconectar...")
            if self.detect_usb_arduino():
                logger.info("✅ Reconexión exitosa")
            else:
                logger.error("❌ No se pudo reconectar")
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

                    # Verificar que sea datos de sensores (acepta ambos message_type)
                    if data.get('message_type') in ('sensor_data', 'sensor_data_clean',) and 'sensors' in data:
                        # Procesar datos de sensores
                        sensors = data['sensors']
                        device_id = data.get('device_id', 'arduino_usb')

                        # Insertar cada sensor por separado
                        for sensor_name, value in sensors.items():
                            sensor_data_clean = {
                                'device_id': device_id,
                                'sensor_type': sensor_name,
                                'value': float(value) if isinstance(value, (int, float)) else value,
                                'unit': self._get_sensor_unit(sensor_name),
                                'raw_data': data,
                                'timestamp': datetime.now(timezone.utc).isoformat()  # Siempre UTC ISO8601
                            }
                            self.db_client.insert_sensor_data(sensor_data_clean)

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
            # Intentar reconectar
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
    
    def _get_esp32_sensor_unit(self, sensor_name: str) -> str:
        """Obtener unidad para sensores ESP32"""
        unit_map = {
            'ntc_entrada': '°C',
            'ntc_salida': '°C', 
            'ldr': '%'
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
    
    def detect_esp32_wifi(self, network_range: str = "192.168.0") -> List[Dict]:
        """Detectar ESP32 conectados por WiFi"""
        detected = []
        
        try:
            # Escanear red en busca de ESP32 WiFi
            import requests
            
            for i in range(1, 255):
                ip = f"{network_range}.{i}"
                
                try:
                    # Probar endpoint /data específico del ESP32
                    response = requests.get(f'http://{ip}/data', timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Verificar que es un ESP32 con sensores
                        if (data.get('device_id') and 'esp32' in str(data.get('device_id')).lower() and
                            'sensors' in data):
                            
                            device_id = data.get('device_id')
                            
                            device_data = {
                                'device_id': device_id,
                                'device_type': 'esp32_wifi',
                                'name': f'ESP32 WiFi {ip}',
                                'ip_address': ip,  # Guardar IP correctamente
                                'port': 80,       # Guardar puerto
                                'status': 'online',
                                'metadata': {'protocol': 'http', 'port': 80, 'ip': ip}
                            }
                            
                            self.db_client.register_device(device_data)
                            self.db_client.log_system_event('device_connected', device_id, f'ESP32 WiFi detectado en {ip}')
                            
                            detected.append(device_data)
                            logger.info(f"✅ ESP32 WiFi detectado: {device_id} en {ip}")
                
                except Exception:
                    continue
            
            return detected
            
        except Exception as e:
            logger.error(f"Error escaneando ESP32 WiFi: {e}")
            return []
    
    def read_esp32_data(self, ip: str) -> Optional[Dict[str, Any]]:
        """Leer datos específicos de ESP32 WiFi"""
        try:
            import requests
            
            response = requests.get(f'http://{ip}/data', timeout=3)
            if response.status_code == 200:
                data = response.json()
                
                if data and 'sensors' in data:
                    device_id = data.get('device_id', f"esp32_wifi_{ip.replace('.', '_')}")
                    
                    # Insertar cada sensor por separado
                    for sensor_name, value in data['sensors'].items():
                        sensor_data_clean = {
                            'device_id': device_id,
                            'sensor_type': sensor_name,
                            'value': value,
                            'unit': self._get_esp32_sensor_unit(sensor_name),
                            'raw_data': data,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        
                        self.db_client.insert_sensor_data(sensor_data_clean)
                    
                    logger.debug(f"📊 Datos ESP32: {data['sensors']}")
                    return data
                    
        except Exception as e:
            logger.error(f"Error leyendo datos ESP32 {ip}: {e}")
            return None
    
    def detect_ethernet_arduinos(self, network_range: str = "192.168.0") -> List[Dict]:
        detected = []
        
        try:
            # Construir lista de IPs a omitir: ESP32 ya conocidos
            try:
                known_devices = self.db_client.get_devices()
                known_esp32_ips = set()
                for d in known_devices:
                    if d.get('device_type') == 'esp32_wifi' and d.get('ip_address'):
                        ip_str = str(d.get('ip_address'))
                        # Normalizar posible formato INET con /32
                        if '/' in ip_str:
                            ip_str = ip_str.split('/', 1)[0]
                        known_esp32_ips.add(ip_str)
            except Exception:
                known_esp32_ips = set()

            # Escanear puertos comunes para Arduinos con Ethernet Shield
            common_ports = [80, 8080, 23, 1883]  # HTTP, HTTP-alt, Telnet, MQTT
            
            for i in range(1, 255):
                ip = f"{network_range}.{i}"

                # Omitir IPs que sabemos que son ESP32
                if ip in known_esp32_ips:
                    continue
                
                for port in common_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        # Normalizar puerto por si viene como string/None en metadata
                        try:
                            scan_port = int(port)
                        except Exception:
                            scan_port = 80

                        result = sock.connect_ex((ip, scan_port))
                        
                        if result == 0:
                            # Solo probar Arduino Ethernet en puerto 80 (HTTP)
                            # Usar scan_port coherente para la prueba
                            if scan_port == 80 and self._test_arduino_ethernet(ip, port=scan_port):
                                # Obtener el device_id real del Arduino
                                import requests
                                try:
                                    response = requests.get(f'http://{ip}/data', timeout=3)
                                    if response.status_code == 200:
                                        data = response.json()
                                        device_id = data.get('device_id', f"arduino_ethernet_{ip.replace('.', '_')}")
                                        # Si en realidad es un ESP32, omitir registro como Arduino Ethernet
                                        dev_id_lower = str(device_id).lower()
                                        if 'esp32' in dev_id_lower or data.get('device_type') == 'esp32_wifi':
                                            self.logger.debug(f"Omitiendo {ip}: identificado como ESP32 ({device_id})")
                                            sock.close()
                                            continue
                                    else:
                                        device_id = f"arduino_ethernet_{ip.replace('.', '_')}"
                                except:
                                    device_id = f"arduino_ethernet_{ip.replace('.', '_')}"
                                
                                    # intentar obtener MAC del host e incluirla en metadata si está disponible
                                    mac = None
                                    try:
                                        mac = self._get_mac_for_ip(ip)
                                    except Exception:
                                        mac = None

                                    metadata = {'protocol': 'http', 'port': scan_port}
                                    if mac:
                                        metadata['mac'] = mac

                                    device_data = {
                                        'device_id': device_id,
                                        'device_type': 'arduino_ethernet',
                                        'name': f'Arduino Ethernet {ip}',
                                        'ip_address': ip,
                                        'status': 'online',
                                        'metadata': metadata
                                    }
                                
                                self.db_client.register_device(device_data)
                                self.db_client.log_system_event('device_connected', device_id, f'Arduino Ethernet detectado en {ip}:{port}')
                                
                                detected.append(device_data)
                                self.logger.info(f"✅ Arduino Ethernet detectado: {device_id} en {ip}:{port}")
                        
                        sock.close()
                        
                    except Exception as e:
                        if sock:
                            sock.close()
                        continue
            
            return detected
            
        except Exception as e:
            logger.error(f"Error escaneando Arduinos Ethernet: {e}")
            return []
    
    def read_ethernet_data(self, ip: str, port: Optional[int], device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Leer datos de Arduino Ethernet"""
        try:
            # Normalizar puerto entrante (acepta None o strings)
            try:
                port = int(port) if port is not None else 80
            except Exception:
                port = 80

            # Para puerto 80, usar HTTP
            if port == 80:
                import requests
                try:
                    # Usar la ruta correcta /data
                    response = requests.get(f'http://{ip}/data', timeout=3)
                    if response.status_code == 200:
                        data = response.json()

                        if data and 'sensors' in data:
                            reported_id = data.get('device_id', f"arduino_ethernet_{ip.replace('.', '_')}")

                            # Si se proporcionó un device_id esperado, comprobar que coincide
                            if device_id and reported_id != device_id:
                                # Caso: en esta IP hay otro dispositivo (p.ej. ESP32) distinto al esperado
                                self.logger.warning(f"ID mismatch en {ip}:{port}: esperado '{device_id}' pero respuesta indica '{reported_id}'")

                                # Registrar el dispositivo encontrado (reported_id) con su IP
                                try:
                                    reported_type = 'esp32_wifi' if 'esp32' in str(reported_id).lower() or data.get('device_type') == 'esp32_wifi' else 'arduino_ethernet'
                                    self.db_client.register_device({
                                        'device_id': reported_id,
                                        'device_type': reported_type,
                                        'name': f"{reported_type} {ip}",
                                                'ip_address': ip,
                                                'port': port,
                                                'status': 'online',
                                                'metadata': {'protocol': 'http', 'port': port, 'ip': ip, 'mac': self._get_mac_for_ip(ip)}
                                    })
                                    self.db_client.log_system_event('device_discovered_at_unexpected_ip', reported_id, f'Found at {ip}:{port} while looking for {device_id}')
                                except Exception as e:
                                    self.logger.error(f"Error registrando dispositivo reportado {reported_id}: {e}")

                                # Intentar localizar el dispositivo esperado en la red
                                try:
                                    found = self.find_device_on_network(device_id)
                                except Exception as e:
                                    self.logger.error(f"Error buscando {device_id} en la red tras mismatch: {e}")
                                    found = None

                                if found:
                                    new_ip = found.get('ip')
                                    new_port = int(found.get('port') or 80)
                                    # Actualizar DB para el device esperado
                                    try:
                                        self.db_client.register_device({
                                            'device_id': device_id,
                                            'device_type': 'arduino_ethernet',
                                            'name': f'Arduino Ethernet {new_ip}',
                                            'ip_address': new_ip,
                                            'port': new_port,
                                            'status': 'online',
                                            'metadata': {'protocol': 'http', 'port': new_port, 'ip': new_ip, 'mac': found.get('mac')}
                                        })
                                        self.db_client.log_system_event('device_reconciled', device_id, f'IP actualizada a {new_ip}:{new_port} tras detectar mismatch en {ip}')
                                    except Exception as e:
                                        self.logger.error(f"Error actualizando BD para {device_id} tras encontrar nueva IP: {e}")

                                    # Reintentar lectura del dispositivo esperado en su nueva IP
                                    try:
                                        return self.read_ethernet_data(new_ip, new_port, device_id=device_id)
                                    except Exception as e:
                                        self.logger.error(f"Error releyendo {device_id} en {new_ip}:{new_port}: {e}")
                                        return None

                                # Si no encontramos el dispositivo esperado, no procesamos los sensores encontrados
                                return None

                            # Si coincide o no hay device_id esperado, procesar normalmente
                            for sensor_name, value in data['sensors'].items():
                                sensor_data_clean = {
                                    'device_id': reported_id,
                                    'sensor_type': sensor_name,
                                    'value': value,
                                    'unit': '°C' if 'temperature' in sensor_name else '',
                                    'raw_data': data,
                                    'timestamp': datetime.now(timezone.utc).isoformat()  # Siempre UTC ISO8601
                                }
                                self.db_client.insert_sensor_data(sensor_data_clean)

                            return data

                except Exception as e:
                    self.logger.error(f"Error HTTP leyendo datos Ethernet {ip}: {e}")
                    # En caso de fallo, permitir que el llamador (DataAcquisition) gestione reconciliación por throttle
                    return None

            # Para otros puertos, usar socket TCP
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
                    derived_id = f"arduino_eth_{ip}_{port}"
                    sensor_data_clean = {
                        'device_id': derived_id,
                        'sensor_type': data.get('sensor_type', 'unknown'),
                        'value': data.get('value'),
                        'unit': data.get('unit', ''),
                        'raw_data': data,
                        'timestamp': datetime.now(timezone.utc).isoformat()  # Siempre UTC ISO8601
                    }

                    self.db_client.insert_sensor_data(sensor_data_clean)
                    return data

            return None

        except Exception as e:
            logger.error(f"Error leyendo datos Ethernet {ip}:{port}: {e}")
            return None
    
    def _test_arduino_ethernet(self, ip: str, port: Optional[int] = 80) -> bool:
        """Probar si hay un Arduino Ethernet en la IP especificada"""
        try:
            import requests

            # Probar el endpoint correcto /data
            # Normalizar puerto
            try:
                port = int(port) if port is not None else 80
            except Exception:
                port = 80

            url = f"http://{ip}:{port}/data" if port != 80 else f"http://{ip}/data"
            try:
                response = requests.get(url, timeout=3)
            except requests.exceptions.ReadTimeout as e:
                # No elevar a error para evitar ruido al escanear IPs que no responden rápido
                self.logger.debug(f"Timeout probando Arduino Ethernet en {ip}:{port} - {e}")
                return False
            except requests.exceptions.ConnectionError as e:
                self.logger.debug(f"Conexión fallida probando Arduino Ethernet en {ip}:{port} - {e}")
                return False

            if response.status_code == 200:
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return False

                # Si responde un ESP32, no es Arduino Ethernet
                dev_id = str(data.get('device_id', '')).lower()
                if 'esp32' in dev_id or data.get('device_type') == 'esp32_wifi':
                    self.logger.debug(f"{ip}:{port} responde como ESP32 ({data.get('device_id')}); se omite como Arduino Ethernet")
                    return False

                # Verificar que es un Arduino con sensores
                # Aceptar si explícitamente marca device_type, o si tiene sensor_data válido
                if (data.get('device_type') == 'arduino_ethernet' and 'sensors' in data and 'device_id' in data):
                    self.logger.info(f"✅ Arduino Ethernet encontrado en {ip}:{port}: {data.get('device_id')}")
                    return True

                # Si firmware no incluye device_type pero devuelve message_type sensor_data válido, aceptarlo
                if (data.get('message_type') in ('sensor_data', 'sensor_data_clean') and 'sensors' in data and 'device_id' in data and 'arduino' in str(data.get('device_id','')).lower()):
                    self.logger.info(f"✅ Arduino Ethernet (sin device_type) aceptado en {ip}:{port}: {data.get('device_id')}")
                    return True

            return False
        except Exception as e:
            # Registrar y devolver False en caso de cualquier excepción para evitar crashes
            msg = str(e)
            if 'Read timed out' in msg or 'Max retries exceeded' in msg:
                self.logger.debug(f"Timeout/conexión al probar Arduino Ethernet en {ip}:{port} - {e}")
            else:
                try:
                    self.logger.error(f"Error probando Arduino Ethernet en {ip}:{port} - {e}")
                except Exception:
                    logger.error(f"Error probando Arduino Ethernet en {ip}:{port} - {e}")
            return False

    def find_device_on_network(self, device_id: str, network_range: str = "192.168.0") -> Optional[Dict[str, Any]]:
        """Buscar en la red un dispositivo que responda con el mismo device_id.

        Devuelve un dict {'ip': ip, 'port': port, 'data': data} si lo encuentra, o None.
        Esta función intenta los puertos HTTP más comunes y solicita /data.
        """
        logger.info(f"🔎 Buscando {device_id} en la red {network_range}.x")
        try:
            import requests

            common_ports = [80, 8080, 8000, 1883]

            for i in range(1, 255):
                ip = f"{network_range}.{i}"

                for port in common_ports:
                    try:
                        # Construir URL según puerto
                        if port == 80:
                            url = f'http://{ip}/data'
                        else:
                            url = f'http://{ip}:{port}/data'

                        resp = requests.get(url, timeout=2)
                        if resp.status_code == 200:
                            try:
                                data = resp.json()
                            except Exception:
                                continue

                            if data and data.get('device_id') == device_id:
                                # intentar incluir MAC si está en la tabla ARP
                                try:
                                    mac = self._get_mac_for_ip(ip)
                                except Exception:
                                    mac = None

                                logger.info(f"🔁 Dispositivo {device_id} encontrado en {ip}:{port}")
                                return {'ip': ip, 'port': port, 'data': data, 'mac': mac}

                    except Exception:
                        # Silenciar errores y continuar
                        continue

            logger.info(f"❌ No se encontró {device_id} en la subred {network_range}.x")
            return None

        except Exception as e:
            logger.error(f"Error buscando dispositivo en la red: {e}")
            return None
    
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

    def _get_mac_for_ip(self, ip: str) -> Optional[str]:
        """Intentar obtener la MAC asociada a una IP local usando /proc/net/arp o 'ip neigh'.

        Devuelve la MAC en formato XX:XX:XX:XX:XX:XX o None si no se encuentra.
        """
        try:
            # Intentar leer /proc/net/arp (Linux)
            with open('/proc/net/arp', 'r') as f:
                lines = f.readlines()
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[0].strip() == ip:
                    hw = parts[3].strip()
                    if hw and hw != '00:00:00:00:00:00':
                        return hw
        except Exception:
            pass

        try:
            # fallback a 'ip neigh' comando
            out = subprocess.check_output(['ip', 'neigh', 'show', ip], stderr=subprocess.DEVNULL, text=True)
            # ejemplo: '192.168.0.101 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE'
            parts = out.split()
            if 'lladdr' in parts:
                idx = parts.index('lladdr')
                if idx + 1 < len(parts):
                    mac = parts[idx + 1]
                    if mac and mac != '00:00:00:00:00:00':
                        return mac
        except Exception:
            pass

        return None
