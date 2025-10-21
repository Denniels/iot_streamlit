#!/usr/bin/env python3
"""
Script de prueba para validar los cálculos de temperatura NTC
"""
import math

# Constantes del Arduino (mismo valores)
SERIES_RESISTOR = 10000.0  # 10kΩ
NOMINAL_RESISTANCE = 10000.0  # 10kΩ
NOMINAL_TEMPERATURE = 25.0  # 25°C
B_COEFFICIENT = 3950.0

def calculate_temperature_old(adc_value):
    """Cálculo anterior (incorrecto para nuestra configuración)"""
    if adc_value <= 0 or adc_value >= 1023:
        return None
    
    # Fórmula anterior
    resistance = SERIES_RESISTOR * ((1023.0 / adc_value) - 1.0)
    
    # Steinhart-Hart
    steinhart = resistance / NOMINAL_RESISTANCE
    steinhart = math.log(steinhart)
    steinhart /= B_COEFFICIENT
    steinhart += 1.0 / (NOMINAL_TEMPERATURE + 273.15)
    steinhart = 1.0 / steinhart
    steinhart -= 273.15
    
    return steinhart, resistance

def calculate_temperature_new(adc_value):
    """Cálculo nuevo (correcto para configuración 5V--NTC--A0--R--GND)"""
    if adc_value <= 0 or adc_value >= 1023:
        return None
    
    # Fórmula corregida
    resistance = SERIES_RESISTOR * (adc_value / (1023.0 - adc_value))
    
    # Steinhart-Hart
    steinhart = resistance / NOMINAL_RESISTANCE
    steinhart = math.log(steinhart)
    steinhart /= B_COEFFICIENT
    steinhart += 1.0 / (NOMINAL_TEMPERATURE + 273.15)
    steinhart = 1.0 / steinhart
    steinhart -= 273.15
    
    return steinhart, resistance

def main():
    print("🧪 Prueba de cálculos de temperatura NTC")
    print("=" * 50)
    print(f"Configuración: 5V--NTC(10kΩ)--A0--R(10kΩ)--GND")
    print(f"B coefficient: {B_COEFFICIENT}")
    print()
    
    # Casos de prueba
    test_cases = [
        (100, "Muy frío"),
        (300, "Frío"),
        (500, "Ambiente"),
        (700, "Caliente"),
        (900, "Muy caliente")
    ]
    
    print("ADC\t| Método Anterior\t\t| Método Corregido")
    print("----\t| ---------------\t\t| ----------------")
    
    for adc, description in test_cases:
        old_result = calculate_temperature_old(adc)
        new_result = calculate_temperature_new(adc)
        
        if old_result and new_result:
            old_temp, old_res = old_result
            new_temp, new_res = new_result
            print(f"{adc}\t| {old_temp:.1f}°C ({old_res:.0f}Ω)\t| {new_temp:.1f}°C ({new_res:.0f}Ω) - {description}")
    
    print()
    print("🔍 Análisis:")
    print("- Con NTC en la parte superior del divisor:")
    print("  • ADC alto → Resistencia NTC baja → Temperatura ALTA")
    print("  • ADC bajo → Resistencia NTC alta → Temperatura BAJA")
    print()
    print("- Comportamiento esperado al calentar el sensor:")
    print("  • Temperatura ↑ → Resistencia NTC ↓ → Voltaje A0 ↑ → ADC ↑")

if __name__ == "__main__":
    main()
