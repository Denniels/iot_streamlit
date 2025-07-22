/*
Arduino Ethernet - Servidor web para 2 sondas NTC de temperatura
Compatible con IoT Streamlit Backend

Hardware requerido:
- Arduino Uno/Nano/Mega
- Ethernet Shield (W5100/W5500) 
- 2x Sondas NTC 10kΩ (termistores)
- 2x Resistencias 10kΩ (divisor de voltaje)
- LED indicador
- Cable de red

Conexiones:
- Ethernet Shield en pines SPI estándar
- NTC1: Un terminal a 5V, otro a A0 y resistencia 10kΩ a GND
- NTC2: Un terminal a 5V, otro a A1 y resistencia 10kΩ a GND
- LED: Pin 13 (built-in)
- PIN 4 reservado para SD card del Ethernet Shield

Funcionalidad:
- Configura IP estática o DHCP
- Responde a peticiones HTTP GET en /data, /status, /info
- LED parpadea al recibir peticiones
- Datos en formato JSON compatible con backend Python
- Cálculo de temperatura promedio y diferencias entre sondas
- Detección de errores en sensores
*/

#include <SPI.h>
#include <Ethernet.h>
#include <ArduinoJson.h>

// Configuración de red
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED }; // MAC única para cada Arduino
IPAddress ip(192, 168, 1, 100);     // IP estática (cambiar según tu red)
IPAddress gateway(192, 168, 1, 1);   // Gateway de tu red
IPAddress subnet(255, 255, 255, 0);  // Máscara de subred

// Para DHCP (comentar las líneas IP estática si usas DHCP)
// bool useDHCP = true;

// Configuración del servidor
EthernetServer server(80); // Puerto 80 para HTTP

// Pines y configuración de sensores
const int NTC1_PIN = A0;        // Primera sonda NTC 10kΩ
const int NTC2_PIN = A1;        // Segunda sonda NTC 10kΩ  
const int LED_PIN = 13;

// Configuración de sensores NTC
const float SERIES_RESISTOR = 10000.0;   // Resistencia serie 10kΩ
const float NOMINAL_RESISTANCE = 10000.0; // Resistencia NTC nominal 10kΩ
const float NOMINAL_TEMPERATURE = 25.0;   // Temperatura nominal 25°C
const float B_COEFFICIENT = 3950.0;       // Coeficiente B típico para NTC 10kΩ

// Variables globales
String deviceId = "arduino_eth_001"; // ID único del dispositivo
String deviceType = "arduino_ethernet";
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 1000; // Leer sensores cada segundo
bool networkReady = false;

// Estructura de datos del sensor
struct SensorData {
  float temperature1;    // Temperatura NTC1
  float temperature2;    // Temperatura NTC2
  float voltage;
  unsigned long uptime;
  String status;
};

SensorData lastReading;

void setup() {
  // Inicializar comunicación serial para debug
  Serial.begin(9600);
  while (!Serial) {
    ; // Esperar conexión serial para Leonardo/Micro
  }
  
  Serial.println("Arduino Ethernet IoT Sensor iniciando...");
  
  // Configurar pines
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  
  // Pin 4 reservado para SD card del Ethernet Shield
  pinMode(4, OUTPUT);
  digitalWrite(4, HIGH);
  
  // Configurar referencia analógica
  analogReference(DEFAULT);
  
  // Inicializar Ethernet
  Serial.println("Inicializando Ethernet...");
  
  // Intentar DHCP primero, luego IP estática
  if (Ethernet.begin(mac) == 0) {
    Serial.println("DHCP falló, usando IP estática");
    Ethernet.begin(mac, ip, gateway, subnet);
  }
  
  // Dar tiempo para inicializar
  delay(1000);
  
  // Iniciar servidor
  server.begin();
  
  // Mostrar configuración de red
  Serial.print("Servidor iniciado en IP: ");
  Serial.println(Ethernet.localIP());
  Serial.print("Puerto: 80");
  Serial.println();
  Serial.println("Endpoints disponibles:");
  Serial.println("  GET /data    - Datos de sensores actuales");
  Serial.println("  GET /status  - Estado del dispositivo");
  Serial.println("  GET /info    - Información del dispositivo");
  Serial.println();
  
  networkReady = true;
  
  // Parpadeo de confirmación
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(200);
    digitalWrite(LED_PIN, LOW);
    delay(200);
  }
  
  Serial.println("Sistema listo. Esperando peticiones...");
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
  switch (Ethernet.maintain()) {
    case 1:
      Serial.println("Error: renovación DHCP falló");
      break;
    case 2:
      Serial.println("DHCP renovado exitosamente");
      break;
    case 3:
      Serial.println("Error: rebind DHCP falló");
      break;
    case 4:
      Serial.println("DHCP rebind exitoso");
      break;
    default:
      // Sin cambios en DHCP
      break;
  }
  
  delay(10); // Pequeña pausa para estabilidad
}

