#!/usr/bin/env python3
"""
Script de prueba para verificar la conexión mejorada con Arduino
"""

import sys
import time
import json
from datetime import datetime
from backend.config import Config, get_logger, setup_logging
from backend.db_writer import SupabaseClient
from backend.arduino_detector import ArduinoDetector

# Configurar logging
setup_logging()
logger = get_logger(__name__)

def test_arduino_connection():
    """Probar la conexión mejorada con Arduino"""
    print("🔧 PRUEBA DE CONEXIÓN ARDUINO MEJORADA")
    print("=" * 50)
    
    try:
        # Crear cliente de base de datos (mock para prueba)
        class MockDB:
            def register_device(self, data):
                print(f"✅ Dispositivo registrado: {data['device_id']}")
            
            def log_system_event(self, event_type, device_id, message):
                print(f"📝 Evento: {event_type} - {device_id} - {message}")
            
            def insert_sensor_data(self, data):
                sensor_type = data['sensor_type']
                value = data['value']
                unit = data['unit']
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"📊 [{timestamp}] {sensor_type}: {value}{unit}")
        
        # Crear detector con mock DB
        db_client = MockDB()
        detector = ArduinoDetector(db_client)
        
        # 1. Probar detección automática
        print("\n🔍 1. DETECCIÓN AUTOMÁTICA DEL PUERTO")
        print("-" * 40)
        
        if detector.detect_usb_arduino():
            print(f"✅ Arduino detectado en: {detector.auto_detected_port}")
        else:
            print("❌ No se pudo detectar Arduino")
            return False
        
        # 2. Probar comandos
        print("\n📤 2. PRUEBA DE COMANDOS")
        print("-" * 40)
        
        commands = ['STATUS', 'READ_NOW']
        for cmd in commands:
            print(f"\nEnviando comando: {cmd}")
            response = detector.send_command(cmd)
            if response:
                print(f"✅ Respuesta: {response}")
            else:
                print("⚠️ Sin respuesta")
        
        # 3. Monitorear datos automáticos por 15 segundos
        print("\n🔄 3. MONITOREO DE DATOS AUTOMÁTICOS (15 segundos)")
        print("-" * 40)
        
        start_time = time.time()
        data_count = 0
        
        while time.time() - start_time < 15:
            data = detector.read_usb_data()
            if data:
                data_count += 1
                if data.get('message_type') == 'sensor_data':
                    sensors = data.get('sensors', {})
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}] 🌡️ T1:{sensors.get('temperature_1')}°C T2:{sensors.get('temperature_2')}°C T3:{sensors.get('temperature_3')}°C 💡:{sensors.get('light_level')}%")
            
            time.sleep(0.1)
        
        # 4. Resumen
        print("\n📊 4. RESUMEN DE LA PRUEBA")
        print("-" * 40)
        print(f"Puerto detectado: {detector.auto_detected_port}")
        print(f"Datos recibidos: {data_count}")
        print(f"Frecuencia: {data_count/15:.1f} datos/segundo")
        
        if data_count > 0:
            print("✅ ¡CONEXIÓN FUNCIONANDO CORRECTAMENTE!")
            return True
        else:
            print("❌ No se recibieron datos automáticos")
            return False
            
    except Exception as e:
        print(f"❌ Error en la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cerrar conexión
        if hasattr(detector, 'usb_connection') and detector.usb_connection:
            detector.usb_connection.close()
            print("\n🔌 Conexión cerrada")

def main():
    """Función principal"""
    success = test_arduino_connection()
    
    if success:
        print("\n🎉 PRUEBA EXITOSA - El Arduino está funcionando correctamente")
        print("\n💡 RECOMENDACIONES:")
        print("1. La aplicación ahora debería funcionar sin problemas")
        print("2. Se detecta automáticamente el puerto correcto")
        print("3. Hay reconexión automática si se pierde la conexión")
        print("4. Los datos se procesan en formato JSON correctamente")
    else:
        print("\n🔧 NECESITA ATENCIÓN:")
        print("1. Verificar que el Arduino esté programado correctamente")
        print("2. Comprobar la conexión USB")
        print("3. Revisar el código del Arduino")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
