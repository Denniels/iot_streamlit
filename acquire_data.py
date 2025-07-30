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
    logger.info("Iniciando adquisición de datos de Arduino USB y Ethernet (clase ArduinoDetector)...")
    from backend.db_writer import LocalPostgresClient
    db_client = LocalPostgresClient()
    detector = ArduinoDetector(db_client)

    # --- Detección y adquisición USB ---
    arduino_usb_ok = detector.detect_usb_arduino()
    if not arduino_usb_ok:
        logger.error("No se encontró Arduino USB")
        print("No se encontró Arduino USB")
    else:
        print("Arduino USB detectado y registrado correctamente.")

    # --- Adquisición Ethernet ---
    ethernet_devices = []
    try:
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
            usb_data = detector.read_usb_data()
            if usb_data:
                print(f"USB: {usb_data}")
            # Ethernet
            if ethernet_devices:
                for dev in ethernet_devices:
                    try:
                        eth_data = detector.read_ethernet_data(dev['ip_address'], dev['metadata']['port'])
                        if eth_data:
                            print(f"ETH: {eth_data}")
                    except Exception as e:
                        logger.warning(f"[ETH][READ] Error leyendo datos de Ethernet: {e}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nAdquisición detenida por el usuario.")
        logger.info("Adquisición detenida por el usuario.")
    except Exception as e:
        logger.error(f"Error en la adquisición: {e}")
        print(f"Error en la adquisición: {e}")
        sys.exit(1)
