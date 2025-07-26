#!/usr/bin/env python3
"""
API IoT Local compatible con PostgreSQL
Recibe datos de Arduino via USB y Ethernet, los almacena en PostgreSQL
"""
import json
import threading
import time
import serial
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify, render_template_string
import logging
from backend.postgres_client import db_client

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración
API_PORT = 8000
NETWORK_SCAN_RANGE = '192.168.0.0/24'
ARDUINO_USB_BAUDRATE = 9600

# Variables globales
arduino_usb = None
arduino_ethernet_ips = []
app = Flask(__name__)

# --- Funciones de acceso a datos usando PostgreSQL ---
def register_device(device_data: Dict[str, Any]) -> bool:
    return db_client.register_device(device_data)

def insert_sensor_data(sensor_data: Dict[str, Any]) -> bool:
    return db_client.insert_sensor_data(sensor_data)

def log_system_event(event_type: str, device_id: str = None, message: str = None, metadata: Dict = None) -> bool:
    return db_client.log_system_event(event_type, device_id, message, metadata)

def get_devices(status: str = None) -> List[Dict]:
    return db_client.get_devices(status)

def get_recent_sensor_data(device_id: str = None, limit: int = 100) -> List[Dict]:
    return db_client.get_recent_sensor_data(device_id, limit)

def find_arduino_usb_port():
    """Encontrar puerto USB del Arduino automáticamente"""
    import serial.tools.list_ports
    logger.info("🔍 Buscando puertos Arduino USB...")
    ports = serial.tools.list_ports.comports()
    for port in ports:
        # Buscar Arduino por VID/PID o descripción
        if (getattr(port, 'vid', None) == 0x2341 or  # Arduino VID
            'arduino' in port.description.lower() or
            'uno' in port.description.lower() or
            'acm' in port.device.lower()):
            try:
                test_serial = serial.Serial(port.device, ARDUINO_USB_BAUDRATE, timeout=2)
                test_serial.close()
                logger.info(f"🔍 Puerto USB encontrado: {port.device} - {port.description}")
                return port.device
            except Exception as e:
                logger.warning(f"⚠️ Error probando puerto {port.device}: {e}")
                continue
    logger.warning("⚠️ No se encontró puerto USB para Arduino")
    return None

def scan_arduino_ethernet():
    """Escanear red para encontrar Arduino Ethernet"""
    logger.info("🔍 Escaneando red para Arduino Ethernet...")
    found_devices = []
    
    # IPs conocidas y comunes para Arduino Ethernet
    test_ips = [
        '192.168.0.110',  # IP encontrada por el escáner
        '192.168.0.177',  # IP común de Arduino Ethernet
        '192.168.0.50',
        '192.168.0.100',
        '192.168.0.200',
        '192.168.0.10',
        '192.168.0.20',
        '192.168.0.30',
        '192.168.0.40',
        '192.168.0.60',
        '192.168.0.70',
        '192.168.0.80',
        '192.168.0.90'
    ]
    
    logger.info(f"🔍 Probando {len(test_ips)} IPs para Arduino Ethernet...")
    
    for ip in test_ips:
        try:
            # Probar múltiples endpoints del Arduino
            endpoints = ['/', '/data', '/sensor', '/status']
            arduino_found = False
            
            for endpoint in endpoints:
                try:
                    url = f'http://{ip}{endpoint}'
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        logger.info(f"✅ Arduino Ethernet encontrado en {ip}{endpoint}")
                        logger.info(f"📄 Respuesta: {response.text[:100]}...")
                        found_devices.append(ip)
                        arduino_found = True
                        
                        # Registrar dispositivo Ethernet
                        device_data = {
                            'device_id': f'arduino_ethernet_{ip.replace(".", "_")}',
                            'device_type': 'arduino_ethernet',
                            'name': f'Arduino Ethernet {ip}',
                            'ip_address': ip,
                            'port': 80,
                            'status': 'active',
                            'metadata': {'connection_type': 'Ethernet', 'ip': ip, 'endpoint': endpoint}
                        }
                        db_client.register_device(device_data)
                        break
                        
                except Exception as e:
                    continue
            
            if arduino_found:
                break
                
        except Exception as e:
            continue
    
    return found_devices

