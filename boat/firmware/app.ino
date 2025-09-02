// ESP32 Boat Telemetry Firmware
// Reads MPU9250 (accel/gyro) over I2C and NEO-M8N GPS over UART,
// and publishes JSON telemetry to MQTT with the same schema as the simulators.

// --- Dependencies (install via Arduino Library Manager) ---
// - TinyGPSPlus by Mikal Hart
// - PubSubClient by Nick O'Leary
//
// Note: We build JSON manually without ArduinoJson to keep dependencies minimal.

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <PubSubClient.h>
#include <TinyGPSPlus.h>
#include <Wire.h>
#include <sys/time.h>


#ifndef WIFI_SSID
#define WIFI_SSID "YOUR_WIFI_SSID"
#endif
#ifndef WIFI_PASS
#define WIFI_PASS "YOUR_WIFI_PASSWORD"
#endif

// Set your MQTT broker (IP recommended for ESP32)
#ifndef MQTT_HOST
#define MQTT_HOST "192.168.1.100"
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif

// MQTT topics must match shared/mqtt_topics.json
static const char* TOPIC_SENSOR_IMU = "sensor/imu";
static const char* TOPIC_SENSOR_GPS = "sensor/gps";
static const char* TOPIC_STATUS     = "sensor/status";

// Device identity for MQTT client id
#ifndef DEVICE_ID
#define DEVICE_ID "esp32-boat"
#endif

// Pins
#ifndef I2C_SDA_PIN
#define I2C_SDA_PIN 21
#endif
#ifndef I2C_SCL_PIN
#define I2C_SCL_PIN 22
#endif

// GPS UART (use UART1)
#ifndef GPS_UART_NUM
#define GPS_UART_NUM 1
#endif
#ifndef GPS_RX_PIN
#define GPS_RX_PIN 16
#endif
#ifndef GPS_TX_PIN
#define GPS_TX_PIN 17
#endif
#ifndef GPS_BAUD
#define GPS_BAUD 9600
#endif

// IMU I2C address (MPU-9250 primary)
#ifndef MPU9250_ADDR
#define MPU9250_ADDR 0x68
#endif

// Publish rates configured in Hz (not ms)
#ifndef IMU_PUBLISH_HZ
#define IMU_PUBLISH_HZ 50.0f
#endif
#ifndef GPS_PUBLISH_HZ
#define GPS_PUBLISH_HZ 5.0f
#endif


WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
TinyGPSPlus gps;

#if GPS_UART_NUM == 1
HardwareSerial SerialGPS(1);
#elif GPS_UART_NUM == 2
HardwareSerial SerialGPS(2);
#else
#error "GPS_UART_NUM must be 1 or 2 for ESP32"
#endif

// Sequence counter for IMU publishes (required by schema)
volatile uint32_t imuSeq = 0;

// Timers (we compute current period from Hz on-the-fly each loop)
uint32_t lastImuPubMs = 0;
uint32_t lastGpsPubMs = 0;

// -------------- Utilities ---------------
static bool wifiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

static void iso8601_utc_now(char* out, size_t outLen) {
  // Format: YYYY-MM-DDTHH:MM:SS.mmmZ (UTC)
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  time_t now = tv.tv_sec;
  struct tm tm_utc;
  gmtime_r(&now, &tm_utc);
  char base[32];
  strftime(base, sizeof(base), "%Y-%m-%dT%H:%M:%S", &tm_utc);
  int ms = (int)(tv.tv_usec / 1000);
  snprintf(out, outLen, "%s.%03dZ", base, ms);
}

static void mqttPublishStatus(const char* status, bool retain) {
  char ts[32];
  iso8601_utc_now(ts, sizeof(ts));
  char payload[96];
  snprintf(payload, sizeof(payload), "{\"status\":\"%s\",\"ts\":\"%s\"}", status, ts);
  mqttClient.publish(TOPIC_STATUS, payload, retain);
}

