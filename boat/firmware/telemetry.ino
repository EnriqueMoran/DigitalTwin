#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_BNO055.h>
#include <TinyGPSPlus.h>
#include <time.h>

// --- WiFi credentials -------------------------------------------------------
#ifndef WIFI_SSID
#define WIFI_SSID "YOUR_WIFI_SSID"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#endif

// --- MQTT configuration -----------------------------------------------------
#ifndef MQTT_HOST
#define MQTT_HOST "192.168.1.10"
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif

// Serial pins for GPS module (ESP32: RX2=16, TX2=17)
static const int GPS_RX_PIN = 16; // GPS TX -> ESP32 RX2
static const int GPS_TX_PIN = 17; // GPS RX <- ESP32 TX2 (usually unused)

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

Adafruit_BNO055 bno = Adafruit_BNO055();
TinyGPSPlus gps;
HardwareSerial GPSSerial(1); // use UART1

static uint32_t seq = 0; // sequence number for IMU messages

// ----------------------------------------------------------------------------
void connectWiFi()
{
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
}

void connectMQTT()
{
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  while (!mqttClient.connected()) {
    if (mqttClient.connect("boat-telemetry")) {
      break;
    }
    delay(2000);
  }
}

String isoTimestamp()
{
  time_t now = time(nullptr);
  struct tm t;
  gmtime_r(&now, &t);
  char buf[25];
  strftime(buf, sizeof(buf), "%FT%TZ", &t);
  return String(buf);
}

void publishIMU()
{
  sensors_event_t accel, gyro, temp;
  bno.getEvent(&accel, Adafruit_BNO055::VECTOR_LINEARACCEL);
  bno.getEvent(&gyro, Adafruit_BNO055::VECTOR_GYROSCOPE);

  char payload[200];
  String ts = isoTimestamp();
  snprintf(payload, sizeof(payload),
           "{\"ax\":%.3f,\"ay\":%.3f,\"az\":%.3f,"
           "\"gx\":%.3f,\"gy\":%.3f,\"gz\":%.3f,"
           "\"ts\":\"%s\",\"seq\":%lu}",
           accel.acceleration.x, accel.acceleration.y, accel.acceleration.z,
           gyro.gyro.x, gyro.gyro.y, gyro.gyro.z,
           ts.c_str(), ++seq);
  mqttClient.publish("sensor/imu", payload);
}

void publishGPS()
{
  while (GPSSerial.available() > 0) {
    gps.encode(GPSSerial.read());
  }
  if (!gps.location.isValid())
    return;

  char payload[200];
  String ts = isoTimestamp();
  snprintf(payload, sizeof(payload),
           "{\"lat\":%.6f,\"lon\":%.6f,\"alt\":%.2f,\"speed\":%.2f,"
           "\"fix\":%d,\"ts\":\"%s\"}",
           gps.location.lat(), gps.location.lng(),
           gps.altitude.meters(), gps.speed.knots(),
           gps.satellites.value(), ts.c_str());
  mqttClient.publish("sensor/gps", payload);
}

void setup()
{
  Serial.begin(115200);
  connectWiFi();
  configTime(0, 0, "pool.ntp.org");
  connectMQTT();

  if (!bno.begin()) {
    Serial.println("Failed to initialize BNO055!\n");
    while (1)
      delay(10);
  }
  bno.setExtCrystalUse(true);

  GPSSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
}

void loop()
{
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  publishIMU();
  publishGPS();

  delay(100); // publish rate ~10 Hz
}

