#!/usr/bin/env python3
"""
Script de adquisición de datos desde Arduino USB y guardado en PostgreSQL local
"""
import json
import sys
import time
from datetime import datetime, timezone
from backend.arduino_detector import ArduinoDetector
from backend.postgres_client import PostgreSQLClient
from backend.config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def main():
    logger.info("Iniciando adquisición de datos de Arduino USB y Ethernet (estrategia robusta)...")
    db_client = PostgreSQLClient()
    import serial
    import serial.tools.list_ports
    from backend.arduino_detector import ArduinoDetector

    # --- Adquisición USB ---
    ports = serial.tools.list_ports.comports()
    arduino_port = None
    for port in ports:
        if (port.vid == 0x2341 or 'arduino' in port.description.lower() or 'uno' in port.description.lower() or 'acm' in port.device.lower()):
            arduino_port = port.device
            logger.info(f"Puerto Arduino USB detectado: {arduino_port} - {port.description}")
            break
    if not arduino_port:
        logger.error("No se encontró Arduino USB")
        print("No se encontró Arduino USB")
    else:
        try:
            ser = serial.Serial(arduino_port, 9600, timeout=2)
            time.sleep(2)
            logger.info(f"Conexión serial abierta en {arduino_port}")
            ser.flushInput()
            ser.flushOutput()

            # Registrar dispositivo USB
            device_id = "arduino_usb_001"
            device_data = {
                'device_id': device_id,
                'device_type': 'arduino_usb',
                'metadata': {'baudrate': 9600, 'port': arduino_port}
            }
            query = """
                INSERT INTO devices (device_id, device_type, metadata, last_seen)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (device_id) DO UPDATE SET
                    device_type = EXCLUDED.device_type,
                    metadata = EXCLUDED.metadata,
                    last_seen = EXCLUDED.last_seen
            """
            params = (
                device_data['device_id'],
                device_data['device_type'],
                json.dumps(device_data['metadata']),
                datetime.now(timezone.utc).isoformat()
            )
            db_client.execute_query(query, params)
            logger.info(f"Dispositivo USB registrado/actualizado: {device_id}")

            print(f"Adquiriendo datos del Arduino USB en {arduino_port}... (Ctrl+C para detener)")
        except Exception as e:
            logger.error(f"No se pudo abrir el puerto serial: {e}")
            print(f"No se pudo abrir el puerto serial: {e}")
            ser = None

    # --- Adquisición Ethernet ---
    ethernet_devices = []
    try:
        detector = ArduinoDetector()
        ethernet_devices = detector.detect_ethernet_arduinos(network_range="192.168.0")
        if ethernet_devices:
            print(f"Dispositivos Ethernet detectados: {len(ethernet_devices)}")
            for dev in ethernet_devices:
                print(f"  - {dev['device_id']} en {dev['ip_address']}:{dev['metadata']['port']}")
        else:
            print("No se detectaron Arduinos Ethernet en la red.")
    except Exception as e:
        logger.error(f"Error detectando Arduinos Ethernet: {e}")

    print("Adquiriendo datos... (Ctrl+C para detener)")
    try:
        while True:
            # USB
            if arduino_port and ser:
                try:
                    if ser.in_waiting > 0:
                        line = ser.readline().decode('utf-8').strip()
                        if line:
                            logger.info(f"[USB][RAW] {line}")
                            try:
                                data = json.loads(line)
                                if data.get('message_type') in ('sensor_data', 'sensor_data_clean') and 'sensors' in data:
                                    sensors = data['sensors']
                                    for sensor_name, value in sensors.items():
                                        if sensor_name != 'temperature_avg':
                                            sensor_data = {
                                                'device_id': device_id,
                                                'sensor_type': sensor_name,
                                                'value': float(value) if isinstance(value, (int, float)) else value,
                                                'unit': '°C' if 'temperature' in sensor_name else '%',
                                                'raw_data': data,
                                                'timestamp': datetime.now(timezone.utc).isoformat()
                                            }
                                            logger.info(f"[USB][INSERT] {json.dumps(sensor_data, default=str)}")
                                            query = """
                                                INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp, created_at)
                                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                                            """
                                            params = (
                                                sensor_data['device_id'],
                                                sensor_data['sensor_type'],
                                                sensor_data['value'],
                                                sensor_data['unit'],
                                                json.dumps(sensor_data['raw_data']),
                                                sensor_data['timestamp'],
                                                datetime.now(timezone.utc).isoformat()
                                            )
                                            db_client.execute_query(query, params)
                                            print(f"USB {sensor_name}: {value}{sensor_data['unit']}")
                            except Exception as e:
                                logger.warning(f"[USB][JSON] Error parseando línea: {e}")
                except Exception as e:
                    logger.warning(f"[USB][READ] Error leyendo línea: {e}")
            # Ethernet
            if ethernet_devices:
                for dev in ethernet_devices:
                    try:
                        detector = ArduinoDetector()
                        eth_data = detector.read_ethernet_data(dev['ip_address'], dev['metadata']['port'])
                        logger.info(f"[ETH] Datos crudos recibidos: {json.dumps(eth_data, default=str)}")
                        if eth_data and eth_data.get('message_type') == 'sensor_data':
                            sensors = eth_data.get('sensors', {})
                            for sensor_name, value in sensors.items():
                                if sensor_name != 'temperature_avg':
                                    sensor_data = {
                                        'device_id': dev['device_id'],
                                        'sensor_type': sensor_name,
                                        'value': float(value) if isinstance(value, (int, float)) else value,
                                        'unit': '°C' if 'temperature' in sensor_name else '%',
                                        'raw_data': eth_data,
                                        'timestamp': datetime.now(timezone.utc).isoformat()
                                    }
                                    logger.info(f"[ETH][INSERT] {json.dumps(sensor_data, default=str)}")
                                    query = """
                                        INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp, created_at)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    """
                                    params = (
                                        sensor_data['device_id'],
                                        sensor_data['sensor_type'],
                                        sensor_data['value'],
                                        sensor_data['unit'],
                                        json.dumps(sensor_data['raw_data']),
                                        sensor_data['timestamp'],
                                        datetime.now(timezone.utc).isoformat()
                                    )
                                    db_client.execute_query(query, params)
                                    print(f"ETH {sensor_name}: {value}{sensor_data['unit']}")
                    except Exception as e:
                        logger.warning(f"[ETH][READ] Error leyendo datos de Ethernet: {e}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nAdquisición detenida por el usuario.")
        logger.info("Adquisición detenida por el usuario.")
    except Exception as e:
        logger.error(f"Error en la adquisición: {e}")
        print(f"Error en la adquisición: {e}")
        sys.exit(1)
    finally:
        if 'ser' in locals() and ser:
            ser.close()
            logger.info("Conexión serial USB cerrada")