def init_arduino_usb():
    """Inicializar conexión Arduino USB"""
    global arduino_usb
    
    # Encontrar puerto automáticamente
    usb_port = find_arduino_usb_port()
    if not usb_port:
        logger.error("❌ No se encontró Arduino USB")
        return False
    
    try:
        arduino_usb = serial.Serial(usb_port, ARDUINO_USB_BAUDRATE, timeout=1)
        logger.info(f"✅ Arduino USB conectado en {usb_port}")
        
        # Registrar dispositivo USB
        device_data = {
            'device_id': 'arduino_usb_001',
            'device_type': 'arduino_usb',
            'name': 'Arduino USB Principal',
            'ip_address': None,
            'port': None,
            'status': 'active',
            'metadata': {'connection_type': 'USB', 'port': usb_port}
        }
        db_client.register_device(device_data)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error conectando Arduino USB: {e}")
        return False

def read_arduino_usb():
    """Leer datos del Arduino USB"""
    global arduino_usb
    while True:
        try:
            if arduino_usb and arduino_usb.is_open:
                line = arduino_usb.readline().decode('utf-8').strip()
                if line:
                    logger.info(f"📡 USB recibido: {line}")
                    
                    # Intentar parsear como JSON
                    try:
                        data = json.loads(line)
                        
                        # Procesar formato complejo del Arduino con múltiples sensores
                        if 'message_type' in data and data['message_type'] == 'sensor_data':
                            device_id = data.get('device_id', 'arduino_usb_001')
                            sensors_data = data.get('sensors', {})
                            
                            # Insertar cada sensor por separado
                            for sensor_name, sensor_value in sensors_data.items():
                                # Solo procesar valores válidos (no -999 o -1)
                                if sensor_value is not None and sensor_value != -999 and sensor_value != -1:
                                    # Determinar unidad según el tipo de sensor
                                    unit = ""
                                    if 'temperature' in sensor_name.lower():
                                        unit = "°C"
                                    elif 'light' in sensor_name.lower():
                                        unit = "lux"
                                    elif 'humidity' in sensor_name.lower():
                                        unit = "%"
                                    
                                    sensor_data = {
                                        'device_id': device_id,
                                        'sensor_type': sensor_name.lower(),
                                        'value': float(sensor_value),
                                        'unit': unit,
                                        'raw_data': {
                                            'original_message': data,
                                            'source': 'usb',
                                            'arduino_timestamp': data.get('timestamp', None)
                                        }
                                    }
                                    
                                    # Insertar en base de datos
                                    success = db_client.insert_sensor_data(sensor_data)
                                    if success:
                                        logger.info(f"✅ Sensor guardado: {sensor_name} = {sensor_value} {unit}")
                                    else:
                                        logger.error(f"❌ Error guardando sensor: {sensor_name}")
                        
                        # Formato simple (legacy)
                        elif 'sensor_type' in data and 'value' in data:
                            data['device_id'] = data.get('device_id', 'arduino_usb_001')
                            db_client.insert_sensor_data(data)
                            
                    except json.JSONDecodeError:
                        # Si no es JSON, intentar parsear formato simple
                        if ':' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                sensor_type = parts[0].strip()
                                value_unit = parts[1].strip()
                                
                                # Extraer valor y unidad
                                import re
                                match = re.match(r'([\d.-]+)\s*(.*)', value_unit)
                                if match:
                                    value = float(match.group(1))
                                    unit = match.group(2).strip()
                                    
                                    sensor_data = {
                                        'device_id': 'arduino_usb_001',
                                        'sensor_type': sensor_type.lower(),
                                        'value': value,
                                        'unit': unit,
                                        'raw_data': {'original_line': line, 'source': 'usb'}
                                    }
                                    db_client.insert_sensor_data(sensor_data)
            
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"❌ Error leyendo Arduino USB: {e}")
            time.sleep(5)
            
