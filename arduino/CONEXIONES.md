# Diagramas de Conexión - Sensores Arduino IoT

## Arduino USB - 3 NTC + LDR

### Componentes necesarios:
- Arduino Uno/Nano
- 3x Termistores NTC 10kΩ
- 1x LDR (fotoresistencia)
- 4x Resistencias 10kΩ
- 1x Botón opcional
- Cables de conexión

### Conexiones:

```
Arduino Uno          NTC1 (10kΩ)         Resistor 10kΩ
    5V    ------------- Terminal 1
                        Terminal 2 ------- A0 ------- Resistor ------- GND
    
Arduino Uno          NTC2 (10kΩ)         Resistor 10kΩ  
    5V    ------------- Terminal 1
                        Terminal 2 ------- A1 ------- Resistor ------- GND
                        
Arduino Uno          NTC3 (10kΩ)         Resistor 10kΩ
    5V    ------------- Terminal 1
                        Terminal 2 ------- A2 ------- Resistor ------- GND

Arduino Uno          LDR                  Resistor 10kΩ
    5V    ------------- Terminal 1  
                        Terminal 2 ------- A3 ------- Resistor ------- GND

Arduino Uno          Botón (opcional)
    D2    ------------- Terminal 1
    GND   ------------- Terminal 2 (usar pull-up interno)

    D13   ------------- LED interno (ya conectado)
```

### Esquema visual NTC:
```
     5V
      |
   [NTC 10kΩ]
      |
      +------- A0/A1/A2 (al Arduino)
      |
   [R 10kΩ]
      |
     GND
```

## Arduino Ethernet - 2 NTC

### Componentes necesarios:
- Arduino Uno/Nano/Mega
- Ethernet Shield W5100/W5500
- 2x Termistores NTC 10kΩ  
- 2x Resistencias 10kΩ
- Cable de red
- Cables de conexión

### Conexiones:

```
Arduino + Ethernet Shield    NTC1 (10kΩ)         Resistor 10kΩ
           5V    ------------- Terminal 1
                               Terminal 2 ------- A0 ------- Resistor ------- GND
    
Arduino + Ethernet Shield    NTC2 (10kΩ)         Resistor 10kΩ  
           5V    ------------- Terminal 1
                               Terminal 2 ------- A1 ------- Resistor ------- GND

           D13   ------------- LED interno (ya conectado)
           
Ethernet Shield ------------- Cable de red a router/switch
```

### Pines reservados por Ethernet Shield:
```
D4  - SD Card (reservado)
D10 - SPI CS Ethernet
D11 - SPI MOSI  
D12 - SPI MISO
D13 - SPI SCK + LED
```

## Características de los sensores

### NTC 10kΩ - Especificaciones típicas:
- Resistencia nominal: 10,000Ω a 25°C
- Coeficiente B: 3950K (típico)
- Rango de temperatura: -40°C a +125°C
- Precisión: ±1°C (con calibración)
- Tiempo de respuesta: 5-30 segundos

### Ecuación de conversión NTC:
```
1/T = 1/T₀ + (1/B) * ln(R/R₀)

Donde:
T  = Temperatura en Kelvin
T₀ = 298.15K (25°C)  
R  = Resistencia medida
R₀ = 10,000Ω (resistencia nominal)
B  = 3950K (coeficiente del termistor)
```

### LDR - Fotoresistencia:
- Resistencia en oscuridad: ~10kΩ - 1MΩ
- Resistencia con luz: ~100Ω - 10kΩ  
- Tiempo de respuesta: 20-30ms (luz a oscuridad)
- Sensibilidad: 400-700nm (luz visible)

## Calibración y ajustes

### Para mayor precisión NTC:
1. **Medir resistencia real** del NTC a temperatura conocida (ej: 25°C)
2. **Ajustar constantes** en el código si es necesario:
   ```cpp
   const float NOMINAL_RESISTANCE = 10000.0; // Ajustar si es diferente
   const float B_COEFFICIENT = 3950.0;       // Medir o consultar datasheet
   ```

### Para calibrar LDR:
1. **Luz máxima**: Apuntar lámpara directamente → anotar valor ADC
2. **Oscuridad total**: Tapar completamente → anotar valor ADC  
3. **Ajustar mapping** en el código:
   ```cpp
   data.lightLevel = map(ldrRaw, DARK_VALUE, BRIGHT_VALUE, 0, 100);
   ```

### Consejos de instalación:
- Usar cables cortos para sensores (< 1 metro)
- Aislar térmicamente las NTC del PCB del Arduino
- Proteger sensores de humedad si es necesario
- Separar sensores de fuentes de calor (reguladores, etc.)
- Usar conectores confiables para instalaciones permanentes

### Diagnóstico de problemas:
- **Temperatura = -999**: NTC desconectada o cable roto
- **Temperatura = -998**: Cortocircuito en NTC  
- **Temperatura = -997**: Sensor dañado o fuera de rango
- **Lecturas erráticas**: Cables sueltos o interferencias
- **Temperatura constante**: NTC dañada o valor de resistencia serie incorrecto
