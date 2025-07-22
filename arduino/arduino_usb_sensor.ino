/*
Arduino USB - Envío de datos de 3 sondas NTC + LDR vía puerto serial
Compatible con IoT Streamlit Backend

Hardware requerido:
- Arduino Uno/Nano/Pro Mini
- 3x Sondas NTC 10kΩ (termistores)  
- 3x Resistencias 10kΩ (divisor de voltaje)
- 1x LDR (fotoresistencia)
- 1x Resistencia 10kΩ para LDR
- LED indicador (built-in en pin 13)
- Botón opcional con pull-up

Conexiones:
- NTC1: Un terminal a 5V, otro a A0 y resistencia 10kΩ a GND
- NTC2: Un terminal a 5V, otro a A1 y resistencia 10kΩ a GND  
- NTC3: Un terminal a 5V, otro a A2 y resistencia 10kΩ a GND
- LDR: Un terminal a 5V, otro a A3 y resistencia 10kΩ a GND
- LED indicador: Pin 13 (built-in)
- Botón opcional: Pin 2 con pull-up interno

Funcionalidad:
- Lee 3 sondas NTC cada 2 segundos
- Calcula temperatura usando ecuación Steinhart-Hart
- Lee LDR para nivel de luz
- Envía datos en formato JSON vía serial
- LED parpadea al enviar datos
- Responde a comandos desde Python
- Calcula temperatura promedio y diferencias
*/

#include <ArduinoJson.h>

// Pines y configuración
const int NTC1_PIN = A0;        // Primera sonda NTC 10kΩ
const int NTC2_PIN = A1;        // Segunda sonda NTC 10kΩ  
const int NTC3_PIN = A2;        // Tercera sonda NTC 10kΩ
const int LDR_PIN = A3;         // LDR (fotoresistencia)
const int LED_PIN = 13;
const int BUTTON_PIN = 2;

// Configuración de sensores NTC
const float SERIES_RESISTOR = 10000.0;   // Resistencia serie 10kΩ
const float NOMINAL_RESISTANCE = 10000.0; // Resistencia NTC nominal 10kΩ
const float NOMINAL_TEMPERATURE = 25.0;   // Temperatura nominal 25°C
const float B_COEFFICIENT = 3950.0;       // Coeficiente B típico para NTC 10kΩ

// Variables globales
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 2000; // 2 segundos
bool ledState = false;
bool buttonPressed = false;

// Estructura de datos del sensor
struct SensorData {
  float temperature1;    // Temperatura NTC1
  float temperature2;    // Temperatura NTC2
  float temperature3;    // Temperatura NTC3
  int lightLevel;        // Nivel de luz LDR (0-100%)
  bool buttonState;
  unsigned long timestamp;
  String status;
};

