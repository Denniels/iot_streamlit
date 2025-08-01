/*
Arduino USB Sensor - CÓDIGO CORREGIDO
Proyecto IoT Streamlit
3x NTC 10kΩ (A0, A1, A2) + 1x LDR (A3)

CONEXIONES CORREGIDAS:
- NTC1: 5V--NTC--A0--R(10kΩ)--GND
- NTC2: 5V--NTC--A1--R(10kΩ)--GND  
- NTC3: 5V--NTC--A2--R(10kΩ)--GND
- LDR:  5V--LDR--A3--R(10kΩ)--GND

CORRECCIÓN APLICADA: Fórmula de resistencia NTC corregida
*/

#include <ArduinoJson.h>

// Definir pines
#define NTC1_PIN A0
#define NTC2_PIN A1
#define NTC3_PIN A2
#define LDR_PIN A3

// Constantes para NTC
const float SERIES_RESISTOR = 10000.0;   // 10kΩ
const float B_COEFFICIENT = 3950.0;      // Coeficiente B para NTC 10kΩ
const float NOMINAL_RESISTANCE = 10000.0; // Resistencia a 25°C
const float NOMINAL_TEMPERATURE = 25.0 + 273.15; // 25°C en Kelvin

// Configuración de timing
const unsigned long SENSOR_INTERVAL = 2000; // Leer sensores cada 2 segundos
unsigned long lastSensorRead = 0;

// Estructura de datos del sensor
struct SensorData {
  float temperature1;    // Temperatura NTC1
  float temperature2;    // Temperatura NTC2
  float temperature3;    // Temperatura NTC3
  int lightLevel;        // Nivel de luz LDR (0-100%)
  unsigned long timestamp;
  char status[8];
};

void setup() {
  Serial.begin(9600);
  analogReference(DEFAULT);
  sendInitMessage();
}

void loop() {
  unsigned long currentTime = millis();
  
  // Leer sensores cada SENSOR_INTERVAL
  if (currentTime - lastSensorRead >= SENSOR_INTERVAL) {
    readAndSendSensors();
    lastSensorRead = currentTime;
  }
  
  // Verificar si hay comandos desde Python
  if (Serial.available() > 0) {
    processCommand();
  }
  
  delay(10); // Pequeña pausa para estabilidad
}

void readAndSendSensors() {
  SensorData data = readSensors();
  sendSensorData(data);
}

SensorData readSensors() {
  SensorData data;
  
  // Leer temperaturas NTC (CORREGIDO)
  data.temperature1 = readNTCTemperatureCorrected(NTC1_PIN);
  data.temperature2 = readNTCTemperatureCorrected(NTC2_PIN);
  data.temperature3 = readNTCTemperatureCorrected(NTC3_PIN);
  
  // Leer nivel de luz LDR
  int ldrRaw = analogRead(LDR_PIN);
  data.lightLevel = map(ldrRaw, 0, 1023, 0, 100);
  
  data.timestamp = millis();
  strcpy(data.status, "ok");
  
  return data;
}

float readNTCTemperatureCorrected(int pin) {
  /*
  CÁLCULO FINAL CORREGIDO para configuración: 5V--NTC--A0--R(10kΩ)--GND
  En esta configuración el voltaje aumenta cuando el NTC se calienta (resistencia baja)
  */
  
  int rawADC = analogRead(pin);
  if (rawADC <= 0) return -999.0;
  
  // Voltaje en el pin analógico
  float voltage = (rawADC / 1023.0) * 5.0;
  
  // Resistencia del NTC (FÓRMULA FINAL CORREGIDA)
  // V_pin = 5V * R_series / (R_ntc + R_series)
  // Despejando: R_ntc = R_series * V_pin / (5V - V_pin)
  if (voltage >= 5.0) return -999.0;
  
  float ntcResistance = SERIES_RESISTOR * voltage / (5.0 - voltage);
  
  // Ecuación de Steinhart-Hart simplificada
  float steinhart = log(ntcResistance / NOMINAL_RESISTANCE) / B_COEFFICIENT;
  steinhart += 1.0 / NOMINAL_TEMPERATURE;
  float temperatureKelvin = 1.0 / steinhart;
  float temperatureCelsius = temperatureKelvin - 273.15;
  
  // Validar rango razonable
  if (temperatureCelsius < -40.0 || temperatureCelsius > 125.0) {
    return -999.0;
  }
  
  return temperatureCelsius;
}

