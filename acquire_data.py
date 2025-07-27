import time
import os
from arduino_detector import ArduinoDetector
from backend.postgres_client import db_client

CONTROL_FLAG_PATH = "/home/daniel/repos/iot_streamlit/acquisition_control.flag"

def save_to_db(data):
    # Inserta los datos en la tabla sensor_data
    if isinstance(data, list):
        for d in data:
            db_client.insert_sensor_data(d)
    elif isinstance(data, dict):
        db_client.insert_sensor_data(data)

def is_acquisition_enabled():
    try:
        if os.path.exists(CONTROL_FLAG_PATH):
            with open(CONTROL_FLAG_PATH, "r") as f:
                status = f.read().strip().upper()
                return status == "ON"
        return False
    except Exception:
        return False

if __name__ == "__main__":
    detector = ArduinoDetector(db_client)
    # Detectar Arduinos Ethernet (puedes ajustar el rango de red si es necesario)
    network_range = "192.168.1"  # Ajusta según tu red
    while True:
        if is_acquisition_enabled():
            # USB
            usb_data = detector.read_usb_data()
            if usb_data:
                save_to_db(usb_data)
            else:
                print("No se recibieron datos USB.")

            # Ethernet
            arduinos_eth = detector.detect_ethernet_arduinos(network_range)
            for eth in arduinos_eth:
                ip = eth.get("ip")
                port = eth.get("port", 80)
                eth_data = detector.read_ethernet_data(ip, port)
                if eth_data:
                    save_to_db(eth_data)
                else:
                    print(f"No se recibieron datos Ethernet de {ip}:{port}.")
        else:
            print("Adquisición pausada por control externo (dashboard)")
        time.sleep(5)