void setup() {
  // Inicializar comunicación serial
  Serial.begin(9600);
  while (!Serial) {
    ; // Esperar conexión serial
  }
  
  // Configurar pines
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  // Configurar referencia analógica
  analogReference(DEFAULT);
  
  // Mensaje de inicio
  digitalWrite(LED_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  
  // Enviar mensaje de inicialización
  sendInitMessage();
  
  Serial.println("Arduino USB inicializado y listo");
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
  
  // Verificar botón
  checkButton();
  
  delay(10); // Pequeña pausa para estabilidad
}

void sendInitMessage() {
  StaticJsonDocument<200> doc;
  doc["message_type"] = "init";
  doc["device_id"] = "arduino_usb_001";
  doc["device_type"] = "arduino_usb";
  doc["firmware_version"] = "1.0.0";
  doc["timestamp"] = millis();
  doc["status"] = "ready";
  
  String jsonString;
  serializeJson(doc, jsonString);
  Serial.println(jsonString);
}

void readAndSendSensors() {
  SensorData data = readSensors();
  sendSensorData(data);
  
  // Parpadear LED al enviar datos
  digitalWrite(LED_PIN, HIGH);
  delay(50);
  digitalWrite(LED_PIN, LOW);
}

SensorData readSensors() {
  SensorData data;
  
  // Leer temperatura de las tres sondas NTC
  data.temperature1 = readNTCTemperature(NTC1_PIN);
  data.temperature2 = readNTCTemperature(NTC2_PIN);
  data.temperature3 = readNTCTemperature(NTC3_PIN);
  
  // Leer LDR (fotoresistencia)
  int ldrRaw = analogRead(LDR_PIN);
  // Convertir a porcentaje (0 = oscuridad total, 100 = luz máxima)
  data.lightLevel = map(ldrRaw, 0, 1023, 0, 100);
  
  // Estado del botón
  data.buttonState = !digitalRead(BUTTON_PIN); // Invertido por pull-up
  
  // Timestamp y estado
  data.timestamp = millis();
  data.status = "ok";
  
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
  StaticJsonDocument<300> doc;
  
  doc["message_type"] = "sensor_data";
  doc["device_id"] = "arduino_usb_001";
  doc["device_type"] = "arduino_usb";
  doc["timestamp"] = data.timestamp;
  doc["status"] = data.status;
  
  // Datos de sensores
  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["temperature_1"] = round(data.temperature1 * 10) / 10.0; // NTC1 - 1 decimal
  sensors["temperature_2"] = round(data.temperature2 * 10) / 10.0; // NTC2 - 1 decimal  
  sensors["temperature_3"] = round(data.temperature3 * 10) / 10.0; // NTC3 - 1 decimal
  sensors["light_level"] = data.lightLevel;                        // LDR en %
  sensors["button_pressed"] = data.buttonState;
  
  // Temperaturas promedio y diferencias
  float avgTemp = (data.temperature1 + data.temperature2 + data.temperature3) / 3.0;
  sensors["temperature_avg"] = round(avgTemp * 10) / 10.0;
  
  // Solo calcular si las temperaturas son válidas (no -999)
  if (data.temperature1 > -100 && data.temperature2 > -100 && data.temperature3 > -100) {
    float maxTemp = max(max(data.temperature1, data.temperature2), data.temperature3);
    float minTemp = min(min(data.temperature1, data.temperature2), data.temperature3);
    sensors["temperature_diff"] = round((maxTemp - minTemp) * 10) / 10.0;
  } else {
    sensors["temperature_diff"] = -1; // Indicador de error
  }
  
  // Información adicional
  JsonObject info = doc.createNestedObject("info");
  info["uptime"] = millis();
  info["free_memory"] = getFreeMemory();
  info["voltage"] = readVccVoltage();
  
  String jsonString;
  serializeJson(doc, jsonString);
  Serial.println(jsonString);
}

void processCommand() {
  String command = Serial.readStringUntil('\n');
  command.trim();
  
  StaticJsonDocument<200> response;
  response["message_type"] = "command_response";
  response["device_id"] = "arduino_usb_001";
  response["timestamp"] = millis();
  response["command"] = command;
  
  if (command == "STATUS") {
    response["status"] = "ok";
    response["uptime"] = millis();
    response["sensors_active"] = true;
    
  } else if (command == "LED_ON") {
    digitalWrite(LED_PIN, HIGH);
    response["status"] = "ok";
    response["action"] = "led_on";
    
  } else if (command == "LED_OFF") {
    digitalWrite(LED_PIN, LOW);
    response["status"] = "ok";
    response["action"] = "led_off";
    
  } else if (command == "READ_NOW") {
    response["status"] = "ok";
    response["action"] = "reading_sensors";
    String jsonString;
    serializeJson(response, jsonString);
    Serial.println(jsonString);
    
    // Leer y enviar sensores inmediatamente
    readAndSendSensors();
    return;
    
  } else if (command == "RESET") {
    response["status"] = "ok";
    response["action"] = "resetting";
    String jsonString;
    serializeJson(response, jsonString);
    Serial.println(jsonString);
    
    delay(100);
    // Software reset
    asm volatile ("  jmp 0");
    
  } else {
    response["status"] = "error";
    response["message"] = "comando_no_reconocido";
  }
  
  String jsonString;
  serializeJson(response, jsonString);
  Serial.println(jsonString);
}

void checkButton() {
  bool currentButtonState = !digitalRead(BUTTON_PIN);
  
  if (currentButtonState && !buttonPressed) {
    // Botón presionado (flanco ascendente)
    buttonPressed = true;
    
    StaticJsonDocument<200> doc;
    doc["message_type"] = "event";
    doc["device_id"] = "arduino_usb_001";
    doc["event_type"] = "button_pressed";
    doc["timestamp"] = millis();
    doc["status"] = "ok";
    
    String jsonString;
    serializeJson(doc, jsonString);
    Serial.println(jsonString);
    
    // Feedback visual
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_PIN, HIGH);
      delay(100);
      digitalWrite(LED_PIN, LOW);
      delay(100);
    }
    
  } else if (!currentButtonState && buttonPressed) {
    // Botón liberado
    buttonPressed = false;
  }
}

// Función para obtener memoria libre (aproximada)
int getFreeMemory() {
  extern int __heap_start, *__brkval;
  int v;
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
}

// Función para leer voltaje VCC
float readVccVoltage() {
  // Lee la referencia interna de 1.1V contra VCC
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
  result = 1125300L / result; // Calcular VCC en mV
  return result / 1000.0; // Convertir a V
}

/*
Comandos soportados:
- STATUS: Devuelve estado del dispositivo
- LED_ON: Enciende LED integrado  
- LED_OFF: Apaga LED integrado
- READ_NOW: Lee sensores inmediatamente
- RESET: Reinicia el Arduino

Formato de datos JSON enviados:
{
  "message_type": "sensor_data",
  "device_id": "arduino_usb_001", 
  "device_type": "arduino_usb",
  "timestamp": 12345,
  "status": "ok",
  "sensors": {
    "temperature_1": 23.5,     // NTC1 en °C
    "temperature_2": 24.1,     // NTC2 en °C  
    "temperature_3": 23.8,     // NTC3 en °C
    "temperature_avg": 23.8,   // Promedio °C
    "temperature_diff": 0.6,   // Diferencia max-min °C
    "light_level": 78,         // LDR en % (0=oscuro, 100=claro)
    "button_pressed": false
  },
  "info": {
    "uptime": 12345,
    "free_memory": 1234,
    "voltage": 5.0
  }
}

Notas sobre calibración NTC:
- Coeficiente B = 3950K (típico para NTC 10kΩ)
- Temperatura nominal = 25°C
- Si necesitas mayor precisión, calibra el coeficiente B:
  1. Mide resistencia real a temperatura conocida
  2. Ajusta B_COEFFICIENT en el código
  3. Para mayor precisión usa tabla lookup o Steinhart-Hart completa
  
Conexión típica NTC:
5V ---- NTC ---- A0 ---- R(10kΩ) ---- GND

Conexión típica LDR:
5V ---- LDR ---- A3 ---- R(10kΩ) ---- GND
*/
