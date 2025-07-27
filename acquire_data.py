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
    if not arduino.detect_usb_arduino():
        logger.error("No se pudo detectar Arduino USB")
        print("No se pudo detectar Arduino USB")
        sys.exit(1)
    print(f"Arduino detectado en: {arduino.auto_detected_port}")
    logger.info(f"Arduino detectado en: {arduino.auto_detected_port}")
    
    # Adquisición continua
    print("Adquiriendo datos... (Ctrl+C para detener)")
    try:
        while True:
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
                        print(f"{sensor_name}: {value}{arduino._get_sensor_unit(sensor_name)}")
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
