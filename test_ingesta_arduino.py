#!/usr/bin/env python3
"""
Prueba de ingesta de datos de Arduino (USB y Ethernet) a la base local y Supabase
"""
from datetime import datetime
from backend.postgres_client import PostgreSQLClient
from backend.db_writer import SupabaseClient
from backend.arduino_detector import ArduinoDetector
from backend.config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

def insert_sensor_data_local(pg_client, sensor_data):
    """Inserta un registro en la base local"""
    query = """
        INSERT INTO sensor_data (device_id, sensor_type, value, unit, raw_data, timestamp, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        sensor_data['device_id'],
        sensor_data['sensor_type'],
        sensor_data['value'],
        sensor_data['unit'],
        str(sensor_data['raw_data']),
        sensor_data['timestamp'],
        datetime.now().isoformat()
    )
    try:
        pg_client.execute_query(query, params)
        logger.info(f"Dato insertado en base local: {sensor_data['device_id']} - {sensor_data['sensor_type']}")
        return True
    except Exception as e:
        logger.error(f"Error insertando en base local: {e}")
        return False

def main():
    print("\n🔧 PRUEBA DE INGESTA DE DATOS DE ARDUINO")
    pg_client = PostgreSQLClient()
    supabase_client = SupabaseClient()
    arduino_detector = ArduinoDetector(supabase_client)  # Usamos Supabase solo para registrar dispositivos

    # 1. Detectar y leer datos del Arduino USB (robusto y monitoreo continuo)
    print("\n📡 Leyendo datos de Arduino USB (robusto y monitoreo continuo)...")
    if arduino_detector.detect_usb_arduino():
        ser = arduino_detector.usb_connection
        if not ser or not ser.is_open:
            print("❌ No se pudo abrir la conexión USB")
            return

        # Probar varios comandos
        test_commands = [b'STATUS\n', b'READ_NOW\n', b'ping\n', b'\n']
        found_data = False
        for cmd in test_commands:
            print(f"📤 Enviando: {cmd.decode().strip()}")
            ser.write(cmd)
            time.sleep(1)
            start_time = time.time()
            while time.time() - start_time < 3:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        if line:
                            print(f"📥 Recibido: {line}")
                            try:
                                data = json.loads(line)
                                if data.get('message_type') == 'sensor_data' and 'sensors' in data:
                                    sensors = data['sensors']
                                    for sensor_name, value in sensors.items():
                                        if sensor_name != 'temperature_avg':
                                            sensor_data = {
                                                'device_id': data.get('device_id', 'arduino_usb'),
                                                'sensor_type': sensor_name,
                                                'value': float(value),
                                                'unit': '°C' if 'temperature' in sensor_name else '%',
                                                'raw_data': data,
                                                'timestamp': datetime.now().isoformat()
                                            }
                                            insert_sensor_data_local(pg_client, sensor_data)
                                            supabase_client.insert_sensor_data(sensor_data)
                                            print(f"✅ USB: {sensor_name} = {value}{sensor_data['unit']}")
                                            found_data = True
                            except Exception as e:
                                print(f"📝 Texto plano: {line}")
                    except Exception as e:
                        print(f"❌ Error leyendo: {e}")
                time.sleep(0.1)
            print("─" * 50)
        # Monitoreo continuo por 10 segundos
        print("🔄 Monitoreando datos automáticos por 10 segundos...")
        start_time = time.time()
        while time.time() - start_time < 10:
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        print(f"[{timestamp}] 📥 {line}")
                        try:
                            data = json.loads(line)
                            if data.get('message_type') == 'sensor_data' and 'sensors' in data:
                                sensors = data['sensors']
                                for sensor_name, value in sensors.items():
                                    if sensor_name != 'temperature_avg':
                                        sensor_data = {
                                            'device_id': data.get('device_id', 'arduino_usb'),
                                            'sensor_type': sensor_name,
                                            'value': float(value),
                                            'unit': '°C' if 'temperature' in sensor_name else '%',
                                            'raw_data': data,
                                            'timestamp': datetime.now().isoformat()
                                        }
                                        insert_sensor_data_local(pg_client, sensor_data)
                                        supabase_client.insert_sensor_data(sensor_data)
                                        print(f"✅ USB: {sensor_name} = {value}{sensor_data['unit']}")
                                        found_data = True
                        except Exception as e:
                            print(f"📝 Texto plano: {line}")
                except Exception as e:
                    print(f"❌ Error procesando datos: {e}")
            time.sleep(0.1)
        if not found_data:
            print("⚠️ No se recibieron datos válidos del Arduino USB")
        ser.close()
    else:
        print("❌ No se detectó Arduino USB")

    # 2. Detectar y leer datos de Arduinos Ethernet
    print("\n🌐 Leyendo datos de Arduinos Ethernet...")
    ethernet_devices = supabase_client.get_devices()
    ethernet_devices = [d for d in ethernet_devices if d.get('device_type') == 'arduino_ethernet']
    for device in ethernet_devices:
        ip = device.get('ip_address')
        port = device.get('port')
        if ip and port:
            data = arduino_detector.read_ethernet_data(ip, port)
            if data and data.get('message_type') == 'sensor_data':
                sensors = data['sensors']
                for sensor_name, value in sensors.items():
                    if sensor_name != 'temperature_avg':
                        sensor_data = {
                            'device_id': device['device_id'],
                            'sensor_type': sensor_name,
                            'value': float(value),
                            'unit': '°C' if 'temperature' in sensor_name else '%',
                            'raw_data': data,
                            'timestamp': datetime.now().isoformat()
                        }
                        # Insertar en base local
                        insert_sensor_data_local(pg_client, sensor_data)
                        # Insertar en Supabase
                        supabase_client.insert_sensor_data(sensor_data)
                        print(f"✅ ETH: {sensor_name} = {value}{sensor_data['unit']} ({ip}:{port})")
            else:
                print(f"⚠️ No se recibieron datos válidos de {device['device_id']} ({ip}:{port})")
        else:
            print(f"⚠️ Dispositivo Ethernet sin IP/puerto válido: {device}")

    print("\n🎉 Prueba de ingesta finalizada. Revisa la base local y Supabase para verificar los datos.")

if __name__ == "__main__":
    main()
