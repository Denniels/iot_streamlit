depura el tiempo de espera, dale un poco mas de tiempo/*
Arduino USB - 3 sondas NTC + LDR vía puerto serial
Hardware: Arduino Uno/Nano + 3x NTC 10kΩ + 1x LDR
Conexiones:
- NTC1: 5V--NTC--A0--R(10kΩ)--GND
- NTC2: 5V--NTC--A1--R(10kΩ)--GND  
- NTC3: 5V--NTC--A2--R(10kΩ)--GND
- LDR: 5V--LDR--A3--R(10kΩ)--GND
*/

#include <ArduinoJson.h>

// Pines y configuración
const int NTC1_PIN = A0;        // Primera sonda NTC 10kΩ
const int NTC2_PIN = A1;        // Segunda sonda NTC 10kΩ  
const int NTC3_PIN = A2;        // Tercera sonda NTC 10kΩ
const int LDR_PIN = A3;         // LDR (fotoresistencia)

// Configuración de sensores NTC
const float SERIES_RESISTOR = 10000.0;   // Resistencia serie 10kΩ
const float NOMINAL_RESISTANCE = 10000.0; // Resistencia NTC nominal 10kΩ
const float NOMINAL_TEMPERATURE = 25.0;   // Temperatura nominal 25°C
const float B_COEFFICIENT = 3950.0;       // Coeficiente B típico para NTC 10kΩ

// Variables globales
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 2000; // 2 segundos

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

void sendInitMessage() {
  StaticJsonDocument<150> doc;
  doc["message_type"] = "init";
  doc["device_id"] = "arduino_usb_001";
  doc["device_type"] = "arduino_usb";
  doc["timestamp"] = millis();
  doc["status"] = "ready";
  
  String jsonString;
  serializeJson(doc, jsonString);
  Serial.println(jsonString);
}

void readAndSendSensors() {
  SensorData data = readSensors();
  sendSensorData(data);
}

SensorData readSensors() {
  SensorData data;
  
  // Leer temperatura de las tres sondas NTC
  data.temperature1 = readNTCTemperature(NTC1_PIN);
  data.temperature2 = readNTCTemperature(NTC2_PIN);
  data.temperature3 = readNTCTemperature(NTC3_PIN);
  
  // Leer LDR (fotoresistencia)
  int ldrRaw = analogRead(LDR_PIN);
  data.lightLevel = map(ldrRaw, 0, 1023, 0, 100);
  
  // Timestamp y estado
  data.timestamp = millis();
  strcpy(data.status, "ok");
  
  return data;
}

float readNTCTemperature(int pin) {
  // Leer valor analógico
  int rawADC = analogRead(pin);
  
  // Convertir a resistencia
  float resistance = SERIES_RESISTOR * ((1023.0 / rawADC) - 1.0);
  
  // Ecuación de Steinhart-Hart simplificada (aproximación B parameter)
  float steinhart;
  steinhart = resistance / NOMINAL_RESISTANCE;           // (R/Ro)
  steinhart = log(steinhart);                            // ln(R/Ro)
  steinhart /= B_COEFFICIENT;                            // 1/B * ln(R/Ro)
  steinhart += 1.0 / (NOMINAL_TEMPERATURE + 273.15);    // + (1/To)
  steinhart = 1.0 / steinhart;                          // Invertir
  steinhart -= 273.15;                                  // Convertir a Celsius
  
  // Validar rango razonable (-40°C a 125°C)
  if (steinhart < -40.0 || steinhart > 125.0) {
    return -999.0; // Valor de error
  }
  
  return steinhart;
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
  
  // Temperatura promedio
  if (data.temperature1 > -100 && data.temperature2 > -100 && data.temperature3 > -100) {
    float avgTemp = (data.temperature1 + data.temperature2 + data.temperature3) / 3.0;
    sensors["temperature_avg"] = round(avgTemp * 10) / 10.0;
  } else {
    sensors["temperature_avg"] = -1;
  }
  
  String jsonString;
  serializeJson(doc, jsonString);
  Serial.println(jsonString);
}

void processCommand() {
  String command = Serial.readStringUntil('\n');
  command.trim();
  
  StaticJsonDocument<100> response;
  response["message_type"] = "command_response";
  response["device_id"] = "arduino_usb_001";
  response["timestamp"] = millis();
  response["command"] = command;
  
  if (command == "STATUS") {
    response["status"] = "ok";
    response["uptime"] = millis();
  } else if (command == "READ_NOW") {
    response["status"] = "ok";
    String jsonString;
    serializeJson(response, jsonString);
    Serial.println(jsonString);
    readAndSendSensors();
    return;
  } else {
    response["status"] = "error";
  }
  
  String jsonString;
  serializeJson(response, jsonString);
  Serial.println(jsonString);
}

// ...sin botón...

// Función para obtener memoria libre (aproximada)
int getFreeMemory() {
  extern int __heap_start, *__brkval;
  int v;
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
}

// Función para leer voltaje VCC
float readVccVoltage() {
  #if defined(__AVR_ATmega32U4__) || defined(__AVR_ATmega1280__) || defined(__AVR_ATmega2560__)
    ADMUX = _BV(REFS0) | _BV(MUX4) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
  #elif defined (__AVR_ATtiny24__) || defined(__AVR_ATtiny44__) || defined(__AVR_ATtiny84__)
    ADMUX = _BV(MUX5) | _BV(MUX0);
  #elif defined (__AVR_ATtiny25__) || defined(__AVR_ATtiny45__) || defined(__AVR_ATtiny85__)
    ADMUX = _BV(MUX3) | _BV(MUX2);
  #else
    ADMUX = _BV(REFS0) | _BV(MUX3) | _BV(MUX2) | _BV(MUX1);
  #endif
  
  delay(2);
  ADCSRA |= _BV(ADSC);
  while (bit_is_set(ADCSRA,ADSC));
  
  uint8_t low  = ADCL;
  uint8_t high = ADCH;
  
  long result = (high<<8) | low;
  result = 1125300L / result;
  return result / 1000.0;
}

// Comandos: STATUS, READ_NOW
// Hardware: 3x NTC 10kΩ (A0,A1,A2) + 1x LDR (A3)
// Conexión NTC: 5V--NTC--Ax--R(10kΩ)--GND