void sendSensorData(SensorData data) {
  StaticJsonDocument<200> doc;
  
  doc["message_type"] = "sensor_data";
  doc["device_id"] = "arduino_usb_001";
  doc["device_type"] = "arduino_usb";
  doc["timestamp"] = data.timestamp;
  doc["status"] = data.status;
  
  // Datos de sensores
  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["temperature_1"] = round(data.temperature1 * 10) / 10.0;
  sensors["temperature_2"] = round(data.temperature2 * 10) / 10.0;
  sensors["temperature_3"] = round(data.temperature3 * 10) / 10.0;
  sensors["light_level"] = data.lightLevel;
  
  // Temperatura promedio (solo si todas son válidas)
  if (data.temperature1 > -100 && data.temperature2 > -100 && data.temperature3 > -100) {
    float avgTemp = (data.temperature1 + data.temperature2 + data.temperature3) / 3.0;
    sensors["temperature_avg"] = round(avgTemp * 10) / 10.0;
  } else {
    sensors["temperature_avg"] = -999;
  }
  
  // Diagnóstico ADC (para debug)
  JsonObject debug = doc.createNestedObject("debug");
  debug["adc_ntc1"] = analogRead(NTC1_PIN);
  debug["adc_ntc2"] = analogRead(NTC2_PIN);
  debug["adc_ntc3"] = analogRead(NTC3_PIN);
  debug["adc_ldr"] = analogRead(LDR_PIN);
  
  serializeJson(doc, Serial);
  Serial.println();
}

void processCommand() {
  String command = Serial.readStringUntil('\n');
  command.trim();
  
  StaticJsonDocument<100> response;
  response["message_type"] = "command_response";
  response["command"] = command;
  
  if (command == "STATUS") {
    response["status"] = "ok";
    response["device_id"] = "arduino_usb_001";
    response["uptime"] = millis();
    response["free_memory"] = getFreeMemory();
  } else if (command == "READ_NOW") {
    response["status"] = "reading";
    serializeJson(response, Serial);
    Serial.println();
    readAndSendSensors();
    return;
  } else {
    response["status"] = "unknown_command";
  }
  
  serializeJson(response, Serial);
  Serial.println();
}

void sendInitMessage() {
  StaticJsonDocument<150> doc;
  doc["message_type"] = "init";
  doc["device_id"] = "arduino_usb_001";
  doc["device_type"] = "arduino_usb";
  doc["firmware_version"] = "1.2_final_fix";
  doc["sensors"] = "3x_NTC_10k + 1x_LDR";
  doc["status"] = "ready";
  doc["correction"] = "NTC_formula_final_corrected";
  
  serializeJson(doc, Serial);
  Serial.println();
}

// Función para obtener memoria libre (aproximada)
int getFreeMemory() {
  extern int __heap_start, *__brkval;
  int v;
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
}

// Función para leer voltaje VCC
float readVccVoltage() {
  long result;
  ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
  delay(2);
  ADCSRA |= _BV(ADSC);
  while (bit_is_set(ADCSRA,ADSC));
  result = ADCL;
  result |= ADCH<<8;
  result = 1126400L / result;
  return result / 1000.0;
}

// Comandos: STATUS, READ_NOW
// Hardware: 3x NTC 10kΩ (A0,A1,A2) + 1x LDR (A3)
// Conexión NTC: 5V--NTC--Ax--R(10kΩ)--GND
// CORRECCIÓN FINAL: Fórmula R_ntc = R_series * V_pin / (5V - V_pin)
