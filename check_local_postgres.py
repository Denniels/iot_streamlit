from backend.postgres_client import db_client

# Consulta los últimos 10 datos de sensores
sensor_data = db_client.get_recent_sensor_data(limit=10)

if sensor_data:
    print("Datos recientes de sensores:")
    for row in sensor_data:
        print(row)
else:
    print("No se encontraron datos de sensores en la base de datos local.")