def read_arduino_ethernet():
    """Leer datos de Arduino Ethernet via HTTP"""
    global arduino_ethernet_ips
    
    while True:
        for ip in arduino_ethernet_ips:
            try:
                # Solicitar datos al Arduino Ethernet
                response = requests.get(f'http://{ip}/data', timeout=5)
                if response.status_code == 200:
                    try:
                        data = json.loads(response.text)
                        device_id = f'arduino_ethernet_{ip.replace(".", "_")}'
                        
                        # Procesar formato similar al USB con múltiples sensores
                        if 'message_type' in data and data['message_type'] == 'sensor_data':
                            sensors_data = data.get('sensors', {})
                            
                            # Insertar cada sensor por separado
                            for sensor_name, sensor_value in sensors_data.items():
                                # Solo procesar valores válidos (no -999 o -1)
                                if sensor_value is not None and sensor_value != -999 and sensor_value != -1:
                                    # Determinar unidad según el tipo de sensor
                                    unit = ""
                                    if 'temperature' in sensor_name.lower():
                                        unit = "°C"
                                    elif 'light' in sensor_name.lower():
                                        unit = "lux"
                                    elif 'humidity' in sensor_name.lower():
                                        unit = "%"
                                    
                                    sensor_data = {
                                        'device_id': device_id,
                                        'sensor_type': sensor_name.lower(),
                                        'value': float(sensor_value),
                                        'unit': unit,
                                        'raw_data': {
                                            'original_message': data,
                                            'source': 'ethernet',
                                            'ip_address': ip,
                                            'arduino_timestamp': data.get('timestamp', None)
                                        }
                                    }
                                    
                                    # Insertar en base de datos
                                    success = db_client.insert_sensor_data(sensor_data)
                                    if success:
                                        logger.info(f"✅ Ethernet sensor guardado: {sensor_name} = {sensor_value} {unit} ({ip})")
                                    else:
                                        logger.error(f"❌ Error guardando Ethernet sensor: {sensor_name}")
                        
                        # Formato simple (legacy)
                        elif 'sensor_type' in data and 'value' in data:
                            data['device_id'] = device_id
                            db_client.insert_sensor_data(data)
                            
                        logger.info(f"📡 Ethernet {ip} procesado: {len(data.get('sensors', {}))} sensores")
                        
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Respuesta no JSON de {ip}: {response.text[:100]}...")
                        
            except Exception as e:
                logger.debug(f"❌ Error leyendo Arduino Ethernet {ip}: {e}")
        
        time.sleep(10)  # Leer cada 10 segundos para Ethernet

