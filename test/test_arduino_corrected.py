#!/usr/bin/env python3
"""
Script para probar el Arduino USB con código corregido
Uso: python test_arduino_corrected.py
"""

import serial
import json
import time
import sys

def test_arduino_usb():
    print("=== PRUEBA ARDUINO USB CORREGIDO ===")
    
    # Buscar puerto Arduino
    possible_ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1']
    arduino_port = None
    
    for port in possible_ports:
        try:
            with open(port, 'r'):
                arduino_port = port
                print(f"✅ Arduino encontrado en: {port}")
                break
        except:
            continue
    
    if not arduino_port:
        print("❌ Arduino no detectado. Asegúrate de que esté conectado.")
        print("Puertos esperados: /dev/ttyACM0, /dev/ttyACM1, /dev/ttyUSB0, /dev/ttyUSB1")
        return
    
    try:
        # Conectar al Arduino
        print(f"🔌 Conectando a {arduino_port}...")
        arduino = serial.Serial(arduino_port, 9600, timeout=2)
        time.sleep(3)  # Esperar inicialización del Arduino
        
        print("📡 Escuchando datos del Arduino por 15 segundos...")
        print("(Tip: Toca los sensores NTC con los dedos para ver cambios)")
        print("-" * 60)
        
        start_time = time.time()
        data_count = 0
        
        while time.time() - start_time < 15:
            if arduino.in_waiting > 0:
                try:
                    line = arduino.readline().decode('utf-8').strip()
                    if line:
                        data = json.loads(line)
                        
                        if data.get('message_type') == 'sensor_data':
                            data_count += 1
                            sensors = data.get('sensors', {})
                            debug = data.get('debug', {})
                            
                            print(f"📊 Lectura #{data_count}:")
                            print(f"  🌡️  NTC1: {sensors.get('temperature_1', 'N/A')}°C")
                            print(f"  🌡️  NTC2: {sensors.get('temperature_2', 'N/A')}°C") 
                            print(f"  🌡️  NTC3: {sensors.get('temperature_3', 'N/A')}°C")
                            print(f"  🌡️  Promedio: {sensors.get('temperature_avg', 'N/A')}°C")
                            print(f"  💡 Luz: {sensors.get('light_level', 'N/A')}%")
                            print(f"  🔧 ADC: NTC1={debug.get('adc_ntc1')}, NTC2={debug.get('adc_ntc2')}, NTC3={debug.get('adc_ntc3')}, LDR={debug.get('adc_ldr')}")
                            print("-" * 40)
                            
                        elif data.get('message_type') == 'init':
                            print(f"🚀 Inicialización: {data.get('device_id')}")
                            print(f"   Firmware: {data.get('firmware_version')}")
                            print(f"   Sensores: {data.get('sensors')}")
                            print(f"   Corrección: {data.get('correction')}")
                            print("-" * 40)
                            
                except json.JSONDecodeError:
                    print(f"📜 Raw data: {line}")
                except Exception as e:
                    print(f"❌ Error procesando línea: {e}")
            
            time.sleep(0.1)
        
        arduino.close()
        
        print("\n" + "=" * 60)
        if data_count > 0:
            print(f"✅ PRUEBA EXITOSA: Recibidas {data_count} lecturas de sensores")
            print("🔥 INSTRUCCIONES PARA VERIFICAR CORRECCIÓN:")
            print("   1. Toca un sensor NTC con el dedo (debería SUBIR la temperatura)")
            print("   2. Sopla aire frío al sensor (debería BAJAR la temperatura)")
            print("   3. Si las temperaturas responden correctamente, ¡la corrección funciona!")
        else:
            print("⚠️  No se recibieron datos de sensores")
            print("   - Verifica que el Arduino esté encendido")
            print("   - Revisa las conexiones de los sensores")
        
    except serial.SerialException as e:
        print(f"❌ Error de comunicación serie: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_arduino_usb()
