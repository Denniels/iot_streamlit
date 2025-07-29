"""
Escáner de red para detectar dispositivos IoT
"""
import socket
import threading
import time
from typing import List, Dict, Any
import netifaces
import subprocess
from concurrent.futures import ThreadPoolExecutor
from backend.config import Config, get_logger
from backend.db_writer import LocalPostgresClient

logger = get_logger(__name__)

class DeviceScanner:
    """Escáner de dispositivos en la red"""
    
    def __init__(self, db_client: LocalPostgresClient):
        self.db_client = db_client
        self.discovered_devices = []
    
    def get_network_range(self) -> str:
        """Obtener el rango de red actual"""
        try:
            # Obtener interfaz de red principal
            gateways = netifaces.gateways()
            default_gateway = gateways['default'][netifaces.AF_INET][1]
            
            # Obtener direcciones de la interfaz
            interface_info = netifaces.ifaddresses(default_gateway)
            ip_info = interface_info[netifaces.AF_INET][0]
            
            ip = ip_info['addr']
            netmask = ip_info['netmask']
            
            # Calcular red base (simplificado para /24)
            ip_parts = ip.split('.')
            return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}"
            
        except Exception as e:
            logger.error(f"Error obteniendo rango de red: {e}")
            return "192.168.1"  # Fallback
    
    def ping_sweep(self, network_range: str) -> List[str]:
        """Realizar ping sweep para encontrar hosts activos"""
        active_hosts = []
        
        def ping_host(ip):
            try:
                # Ping rápido (Windows/Linux compatible)
                result = subprocess.run(
                    ['ping', '-c', '1', '-W', '1', ip] if 
                    subprocess.run(['which', 'ping'], capture_output=True).returncode == 0 
                    else ['ping', '-n', '1', '-w', '1000', ip],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                
                if result.returncode == 0:
                    active_hosts.append(ip)
                    logger.debug(f"Host activo encontrado: {ip}")
            except Exception as e:
                logger.debug(f"Error haciendo ping a {ip}: {e}")
        
        # Usar ThreadPoolExecutor para paralelizar pings
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(1, 255):
                ip = f"{network_range}.{i}"
                futures.append(executor.submit(ping_host, ip))
            
            # Esperar a que terminen todos
            for future in futures:
                try:
                    future.result(timeout=1)
                except:
                    continue
        
        logger.info(f"Ping sweep completado. {len(active_hosts)} hosts activos")
        return active_hosts
    
    def port_scan(self, ip: str, common_ports: List[int] = None) -> List[int]:
        """Escanear puertos comunes en una IP"""
        if common_ports is None:
            # Puertos comunes para dispositivos IoT
            common_ports = [
                22, 23, 80, 443, 502,  # SSH, Telnet, HTTP, HTTPS, Modbus
                1883, 8080, 8883, 9000, 10000,  # MQTT, HTTP-alt, MQTT-S, misc
                21, 25, 53, 110, 143, 993, 995  # FTP, SMTP, DNS, POP3, IMAP
            ]
        
        open_ports = []
        
        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((ip, port))
                
                if result == 0:
                    open_ports.append(port)
                    logger.debug(f"Puerto abierto: {ip}:{port}")
                
                sock.close()
                
            except Exception as e:
                logger.debug(f"Error escaneando {ip}:{port}: {e}")
                continue
        
        return open_ports
    
    def identify_device(self, ip: str, ports: List[int]) -> Dict[str, Any]:
        """Identificar tipo de dispositivo basado en puertos abiertos"""
        device_info = {
            'ip_address': ip,
            'device_type': 'unknown',
            'name': f'Device {ip}',
            'status': 'online',
            'metadata': {'ports': ports}
        }
        
        # Lógica de identificación basada en puertos
        if 502 in ports:
            device_info.update({
                'device_type': 'modbus_device',
                'name': f'Modbus Device {ip}',
                'metadata': {'protocol': 'modbus'}
            })
        elif 80 in ports or 8080 in ports:
            # Intentar identificar si es Arduino con web server
            if self._is_arduino_web_server(ip, 80 if 80 in ports else 8080):
                device_info.update({
                    'device_type': 'arduino_ethernet',
                    'name': f'Arduino Web {ip}',
                    'metadata': {'protocol': 'http'}
                })
            else:
                device_info.update({
                    'device_type': 'web_device',
                    'name': f'Web Device {ip}',
                    'metadata': {'protocol': 'http'}
                })
        elif 1883 in ports:
            device_info.update({
                'device_type': 'mqtt_device',
                'name': f'MQTT Device {ip}',
                'metadata': {'protocol': 'mqtt'}
            })
        elif 22 in ports:
            device_info.update({
                'device_type': 'linux_device',
                'name': f'Linux Device {ip}',
                'metadata': {'protocol': 'ssh'}
            })
        
        return device_info
    
    def _is_arduino_web_server(self, ip: str, port: int) -> bool:
        """Verificar si es un servidor web de Arduino"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((ip, port))
            
            # Enviar petición HTTP básica
            request = b"GET / HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n"
            sock.send(request)
            
            response = sock.recv(1024).decode().lower()
            sock.close()
            
            # Buscar indicadores de Arduino
            arduino_indicators = ['arduino', 'esp8266', 'esp32', 'nodemcu']
            return any(indicator in response for indicator in arduino_indicators)
            
        except:
            return False
    
    def scan_network(self) -> List[Dict[str, Any]]:
        """Escanear toda la red en busca de dispositivos"""
        logger.info("Iniciando escaneo de red...")
        
        network_range = self.get_network_range()
        active_hosts = self.ping_sweep(network_range)
        
        discovered = []
        
        for ip in active_hosts:
            try:
                # Escanear puertos
                open_ports = self.port_scan(ip)
                
                if open_ports:
                    # Identificar dispositivo
                    device_info = self.identify_device(ip, open_ports)
                    device_info['device_id'] = f"net_device_{ip.replace('.', '_')}"
                    
                    # Registrar en base de datos
                    self.db_client.register_device(device_info)
                    self.db_client.log_system_event(
                        'device_discovered', 
                        device_info['device_id'],
                        f"Dispositivo descubierto: {device_info['name']}"
                    )
                    
                    discovered.append(device_info)
                    logger.info(f"Dispositivo registrado: {device_info['name']} ({ip})")
                
            except Exception as e:
                logger.error(f"Error procesando dispositivo {ip}: {e}")
                continue
        
        logger.info(f"Escaneo completado. {len(discovered)} dispositivos encontrados")
        self.discovered_devices = discovered
        return discovered
    
    def continuous_scan(self, interval: int = 300):
        """Escanear red continuamente cada X segundos"""
        logger.info(f"Iniciando escaneo continuo cada {interval} segundos")
        
        while True:
            try:
                self.scan_network()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Escaneo continuo detenido")
                break
            except Exception as e:
                logger.error(f"Error en escaneo continuo: {e}")
                time.sleep(60)  # Esperar 1 minuto antes de reintentar