static void connectWiFi() {
  if (wifiConnected()) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("WiFi connecting to %s", WIFI_SSID);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (wifiConnected()) {
    Serial.printf("WiFi connected: %s (IP %s)\n", WIFI_SSID, WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi connection failed");
  }
}

static void setupTimeNTP() {
  // Set time to UTC via NTP. If no internet, time may remain unset; we still publish ISO with whatever base we have.
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  // Try briefly to sync
  for (int i = 0; i < 20; ++i) {
    struct tm t;
    if (getLocalTime(&t, 100)) {
      Serial.println("NTP time synced");
      return;
    }
    delay(250);
  }
  Serial.println("NTP time sync not confirmed (continuing)");
}

static void ensureMqtt() {
  if (mqttClient.connected()) return;

  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  // Build LWT
  char willPayload[96];
  char ts[32];
  iso8601_utc_now(ts, sizeof(ts));
  snprintf(willPayload, sizeof(willPayload), "{\"status\":\"offline\",\"ts\":\"%s\"}", ts);

  // Attempt connect with LWT (qos=1, retain=true)
  Serial.printf("Connecting MQTT to %s:%d ...\n", MQTT_HOST, MQTT_PORT);
  if (mqttClient.connect(DEVICE_ID, nullptr, nullptr, TOPIC_STATUS, 1, true, willPayload, true)) {
    Serial.println("MQTT connected");
    mqttPublishStatus("online", true);
  } else {
    Serial.printf("MQTT connect failed, rc=%d\n", mqttClient.state());
  }
}

// -------------- MPU9250 low-level I2C --------------
namespace MPU9250 {
  static const uint8_t REG_PWR_MGMT_1   = 0x6B;
  static const uint8_t REG_SMPLRT_DIV   = 0x19;
  static const uint8_t REG_CONFIG       = 0x1A;
  static const uint8_t REG_GYRO_CONFIG  = 0x1B;
  static const uint8_t REG_ACCEL_CONFIG = 0x1C;
  static const uint8_t REG_ACCEL_CONFIG2= 0x1D;
  static const uint8_t REG_ACCEL_XOUT_H = 0x3B;
  static const uint8_t REG_GYRO_XOUT_H  = 0x43;

  static bool write8(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(MPU9250_ADDR);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
  }

  static bool readBytes(uint8_t reg, uint8_t* buf, size_t len) {
    Wire.beginTransmission(MPU9250_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false; // repeated start
    size_t n = Wire.requestFrom((int)MPU9250_ADDR, (int)len);
    if (n != len) return false;
    for (size_t i = 0; i < len; ++i) buf[i] = Wire.read();
    return true;
  }

  static bool init() {
    // Wake up device
    if (!write8(REG_PWR_MGMT_1, 0x00)) return false;
    delay(100);
    // Sample rate divider (Gyro/Accel base 1kHz when DLPF on): 1kHz/(1+7)=125Hz
    write8(REG_SMPLRT_DIV, 7);
    // DLPF config: set to 0x03 (~44/42 Hz) for ACC and ~42Hz for Gyro via CONFIG
    write8(REG_CONFIG, 0x03);
    // Gyro full-scale ±250 dps -> 0x00
    write8(REG_GYRO_CONFIG, 0x00);
    // Accel full-scale ±2g -> 0x00
    write8(REG_ACCEL_CONFIG, 0x00);
    // Accel DLPF cutoff ~44.8 Hz, enable DLPF (ACCEL_CONFIG2 A_DLPF_CFG=3, ACCEL_FCHOICE_B=0)
    write8(REG_ACCEL_CONFIG2, 0x03);
    delay(10);
    return true;
  }

  static inline int16_t to_i16(uint8_t hi, uint8_t lo) {
    return (int16_t)((hi << 8) | lo);
  }

  static bool readAccelGyro(float& ax_g, float& ay_g, float& az_g,
                            float& gx_dps, float& gy_dps, float& gz_dps) {
    uint8_t buf[14];
    if (!readBytes(REG_ACCEL_XOUT_H, buf, sizeof(buf))) return false;
    int16_t ax = to_i16(buf[0], buf[1]);
    int16_t ay = to_i16(buf[2], buf[3]);
    int16_t az = to_i16(buf[4], buf[5]);
    // buf[6], buf[7] are temp, ignored
    int16_t gx = to_i16(buf[8], buf[9]);
    int16_t gy = to_i16(buf[10], buf[11]);
    int16_t gz = to_i16(buf[12], buf[13]);

    // Convert to physical units
    // Accel: ±2g -> 16384 LSB/g
    ax_g = (float)ax / 16384.0f;
    ay_g = (float)ay / 16384.0f;
    az_g = (float)az / 16384.0f;
    // Gyro: ±250 dps -> 131 LSB/(°/s)
    gx_dps = (float)gx / 131.0f;
    gy_dps = (float)gy / 131.0f;
    gz_dps = (float)gz / 131.0f;
    return true;
  }
}

// -------------- Setup & Loop --------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println("\n[Boat Telemetry] Booting...");

  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, 400000);
  if (!MPU9250::init()) {
    Serial.println("MPU9250 init failed (check wiring)");
  } else {
    Serial.println("MPU9250 initialized");
  }

  // GPS UART init
  SerialGPS.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN, false);
  Serial.println("GPS UART initialized");

  connectWiFi();
  setupTimeNTP();
  ensureMqtt();

  // Log derived periods once for visibility
  uint32_t imuMs = (uint32_t)((1000.0f / IMU_PUBLISH_HZ) + 0.5f); if (imuMs == 0) imuMs = 1;
  uint32_t gpsMs = (uint32_t)((1000.0f / GPS_PUBLISH_HZ) + 0.5f); if (gpsMs == 0) gpsMs = 1;
  Serial.printf("IMU rate: %.2f Hz (%u ms) | GPS rate: %.2f Hz (%u ms)\n",
                (double)IMU_PUBLISH_HZ, imuMs, (double)GPS_PUBLISH_HZ, gpsMs);
}

