#!/usr/bin/env python3
"""
Prueba FINAL - Verificar que la corrección NTC funciona correctamente
"""

import serial
import json
import time

def test_final_correction():
    print("=== PRUEBA FINAL - CORRECCIÓN NTC ===")
    
    try:
        arduino = serial.Serial('/dev/ttyACM0', 9600, timeout=2)
        time.sleep(3)
        
        print("✅ Arduino conectado")
        print("\n🧪 INSTRUCCIONES DE PRUEBA:")
        print("   1. Observa las temperaturas iniciales (ambiente)")
        print("   2. Toca UN sensor con el dedo (debería SUBIR la temperatura)")
        print("   3. Retira el dedo (debería BAJAR la temperatura)")
        print("\n" + "="*60)
        
        start_time = time.time()
        last_temps = {'temp1': None, 'temp2': None, 'temp3': None}
        
        while time.time() - start_time < 20:
            if arduino.in_waiting > 0:
                try:
                    line = arduino.readline().decode('utf-8').strip()
                    if line:
                        data = json.loads(line)
                        
                        if data.get('message_type') == 'sensor_data':
                            sensors = data.get('sensors', {})
                            debug = data.get('debug', {})
                            
                            temp1 = sensors.get('temperature_1', 0)
                            temp2 = sensors.get('temperature_2', 0) 
                            temp3 = sensors.get('temperature_3', 0)
                            
                            # Detectar cambios
                            changes = []
                            if last_temps['temp1'] is not None:
                                change1 = temp1 - last_temps['temp1']
                                if abs(change1) > 0.5:
                                    direction = "⬆️ SUBE" if change1 > 0 else "⬇️ BAJA"
                                    changes.append(f"NTC1 {direction} ({change1:+.1f}°C)")
                            
                            if last_temps['temp2'] is not None:
                                change2 = temp2 - last_temps['temp2']
                                if abs(change2) > 0.5:
                                    direction = "⬆️ SUBE" if change2 > 0 else "⬇️ BAJA"
                                    changes.append(f"NTC2 {direction} ({change2:+.1f}°C)")
                            
                            if last_temps['temp3'] is not None:
                                change3 = temp3 - last_temps['temp3']
                                if abs(change3) > 0.5:
                                    direction = "⬆️ SUBE" if change3 > 0 else "⬇️ BAJA"
                                    changes.append(f"NTC3 {direction} ({change3:+.1f}°C)")
                            
                            print(f"🌡️  NTC1: {temp1:.1f}°C | NTC2: {temp2:.1f}°C | NTC3: {temp3:.1f}°C | Luz: {sensors.get('light_level', 0)}%")
                            
                            if changes:
                                print(f"📈 CAMBIOS: {' | '.join(changes)}")
                            
                            last_temps = {'temp1': temp1, 'temp2': temp2, 'temp3': temp3}
                            
                        elif data.get('message_type') == 'init':
                            print(f"🚀 Arduino iniciado: Firmware {data.get('firmware_version')}")
                            print(f"🔧 Corrección: {data.get('correction')}")
                            print("-" * 60)
                            
                except Exception as e:
                    continue
            
            time.sleep(0.5)
        
        arduino.close()
        
        print("\n" + "="*60)
        print("✅ PRUEBA COMPLETADA")
        print("\n🎯 RESULTADOS ESPERADOS:")
        print("   ✅ Al tocar sensor → Temperatura SUBE")
        print("   ✅ Al retirar dedo → Temperatura BAJA")
        print("   ❌ Si pasa lo contrario → Aún hay problema")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_final_correction()
