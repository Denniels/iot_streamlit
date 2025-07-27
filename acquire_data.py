#!/usr/bin/env python3
"""
Script de adquisición de datos desde Arduino USB y guardado en PostgreSQL local
"""
import json
import sys
import time
from datetime import datetime
from backend.arduino_detector import ArduinoDetector
from backend.postgres_client import PostgreSQLClient
from backend.config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def main():
    logger.info("Iniciando adquisición de datos desde Arduino USB...")
    db_client = PostgreSQLClient()
    # Usamos un mock para la inserción directa en la base local
    class LocalDB:
        def insert_sensor_data(self, data):
            # Insertar en la tabla sensor_data
            query = """
                INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            params = (
                data.get('device_id'),
                data.get('sensor_type'),
                data.get('value'),
                data.get('unit'),
                json.dumps(data.get('raw_data')),
                data.get('timestamp'),
                datetime.now().isoformat()
            )
            db_client.execute_query(query, params)
            logger.info(f"Dato insertado: {data.get('device_id')} {data.get('sensor_type')}={data.get('value')}{data.get('unit')}")

        def register_device(self, device_data):
            # Mock: solo loguea el registro
            logger.info(f"Dispositivo registrado: {device_data}")

        def log_system_event(self, event_type, device_id, message):
            # Mock: solo loguea el evento
            logger.info(f"Evento sistema: {event_type} - {device_id} - {message}")
    
    arduino = ArduinoDetector(LocalDB())
    # Detectar Arduino USB
    usb_ok = False
    try:
        usb_ok = arduino.detect_usb_arduino()
    except AttributeError:
        # Si el método no existe, intentar detect_usb_arduino()
        if hasattr(arduino, 'detect_usb_arduino'):
            usb_ok = arduino.detect_usb_arduino()
        else:
            logger.error("No se pudo detectar Arduino USB: método no encontrado")
            print("No se pudo detectar Arduino USB: método no encontrado")
    if not usb_ok:
        logger.error("No se pudo detectar Arduino USB")
        print("No se pudo detectar Arduino USB")
    else:
        print(f"Arduino USB detectado en: {arduino.auto_detected_port}")
        logger.info(f"Arduino USB detectado en: {arduino.auto_detected_port}")

    # Detectar Arduino Ethernet
    print("Buscando Arduino Ethernet en la red...")
    ethernet_devices = arduino.detect_ethernet_arduinos(network_range="192.168.0")
    if ethernet_devices:
        print(f"Dispositivos Ethernet detectados: {len(ethernet_devices)}")
        for dev in ethernet_devices:
            print(f"  - {dev['device_id']} en {dev['ip_address']}:{dev['metadata']['port']}")
    else:
        print("No se detectaron Arduinos Ethernet en la red.")

    # Adquisición continua
    print("Adquiriendo datos... (Ctrl+C para detener)")
    try:
        while True:
            # USB
            if usb_ok:
                data = arduino.read_usb_data()
                if data and data.get('message_type') == 'sensor_data':
                    sensors = data.get('sensors', {})
                    for sensor_name, value in sensors.items():
                        if sensor_name != 'temperature_avg':
                            sensor_data = {
                                'device_id': data.get('device_id', 'arduino_usb'),
                                'sensor_type': sensor_name,
                                'value': float(value) if isinstance(value, (int, float)) else value,
                                'unit': arduino._get_sensor_unit(sensor_name),
                                'raw_data': data,
                                'timestamp': datetime.now().isoformat()
                            }
                            arduino.db_client.insert_sensor_data(sensor_data)
                            print(f"USB {sensor_name}: {value}{arduino._get_sensor_unit(sensor_name)}")
            # Ethernet
            if ethernet_devices:
                for dev in ethernet_devices:
                    ip = dev['ip_address']
                    port = dev['metadata']['port']
                    eth_data = arduino.read_ethernet_data(ip, port)
                    if eth_data and eth_data.get('message_type') == 'sensor_data':
                        sensors = eth_data.get('sensors', {})
                        for sensor_name, value in sensors.items():
                            if sensor_name != 'temperature_avg':
                                sensor_data = {
                                    'device_id': dev['device_id'],
                                    'sensor_type': sensor_name,
                                    'value': float(value) if isinstance(value, (int, float)) else value,
                                    'unit': arduino._get_sensor_unit(sensor_name),
                                    'raw_data': eth_data,
                                    'timestamp': datetime.now().isoformat()
                                }
                                arduino.db_client.insert_sensor_data(sensor_data)
                                print(f"ETH {sensor_name}: {value}{arduino._get_sensor_unit(sensor_name)}")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nAdquisición detenida por el usuario.")
        logger.info("Adquisición detenida por el usuario.")
    except Exception as e:
        logger.error(f"Error en la adquisición: {e}")
        print(f"Error en la adquisición: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
