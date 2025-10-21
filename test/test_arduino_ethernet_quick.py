#!/usr/bin/env python3
"""
Script de prueba rápida para detectar Arduino Ethernet en IP específica
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.config import Config, get_logger, setup_logging
from backend.postgres_client import PostgreSQLClient
from backend.arduino_detector import ArduinoDetector

# Configurar logging
setup_logging()
logger = get_logger(__name__)

def test_specific_ip():
    print("🔍 PRUEBA ESPECÍFICA DE ARDUINO ETHERNET - IP 192.168.0.110")
    print("=" * 60)
    
    try:
        # Crear cliente de base de datos
        db_client = PostgreSQLClient()
        
        # Crear detector
        print("\n📡 Creando detector Arduino...")
        arduino = ArduinoDetector(db_client)
        
        # Probar IP específica
        ip = "192.168.0.110"
        print(f"\n🌐 Probando Arduino Ethernet en {ip}...")
        
        # Probar si es un Arduino Ethernet
        is_arduino = arduino._test_arduino_ethernet(ip)
        print(f"   ✅ ¿Es Arduino?: {is_arduino}")
        
        if is_arduino:
            # Registrar dispositivo manualmente ANTES de leer datos
            print(f"\n📝 Registrando dispositivo...")
            device_data = {
                'device_id': 'arduino_eth_001',
                'device_type': 'arduino_ethernet',
                'name': f'Arduino Ethernet {ip}',
                'ip_address': ip,
                'port': 80,
                'status': 'online',
                'metadata': {'protocol': 'http'}
            }
            arduino.db_client.register_device(device_data)
            arduino.db_client.log_system_event('device_connected', 'arduino_eth_001', f'Arduino Ethernet detectado en {ip}:80')
            print(f"   ✅ Dispositivo registrado: arduino_eth_001")

            print(f"\n📊 Probando lectura de datos...")
            data = arduino.read_ethernet_data(ip, 80)
            if data:
                print(f"   ✅ Datos recibidos: {data}")
            else:
                print(f"   ❌ No se pudieron leer datos")
        else:
            print(f"   ❌ No es un Arduino Ethernet válido")
        
        print(f"\n🏁 PRUEBA COMPLETADA")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.error(f"Error en prueba: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    test_specific_ip()