static void publishIMU() {
  float ax_g = 0, ay_g = 0, az_g = 0;
  float gx_dps = 0, gy_dps = 0, gz_dps = 0;
  if (!MPU9250::readAccelGyro(ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps)) {
    return;
  }

  char ts[32];
  iso8601_utc_now(ts, sizeof(ts));

  // Build compact JSON
  // Required: ax, ay, az, gx, gy, gz, ts, seq
  char payload[256];
  uint32_t seq = imuSeq++;
  // Use 4-6 decimals for stability
  snprintf(payload, sizeof(payload),
           "{\"ax\":%.4f,\"ay\":%.4f,\"az\":%.4f,\"gx\":%.3f,\"gy\":%.3f,\"gz\":%.3f,\"ts\":\"%s\",\"seq\":%lu}",
           ax_g, ay_g, az_g, gx_dps, gy_dps, gz_dps, ts, (unsigned long)seq);

  mqttClient.publish(TOPIC_SENSOR_IMU, payload, false);
}

static void publishGPS() {
  if (!gps.location.isValid()) return;
  char ts[32];
  iso8601_utc_now(ts, sizeof(ts));

  double lat = gps.location.lat();
  double lon = gps.location.lng();
  double alt_m = gps.altitude.isValid() ? gps.altitude.meters() : NAN;
  double spd_kn = gps.speed.isValid() ? gps.speed.knots() : NAN;

  int fix = gps.location.isValid() ? (gps.altitude.isValid() ? 3 : 2) : 0;

  // Build JSON with optional fields only if valid
  String json = "{";
  json += "\"lat\":" + String(lat, 7) + ",";
  json += "\"lon\":" + String(lon, 7) + ",";
  if (!isnan(alt_m)) {
    json += "\"alt\":" + String(alt_m, 2) + ",";
  }
  if (!isnan(spd_kn)) {
    json += "\"speed\":" + String(spd_kn, 2) + ",";
  }
  json += "\"fix\":" + String(fix) + ",";
  json += "\"ts\":\"" + String(ts) + "\"";
  json += "}";

  mqttClient.publish(TOPIC_SENSOR_GPS, json.c_str(), false);
}

void loop() {
  // Keep connections
  if (!wifiConnected()) connectWiFi();
  ensureMqtt();
  mqttClient.loop();

  // Feed GPS parser
  while (SerialGPS.available() > 0) {
    gps.encode(SerialGPS.read());
  }

  // Compute current publish periods from Hz (allows changing macros without tracking ms)
  uint32_t nowMs = millis();
  uint32_t imuPeriodMsCur = (uint32_t)((1000.0f / IMU_PUBLISH_HZ) + 0.5f); if (imuPeriodMsCur == 0) imuPeriodMsCur = 1;
  uint32_t gpsPeriodMsCur = (uint32_t)((1000.0f / GPS_PUBLISH_HZ) + 0.5f); if (gpsPeriodMsCur == 0) gpsPeriodMsCur = 1;

  // Publish IMU at fixed rate
  if (nowMs - lastImuPubMs >= imuPeriodMsCur) {
    publishIMU();
    lastImuPubMs = nowMs;
  }

  // Publish GPS if updated and rate-limited
  if (gps.location.isUpdated()) {
    if (nowMs - lastGpsPubMs >= gpsPeriodMsCur) {
      publishGPS();
      lastGpsPubMs = nowMs;
    }
  }

  // Small sleep yields to WiFi/MQTT processing
  delay(1);
}