# Rutas de la API
@app.route('/')
def index():
    """Página principal con interfaz web"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>IoT Dashboard - Jetson Nano</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .stat { background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }
            .devices, .data { margin-top: 20px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            .refresh { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
            .refresh:hover { background: #0056b3; }
        </style>
        <script>
            function refreshData() {
                location.reload();
            }
        </script>
    </head>
    <body>
        <div class="container">
            <div class="card header">
                <h1>🚀 IoT Dashboard - Jetson Nano</h1>
                <p>Sistema de monitoreo en tiempo real para Arduino</p>
            </div>
            
            <div class="card">
                <h2>📊 Estadísticas del Sistema</h2>
                <div class="stats">
                    <div class="stat">
                        <h3 id="device-count">Cargando...</h3>
                        <p>Dispositivos</p>
                    </div>
                    <div class="stat">
                        <h3 id="reading-count">Cargando...</h3>
                        <p>Lecturas</p>
                    </div>
                    <div class="stat">
                        <h3 id="last-reading">Cargando...</h3>
                        <p>Última lectura</p>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📱 Dispositivos Conectados</h2>
                <div id="devices-list">Cargando dispositivos...</div>
            </div>
            
            <div class="card">
                <h2>📈 Últimas Lecturas de Sensores</h2>
                <div id="sensor-data">Cargando datos...</div>
            </div>
            
            <div class="card">
                <button class="refresh" onclick="refreshData()">🔄 Actualizar Datos</button>
            </div>
        </div>
        
        <script>
            // Cargar datos al inicio
            fetch('/api/devices')
                .then(response => response.json())
                .then(devices => {
                    document.getElementById('device-count').textContent = devices.length;
                    
                    let html = '<table><tr><th>Device ID</th><th>Tipo</th><th>Nombre</th><th>Estado</th><th>Última actividad</th></tr>';
                    devices.forEach(device => {
                        html += `<tr>
                            <td>${device.device_id}</td>
                            <td>${device.device_type}</td>
                            <td>${device.name || 'N/A'}</td>
                            <td>${device.status}</td>
                            <td>${device.last_seen}</td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('devices-list').innerHTML = html;
                });
            
            fetch('/api/sensor-data?limit=20')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('reading-count').textContent = data.length;
                    
                    if (data.length > 0) {
                        document.getElementById('last-reading').textContent = data[0].timestamp;
                        
                        let html = '<table><tr><th>Device</th><th>Sensor</th><th>Valor</th><th>Unidad</th><th>Timestamp</th></tr>';
                        data.forEach(reading => {
                            html += `<tr>
                                <td>${reading.device_id}</td>
                                <td>${reading.sensor_type}</td>
                                <td>${reading.value}</td>
                                <td>${reading.unit || ''}</td>
                                <td>${reading.timestamp}</td>
                            </tr>`;
                        });
                        html += '</table>';
                        document.getElementById('sensor-data').innerHTML = html;
                    }
                });
        </script>
    </body>
    </html>
    '''
    return html

@app.route('/api/devices', methods=['GET', 'POST'])
def api_devices():
    """API para dispositivos"""
    if request.method == 'POST':
        try:
            device_data = request.get_json()
            if db_client.register_device(device_data):
                return jsonify({'status': 'success', 'message': 'Dispositivo registrado'})
            else:
                return jsonify({'status': 'error', 'message': 'Error registrando dispositivo'}), 500
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    
    else:  # GET
        devices = db_client.get_devices()
        # Filtrar dispositivos de prueba
        devices = [d for d in devices if not (d.get('device_id') == 'test_device_001' or d.get('device_type') == 'test_type')]
        return jsonify(devices)

@app.route('/api/sensor-data', methods=['GET', 'POST'])
def api_sensor_data():
    """API para datos de sensores"""
    if request.method == 'POST':
        try:
            sensor_data = request.get_json()
            
            # Validación básica
            if not all(key in sensor_data for key in ['device_id', 'sensor_type', 'value']):
                return jsonify({'status': 'error', 'message': 'Faltan campos requeridos'}), 400
            
            if db_client.insert_sensor_data(sensor_data):
                return jsonify({'status': 'success', 'message': 'Datos guardados'})
            else:
                return jsonify({'status': 'error', 'message': 'Error guardando datos'}), 500
                
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    
    else:  # GET
        device_id = request.args.get('device_id')
        limit = int(request.args.get('limit', 100))
        
        data = db_client.get_recent_sensor_data(device_id, limit)
        return jsonify(data)

@app.route('/api/stats')
def api_stats():
    """API para estadísticas"""
    try:
        devices = db_client.get_devices()
        recent_data = db_client.get_recent_sensor_data(limit=1)
        
        stats = {
            'total_devices': len(devices),
            'active_devices': len([d for d in devices if d['status'] == 'active']),
            'last_reading': recent_data[0]['timestamp'] if recent_data else None,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def main():
    """Función principal"""
    global arduino_ethernet_ips
    
    logger.info("🚀 Iniciando API IoT Local...")
    logger.info(f"🌐 Puerto API: {API_PORT}")
    
    # Escanear Arduino Ethernet
    arduino_ethernet_ips = scan_arduino_ethernet()
    if arduino_ethernet_ips:
        logger.info(f"✅ Arduino Ethernet encontrados: {arduino_ethernet_ips}")
    
    # Inicializar Arduino USB
    init_arduino_usb()
    
    # Iniciar threads para leer ambos tipos de Arduino
    if arduino_usb:
        usb_thread = threading.Thread(target=read_arduino_usb, daemon=True)
        usb_thread.start()
        logger.info("🔄 Thread Arduino USB iniciado")
    
    if arduino_ethernet_ips:
        ethernet_thread = threading.Thread(target=read_arduino_ethernet, daemon=True)
        ethernet_thread.start()
        logger.info("🔄 Thread Arduino Ethernet iniciado")
    
    # Mostrar información
    logger.info(f"🌐 Documentación disponible en http://localhost:{API_PORT}/docs")
    logger.info(f"📱 Interfaz web en http://localhost:{API_PORT}")
    
    # Iniciar servidor Flask
    try:
        app.run(host='0.0.0.0', port=API_PORT, debug=False)
    except Exception as e:
        logger.error(f"❌ Error en servidor: {e}")

if __name__ == "__main__":
    main()
