#!/usr/bin/env python3
"""
Script de prueba para detectar Arduino Ethernet específicamente
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

def main():
    print("🔍 PRUEBA ESPECÍFICA DE DETECCIÓN ARDUINO ETHERNET")
    print("=" * 60)
    
    try:
        # Crear cliente de base de datos
        db_client = PostgreSQLClient()
        
        # Crear detector
        print("\n📡 Creando detector Arduino...")
        arduino = ArduinoDetector(db_client)
        
        # Detectar Arduino Ethernet específicamente
        print("\n🌐 Detectando Arduino Ethernet en red 192.168.0...")
        print("   (Esto puede tomar 1-2 minutos)")
        
        ethernet_devices = arduino.detect_ethernet_arduinos(network_range="192.168.0")
        
        print(f"\n✅ RESULTADO: {len(ethernet_devices)} dispositivos encontrados")
        
        if ethernet_devices:
            for i, dev in enumerate(ethernet_devices, 1):
                print(f"\n📱 DISPOSITIVO {i}:")
                print(f"   • device_id: {dev['device_id']}")
                print(f"   • device_type: {dev['device_type']}")
                print(f"   • ip_address: {dev['ip_address']}")
                print(f"   • status: {dev['status']}")
                print(f"   • metadata: {dev['metadata']}")
                
                # Probar lectura de datos
                print(f"\n📊 Probando lectura de datos de {dev['ip_address']}...")
                data = arduino.read_ethernet_data(dev['ip_address'], dev['metadata']['port'])
                if data:
                    print(f"   ✅ Datos recibidos: {data}")
                else:
                    print(f"   ❌ No se pudieron leer datos")
        else:
            print("\n❌ No se detectaron Arduinos Ethernet")
            print("\n🔍 DIAGNÓSTICO:")
            print("   1. Verificar que el Arduino Ethernet esté encendido")
            print("   2. Verificar conectividad de red:")
            print("      ping 192.168.0.110")
            print("   3. Verificar servidor HTTP:")
            print("      curl http://192.168.0.110/data")
        
        print(f"\n🏁 PRUEBA COMPLETADA")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        logger.error(f"Error en prueba de detección: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
