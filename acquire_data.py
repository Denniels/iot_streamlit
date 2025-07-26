import time
from arduino_detector import get_sensor_data  # Debes implementar esta función
from backend.postgres_client import db_client

def save_to_db(data):
    # Inserta los datos en la tabla sensor_data
    db_client.insert_sensor_data(data)

if __name__ == "__main__":
    # Adquisición de datos de Arduino
    data = get_sensor_data()  # Debes adaptar esta función a tu hardware
    if data:
        save_to_db(data)
    else:
        print("No se recibieron datos del sensor.")
