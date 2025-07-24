// Arduino Ethernet - 2 sondas NTC de temperatura
// Hardware: Arduino Uno/Nano/Mega + Ethernet Shield + 2x NTC 10kΩ
// Conexión: NTC1 en A0, NTC2 en A1, divisor 10kΩ a GND
// Endpoints: /data, /status

#include <SPI.h>
#include <Ethernet.h>
#include <ArduinoJson.h>

// Configuración de red
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED }; // MAC única para cada Arduino
IPAddress ip(192, 168, 1, 100);     // IP estática en tu red
IPAddress gateway(192, 168, 1, 1);   // Gateway de tu red
IPAddress subnet(255, 255, 255, 0);  // Máscara de subred
IPAddress dns(192, 168, 1, 1);       // DNS server

// Para DHCP (comentar las líneas IP estática si usas DHCP)
// bool useDHCP = true;

// Configuración del servidor
EthernetServer server(80); // Puerto 80 para HTTP

// Pines y configuración de sensores
const int NTC1_PIN = A0;        // Primera sonda NTC 10kΩ
const int NTC2_PIN = A1;        // Segunda sonda NTC 10kΩ

// Configuración de sensores NTC
const float SERIES_RESISTOR = 10000.0;   // Resistencia serie 10kΩ
const float NOMINAL_RESISTANCE = 10000.0; // Resistencia NTC nominal 10kΩ
const float NOMINAL_TEMPERATURE = 25.0;   // Temperatura nominal 25°C
const float B_COEFFICIENT = 3950.0;       // Coeficiente B típico para NTC 10kΩ

// Variables globales
const char deviceId[] = "arduino_eth_001"; // ID único del dispositivo
const char deviceType[] = "arduino_ethernet";
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 1000; // Leer sensores cada segundo
bool networkReady = false;

// Estructura de datos del sensor
struct SensorData {
  float temperature1;    // Temperatura NTC1
  float temperature2;    // Temperatura NTC2
  float voltage;
  unsigned long uptime;
  char status[8];
};

SensorData lastReading;

void setup() {
  pinMode(4, OUTPUT);
  digitalWrite(4, HIGH);
  analogReference(DEFAULT);
  
  // Intentar DHCP primero, si falla usar IP estática
  if (Ethernet.begin(mac) == 0) {
    // DHCP falló, configurar IP estática
    Ethernet.begin(mac, ip, dns, gateway, subnet);
  }
  
  delay(2000); // Dar más tiempo para inicializar
  server.begin();
  networkReady = true;
}

void loop() {
  unsigned long currentTime = millis();
  
  // Leer sensores periódicamente
  if (currentTime - lastSensorRead >= SENSOR_INTERVAL) {
    lastReading = readSensors();
    lastSensorRead = currentTime;
  }
  
  // Verificar si hay clientes conectados
  EthernetClient client = server.available();
  if (client) {
    handleClient(client);
  }
  
  // Mantener conexión Ethernet
  Ethernet.maintain();
  
  delay(10); // Pequeña pausa para estabilidad
}

void handleClient(EthernetClient client) {
  String currentLine = "";
  String httpMethod = "";
  String httpPath = "";
  bool isHeaderComplete = false;
  
  while (client.connected()) {
    if (client.available()) {
      char c = client.read();
      
      if (c == '\n') {
        if (currentLine.length() == 0) {
          // Fin de headers HTTP
          isHeaderComplete = true;
          break;
        } else {
          // Procesar línea de header
          if (currentLine.startsWith("GET ")) {
            httpMethod = "GET";
            int spaceIndex = currentLine.indexOf(' ', 4);
            httpPath = currentLine.substring(4, spaceIndex);
          }
          currentLine = "";
        }
      } else if (c != '\r') {
        currentLine += c;
      }
    }
  }
  
  if (isHeaderComplete && httpMethod == "GET") {
    // Procesar diferentes endpoints
    if (httpPath == "/data") {
      sendSensorData(client);
    } else if (httpPath == "/status") {
      sendStatusData(client);
    } else {
      sendNotFound(client);
    }
  }
  
  // Cerrar conexión
  delay(10);
  client.stop();
}

SensorData readSensors() {
  SensorData data;
  
  // Leer temperatura de las dos sondas NTC
  data.temperature1 = readNTCTemperature(NTC1_PIN);
  data.temperature2 = readNTCTemperature(NTC2_PIN);
  
  // Voltaje de alimentación
  data.voltage = readVccVoltage();
  
  // Uptime
  data.uptime = millis();
  
  // Estado
  strcpy(data.status, "ok");
  
  return data;
}

float readNTCTemperature(int pin) {
  // Leer valor analógico
  int rawADC = analogRead(pin);
  
  // Evitar división por cero
  if (rawADC >= 1023) {
    return -999.0; // Error: circuito abierto
  }
  if (rawADC <= 0) {
    return -998.0; // Error: cortocircuito
  }
  
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
    return -997.0; // Valor fuera de rango
  }
  
  return steinhart;
}

void sendSensorData(EthernetClient client) {
  StaticJsonDocument<150> doc;
  
  doc["message_type"] = "sensor_data";
  doc["device_id"] = deviceId;
  doc["device_type"] = deviceType;
  doc["timestamp"] = millis();
  doc["status"] = lastReading.status;
  
  // Datos de sensores
  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["temperature_1"] = round(lastReading.temperature1 * 10) / 10.0;
  sensors["temperature_2"] = round(lastReading.temperature2 * 10) / 10.0;
  
  // Temperatura promedio
  if (lastReading.temperature1 > -100 && lastReading.temperature2 > -100) {
    float avgTemp = (lastReading.temperature1 + lastReading.temperature2) / 2.0;
    sensors["temperature_avg"] = round(avgTemp * 10) / 10.0;
  } else {
    sensors["temperature_avg"] = -1;
  }
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 200, "application/json", jsonString);
}

void sendStatusData(EthernetClient client) {
  StaticJsonDocument<100> doc;
  
  doc["message_type"] = "status";
  doc["device_id"] = deviceId;
  doc["device_type"] = deviceType;
  doc["timestamp"] = millis();
  doc["status"] = "online";
  char ipStr[16];
  IPAddress ip = Ethernet.localIP();
  sprintf(ipStr, "%u.%u.%u.%u", ip[0], ip[1], ip[2], ip[3]);
  doc["ip_address"] = ipStr;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 200, "application/json", jsonString);
}

void sendNotFound(EthernetClient client) {
  StaticJsonDocument<50> doc;
  doc["error"] = "not_found";
  doc["device_id"] = deviceId;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 404, "application/json", jsonString);
}

void sendHttpResponse(EthernetClient client, int statusCode, String contentType, String body) {
  client.print("HTTP/1.1 ");
  client.print(statusCode);
  if (statusCode == 200) {
    client.println(" OK");
  } else if (statusCode == 404) {
    client.println(" Not Found");
  }
  
  client.print("Content-Type: ");
  client.println(contentType);
  client.println("Connection: close");
  client.print("Content-Length: ");
  client.println(body.length());
  client.println();
  
  client.print(body);
}

// Función para obtener memoria libre
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

// Configuración: Cambia IP/MAC/device_id si tienes varios Arduinos
// Red: 192.168.1.x - El Arduino usará IP 192.168.1.100
// NTC1: 5V--NTC--A0--R(10kΩ)--GND | NTC2: 5V--NTC--A1--R(10kΩ)--GND
// Endpoints: /data, /status
// Acceso: http://192.168.1.100/data