
#include <ArduinoJson.h>
#include <WiFi.h>
#include <WebServer.h>
#include <time.h>

// Pines de sensores
#define LDR_PIN 12
#define NTC1_PIN 27
#define NTC2_PIN 14

const char* DEVICE_ID = "esp32_wifi_001";
const char* ssid = "DMS_2.4Gm"; // Cambia a "DMS_5G" si lo prefieres
const char* password = "DAms15820";

const float SERIES_RESISTOR = 10000.0;
const float NOMINAL_RESISTANCE = 10000.0;
const float NOMINAL_TEMPERATURE = 25.0;
const float B_COEFFICIENT = 3950.0;
const int ADC_MAX = 4095;

WebServer server(80);

float readNTC(int pin) {
  int adc = analogRead(pin);
  if (adc <= 0 || adc >= ADC_MAX) {
    return 25.0; // Valor por defecto si no hay sensor conectado
  }
  
  float voltage = (adc * 3.3) / ADC_MAX;
  float resistance = SERIES_RESISTOR * voltage / (3.3 - voltage);
  
  if (resistance <= 0) {
    return 25.0; // Valor por defecto
  }
  
  float steinhart;
  steinhart = resistance / NOMINAL_RESISTANCE;
  steinhart = log(steinhart);
  steinhart /= B_COEFFICIENT;
  steinhart += 1.0 / (NOMINAL_TEMPERATURE + 273.15);
  steinhart = 1.0 / steinhart;
  steinhart -= 273.15;
  
  // Validar rango razonable
  if (steinhart < -50 || steinhart > 150) {
    return 25.0;
  }
  
  return steinhart;
}

float readLDR(int pin) {
  int adc = analogRead(pin);
  return (adc * 100.0) / ADC_MAX;
}

void handleData() {
  StaticJsonDocument<512> doc;
  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["ntc_entrada"] = readNTC(NTC1_PIN);
  sensors["ntc_salida"] = readNTC(NTC2_PIN);
  sensors["ldr"] = readLDR(LDR_PIN);
  doc["device_id"] = DEVICE_ID;
  doc["ip"] = WiFi.localIP().toString();
  String output;
  serializeJson(doc, output);
  server.send(200, "application/json", output);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Conectando a WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado. IP: " + WiFi.localIP().toString());

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.println("Esperando sincronización NTP...");
  time_t now = time(nullptr);
  while (now < 100000) {
    delay(500);
    Serial.print(".");
    now = time(nullptr);
  }
  Serial.println("\nHora sincronizada.");

  server.on("/data", handleData);
  server.begin();
  Serial.println("Servidor HTTP iniciado.");
}

void loop() {
  server.handleClient();
}