void handleClient(EthernetClient client) {
  Serial.println("Cliente conectado");
  
  // LED indica actividad
  digitalWrite(LED_PIN, HIGH);
  
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
            Serial.print("Petición: GET ");
            Serial.println(httpPath);
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
    } else if (httpPath == "/info") {
      sendInfoData(client);
    } else {
      sendNotFound(client);
    }
  }
  
  // Cerrar conexión
  delay(10);
  client.stop();
  digitalWrite(LED_PIN, LOW);
  Serial.println("Cliente desconectado");
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
  data.status = "ok";
  
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
  // Crear JSON con datos de sensores
  StaticJsonDocument<400> doc;
  
  doc["message_type"] = "sensor_data";
  doc["device_id"] = deviceId;
  doc["device_type"] = deviceType;
  doc["timestamp"] = millis();
  doc["status"] = lastReading.status;
  
  // Datos de sensores
  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["temperature_1"] = round(lastReading.temperature1 * 10) / 10.0; // NTC1
  sensors["temperature_2"] = round(lastReading.temperature2 * 10) / 10.0; // NTC2
  
  // Cálculos adicionales si ambas temperaturas son válidas
  if (lastReading.temperature1 > -100 && lastReading.temperature2 > -100) {
    float avgTemp = (lastReading.temperature1 + lastReading.temperature2) / 2.0;
    sensors["temperature_avg"] = round(avgTemp * 10) / 10.0;
    
    float tempDiff = abs(lastReading.temperature1 - lastReading.temperature2);
    sensors["temperature_diff"] = round(tempDiff * 10) / 10.0;
  } else {
    sensors["temperature_avg"] = -1;   // Indicador de error
    sensors["temperature_diff"] = -1;  // Indicador de error
  }
  
  // Información del sistema
  JsonObject info = doc.createNestedObject("info");
  info["uptime"] = lastReading.uptime;
  info["voltage"] = lastReading.voltage;
  info["ip_address"] = Ethernet.localIP().toString();
  info["free_memory"] = getFreeMemory();
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 200, "application/json", jsonString);
}

void sendStatusData(EthernetClient client) {
  StaticJsonDocument<300> doc;
  
  doc["message_type"] = "status";
  doc["device_id"] = deviceId;
  doc["device_type"] = deviceType;
  doc["timestamp"] = millis();
  doc["status"] = "online";
  doc["uptime"] = millis();
  doc["network_status"] = "connected";
  doc["ip_address"] = Ethernet.localIP().toString();
  doc["mac_address"] = String(mac[0], HEX) + ":" + 
                       String(mac[1], HEX) + ":" + 
                       String(mac[2], HEX) + ":" + 
                       String(mac[3], HEX) + ":" + 
                       String(mac[4], HEX) + ":" + 
                       String(mac[5], HEX);
  doc["firmware_version"] = "1.0.0";
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 200, "application/json", jsonString);
}

void sendInfoData(EthernetClient client) {
  StaticJsonDocument<400> doc;
  
  doc["device_info"] = deviceId;
  doc["device_type"] = deviceType;
  doc["firmware_version"] = "1.0.0";
  doc["hardware"] = "Arduino + Ethernet Shield";
  doc["sensors"] = "Temperature, Humidity, Light";
  doc["uptime"] = millis();
  doc["memory"] = getFreeMemory();
  doc["voltage"] = readVccVoltage();
  
  JsonObject network = doc.createNestedObject("network");
  network["ip"] = Ethernet.localIP().toString();
  network["gateway"] = Ethernet.gatewayIP().toString();
  network["subnet"] = Ethernet.subnetMask().toString();
  network["dns"] = Ethernet.dnsServerIP().toString();
  
  JsonObject endpoints = doc.createNestedObject("endpoints");
  endpoints["/data"] = "Sensor data in JSON format";
  endpoints["/status"] = "Device status information";
  endpoints["/info"] = "Device information and capabilities";
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 200, "application/json", jsonString);
}

void sendNotFound(EthernetClient client) {
  StaticJsonDocument<200> doc;
  doc["error"] = "endpoint_not_found";
  doc["message"] = "Available endpoints: /data, /status, /info";
  doc["device_id"] = deviceId;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  sendHttpResponse(client, 404, "application/json", jsonString);
}

void sendHttpResponse(EthernetClient client, int statusCode, String contentType, String body) {
  // Headers HTTP
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
  client.println("Access-Control-Allow-Origin: *"); // CORS para web apps
  client.println();
  
  // Cuerpo de respuesta
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

/*
CONFIGURACIÓN IMPORTANTE:

1. Cambiar la IP estática según tu red local
2. Si tienes múltiples Arduinos, cambiar:
   - MAC address (debe ser única)
   - IP address (debe ser única)
   - device_id (debe ser único)

3. Conexiones de sensores NTC 10kΩ:
   - NTC1: 5V ---- NTC ---- A0 ---- R(10kΩ) ---- GND
   - NTC2: 5V ---- NTC ---- A1 ---- R(10kΩ) ---- GND
   
4. Calibración de NTC:
   - Coeficiente B = 3950K (típico)
   - Para mayor precisión, medir resistencia real a temperatura conocida
   - Ajustar B_COEFFICIENT si es necesario

5. Test de endpoints:
   - http://IP_DEL_ARDUINO/data    -> Datos de sensores
   - http://IP_DEL_ARDUINO/status  -> Estado del dispositivo  
   - http://IP_DEL_ARDUINO/info    -> Información detallada

6. Códigos de error de temperatura:
   - -999.0: Circuito abierto (NTC desconectada)
   - -998.0: Cortocircuito 
   - -997.0: Temperatura fuera de rango (-40°C a 125°C)

7. El backend Python detectará automáticamente estos Arduinos
   escaneando la red y probando el endpoint /status

Ejemplo de respuesta JSON:
{
  "message_type": "sensor_data",
  "device_id": "arduino_eth_001",
  "device_type": "arduino_ethernet", 
  "timestamp": 12345,
  "status": "ok",
  "sensors": {
    "temperature_1": 23.5,      // NTC1 en °C
    "temperature_2": 24.1,      // NTC2 en °C
    "temperature_avg": 23.8,    // Promedio °C
    "temperature_diff": 0.6     // Diferencia absoluta °C
  },
  "info": {
    "uptime": 12345,
    "voltage": 5.0,
    "ip_address": "192.168.1.100",
    "free_memory": 1234
  }
}
*/
