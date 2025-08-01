#!/usr/bin/env python3
"""
Test para verificar cálculos de sensores del Arduino USB
3 NTC + 1 LDR
"""

import math

# Constantes para NTC
SERIES_RESISTOR = 10000.0  # 10kΩ
B_COEFFICIENT = 3950.0     # Coeficiente B típico para NTC 10kΩ
NOMINAL_RESISTANCE = 10000.0  # Resistencia a 25°C
NOMINAL_TEMPERATURE = 25.0 + 273.15  # 25°C en Kelvin

def calculate_ntc_temperature_corrected(adc_value):
    """
    Cálculo CORREGIDO para NTC en configuración: 5V--NTC--A0--R(10kΩ)--GND
    """
    if adc_value <= 0:
        return -999
    
    # Voltaje en el pin analógico
    voltage = (adc_value / 1023.0) * 5.0
    
    # Resistencia del NTC usando divisor de voltaje CORREGIDO
    # En esta configuración: V_pin = 5V * R_series / (R_ntc + R_series)
    # Despejando R_ntc: R_ntc = R_series * (5V - V_pin) / V_pin
    if voltage >= 5.0:
        return -999
    
    ntc_resistance = SERIES_RESISTOR * (5.0 - voltage) / voltage
    
    # Ecuación de Steinhart-Hart simplificada
    steinhart = math.log(ntc_resistance / NOMINAL_RESISTANCE) / B_COEFFICIENT
    steinhart += 1.0 / NOMINAL_TEMPERATURE
    temperature_kelvin = 1.0 / steinhart
    temperature_celsius = temperature_kelvin - 273.15
    
    return temperature_celsius

def calculate_ldr_percentage(adc_value):
    """
    Cálculo para LDR: convertir ADC a porcentaje de luz
    Asumiendo: 5V--LDR--A3--R(10kΩ)--GND
    """
    # LDR: más luz = menos resistencia = más voltaje en pin
    # ADC alto = mucha luz
    percentage = (adc_value / 1023.0) * 100.0
    return percentage

def test_all_sensors():
    """Test completo de los 4 sensores del Arduino USB"""
    print("🔬 TEST COMPLETO - Arduino USB (3 NTC + 1 LDR)")
    print("=" * 60)
    
    # Test scenarios para NTC
    test_cases_ntc = [
        ("Sensor caliente (taza caliente)", 100),
        ("Temperatura ambiente", 400),
        ("Sensor frío (hielo)", 900)
    ]
    
    print("\n📡 SENSORES NTC (A0, A1, A2):")
    print("-" * 40)
    for description, adc in test_cases_ntc:
        temp = calculate_ntc_temperature_corrected(adc)
        print(f"{description:25} | ADC: {adc:3d} | Temp: {temp:6.1f}°C")
    
    # Test scenarios para LDR
    test_cases_ldr = [
        ("Oscuridad total", 100),
        ("Luz ambiente", 400),
        ("Luz directa", 900)
    ]
    
    print("\n💡 SENSOR LDR (A3):")
    print("-" * 40)
    for description, adc in test_cases_ldr:
        light = calculate_ldr_percentage(adc)
        print(f"{description:25} | ADC: {adc:3d} | Luz: {light:5.1f}%")
    
    print("\n🎯 CÓDIGO ARDUINO CORREGIDO:")
    print("-" * 40)
    print("// Para NTC (A0, A1, A2):")
    print("float resistance = SERIES_RESISTOR * (5.0 - voltage) / voltage;")
    print("\n// Para LDR (A3):")
    print("int lightPercentage = (analogRead(LDR_PIN) * 100) / 1023;")

if __name__ == "__main__":
    test_all_sensors()
