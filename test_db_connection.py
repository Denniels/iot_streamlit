from backend.postgres_client import db_client

# Probar registro de dispositivo
device_data = {
    'device_id': 'test_device_002',
    'device_type': 'arduino_usb',
    'name': 'Arduino USB de Prueba',
    'ip_address': None,
    'port': None,
    'status': 'active',
    'metadata': {'connection_type': 'USB', 'port': '/dev/ttyACM0'}
}
result_device = db_client.register_device(device_data)
print("Registro de dispositivo:", "OK" if result_device else "FALLÓ")

# Probar inserción de datos de sensor
sensor_data = {
    'device_id': 'test_device_002',
    'sensor_type': 'temperature',
    'value': 25.5,
    'unit': '°C',
    'raw_data': {'source': 'test_script'}
}
result_sensor = db_client.insert_sensor_data(sensor_data)
print("Inserción de sensor:", "OK" if result_sensor else "FALLÓ")
