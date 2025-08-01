#!/usr/bin/env python3
"""
Script de diagnóstico detallado para identificar el problema con los sensores NTC
"""

import serial
import json
import time
import math

def analyze_ntc_readings():
    print("=== DIAGNÓSTICO DETALLADO NTC ===")
    print("Este script te ayudará a identificar el problema exacto")
    
    # Buscar Arduino
    possible_ports = ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0']
    arduino_port = None
    
    for port in possible_ports:
        try:
            with open(port, 'r'):
                arduino_port = port
                break
        except:
            continue
    
    if not arduino_port:
        print("❌ Arduino no encontrado")
        return
    
    try:
        arduino = serial.Serial(arduino_port, 9600, timeout=2)
        time.sleep(3)
        
        print(f"✅ Conectado a {arduino_port}")
        print("\n🔬 ANÁLISIS EN TIEMPO REAL:")
        print("📋 Instrucciones:")
        print("   1. Deja los sensores al aire libre (temperatura ambiente)")
        print("   2. Luego toca UN SOLO sensor con el dedo")
        print("   3. Observa los valores ADC y temperatura calculada")
        print("\n" + "="*80)
        
        readings = []
        start_time = time.time()
        
        while time.time() - start_time < 30:  # 30 segundos de análisis
            if arduino.in_waiting > 0:
                try:
                    line = arduino.readline().decode('utf-8').strip()
                    if line:
                        data = json.loads(line)
                        
                        if data.get('message_type') == 'sensor_data':
                            sensors = data.get('sensors', {})
                            debug = data.get('debug', {})
                            
                            # Valores actuales
                            adc1 = debug.get('adc_ntc1', 0)
                            adc2 = debug.get('adc_ntc2', 0)
                            adc3 = debug.get('adc_ntc3', 0)
                            temp1 = sensors.get('temperature_1', 0)
                            temp2 = sensors.get('temperature_2', 0)
                            temp3 = sensors.get('temperature_3', 0)
                            
                            # Calcular voltajes
                            v1 = (adc1 / 1023.0) * 5.0
                            v2 = (adc2 / 1023.0) * 5.0
                            v3 = (adc3 / 1023.0) * 5.0
                            
                            # Calcular resistencias con ambas fórmulas
                            # Fórmula actual (corregida): R_ntc = R_series * (5V - V_pin) / V_pin
                            if v1 > 0: r1_current = 10000 * (5.0 - v1) / v1
                            else: r1_current = 0
                            
                            if v2 > 0: r2_current = 10000 * (5.0 - v2) / v2
                            else: r2_current = 0
                            
                            if v3 > 0: r3_current = 10000 * (5.0 - v3) / v3
                            else: r3_current = 0
                            
                            # Fórmula alternativa: R_ntc = R_series * V_pin / (5V - V_pin)
                            if v1 < 5.0: r1_alt = 10000 * v1 / (5.0 - v1)
                            else: r1_alt = 0
                            
                            if v2 < 5.0: r2_alt = 10000 * v2 / (5.0 - v2)
                            else: r2_alt = 0
                            
                            if v3 < 5.0: r3_alt = 10000 * v3 / (5.0 - v3)
                            else: r3_alt = 0
                            
                            print(f"\n⏰ Tiempo: {time.time() - start_time:.1f}s")
                            print(f"📊 NTC1: ADC={adc1:4d} | V={v1:.2f}V | R_actual={r1_current:.0f}Ω | R_alt={r1_alt:.0f}Ω | T={temp1:.1f}°C")
                            print(f"📊 NTC2: ADC={adc2:4d} | V={v2:.2f}V | R_actual={r2_current:.0f}Ω | R_alt={r2_alt:.0f}Ω | T={temp2:.1f}°C")
                            print(f"📊 NTC3: ADC={adc3:4d} | V={v3:.2f}V | R_actual={r3_current:.0f}Ω | R_alt={r3_alt:.0f}Ω | T={temp3:.1f}°C")
                            
                            # Guardar lectura para análisis
                            readings.append({
                                'time': time.time() - start_time,
                                'adc1': adc1, 'adc2': adc2, 'adc3': adc3,
                                'v1': v1, 'v2': v2, 'v3': v3,
                                'temp1': temp1, 'temp2': temp2, 'temp3': temp3
                            })
                            
                except Exception as e:
                    continue
            
            time.sleep(0.5)
        
        arduino.close()
        
        # Análisis de patrones
        print("\n" + "="*80)
        print("🔍 ANÁLISIS DE PATRONES:")
        
        if len(readings) > 5:
            # Comparar primera y última lectura
            first = readings[2]  # Ignorar primeras lecturas
            last = readings[-1]
            
            print(f"\n📈 CAMBIOS DETECTADOS:")
            for i in range(1, 4):
                adc_change = last[f'adc{i}'] - first[f'adc{i}']
                temp_change = last[f'temp{i}'] - first[f'temp{i}']
                
                print(f"   NTC{i}: ADC cambió {adc_change:+d}, Temperatura cambió {temp_change:+.1f}°C")
                
                if abs(adc_change) > 20:  # Cambio significativo
                    if adc_change > 0 and temp_change < 0:
                        print(f"   ❌ NTC{i}: ADC sube pero temperatura baja - PROBLEMA DETECTADO")
                    elif adc_change < 0 and temp_change > 0:
                        print(f"   ❌ NTC{i}: ADC baja pero temperatura sube - PROBLEMA DETECTADO")
                    elif adc_change > 0 and temp_change > 0:
                        print(f"   ✅ NTC{i}: ADC sube y temperatura sube - CORRECTO")
                    elif adc_change < 0 and temp_change < 0:
                        print(f"   ✅ NTC{i}: ADC baja y temperatura baja - CORRECTO")
        
        print(f"\n🎯 CONCLUSIONES:")
        print(f"   - Si al calentar: ADC sube pero temperatura baja → Fórmula incorrecta")
        print(f"   - Si al calentar: ADC baja pero temperatura sube → Fórmula correcta")
        print(f"   - Resistencia NTC nominal: ~10kΩ a 25°C")
        print(f"   - Al calentar NTC: resistencia debe BAJAR")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    analyze_ntc_readings()
