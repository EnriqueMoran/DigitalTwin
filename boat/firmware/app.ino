#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <time.h>
#include <MPU9250.h>
#include <TinyGPSPlus.h>

// -------- Wi-Fi / MQTT --------
#define WIFI_SSID  ""
#define WIFI_PASS  ""
#define MQTT_HOST  "192.168.1.0"
#define MQTT_PORT  1883
#define TOPIC_IMU     "sensor/imu"
#define TOPIC_GPS     "sensor/gps"
#define TOPIC_STATUS  "sensor/status"

// -------- I2C / IMU --------
#define SDA_PIN 8
#define SCL_PIN 9

// -------- UART / GPS --------
#define GPS_RX_PIN 18
#define GPS_TX_PIN 17
#define GPS_BAUD   9600

// -------- Rates (ms) --------
const uint32_t IMU_PERIOD_MS = 10;   // 100 Hz
// GPS_PERIOD_MS = 0 -> publish as sentences arrive (no throttle)
// GPS_PERIOD_MS > 0 -> fixed-rate publish using last decoded data
uint32_t GPS_PERIOD_MS = 0;

// -------- IMU mag calibration --------
struct MagCal { float offsetX, offsetY, offsetZ, scaleX, scaleY, scaleZ; };
MagCal MAG = { -43.479370f, 7.986023f, -168.458771f, 1.050293f, 0.997966f, 0.956163f };

const float DECLINATION_RAD = 0.0f;
// Complementary filter time constant for yaw (seconds).
// Lower values => stronger magnetometer correction (faster pull to North).
// Example at 100 Hz (dt≈0.01s):
//   YAW_TAU_S=0.05 -> alpha≈0.83 (≈17% magnetometer)
//   YAW_TAU_S=0.02 -> alpha≈0.67 (≈33% magnetometer)
const float YAW_TAU_S = 0.05f;

MPU9250 mpu;
WiFiClient net;
PubSubClient mqtt(net);
HardwareSerial& GPS_PORT = Serial1;
TinyGPSPlus gps;

uint32_t seq = 0;
uint32_t lastImuSendMs = 0;
uint32_t lastGpsSendMs = 0;
uint32_t lastStatusSendMs = 0;

bool yaw_init = false;
float yaw_fused = 0.0f;

// -------- GPS cache (last decoded) --------
struct GpsCache {
  bool locValid=false, altValid=false, spdValid=false, crsValid=false, dopValid=false;
  double lat=NAN, lon=NAN, altm=NAN, sog_kn=NAN, sog_kmh=NAN, cog_deg=NAN, hdop=NAN;
  uint32_t sats=0;
  uint32_t lastUpdateMs=0; // when a sentence updated the cache
} GC;

String iso8601_utc(time_t t){
  char buf[32]; struct tm tm_utc; gmtime_r(&t,&tm_utc);
  strftime(buf,sizeof(buf),"%Y-%m-%dT%H:%M:%SZ",&tm_utc);
  return String(buf);
}

void wifiConnect(){
  WiFi.mode(WIFI_STA); WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status()!=WL_CONNECTED) delay(300);
  // Keep radio awake to avoid packet bursts caused by power-save batching
  WiFi.setSleep(false);
}
void mqttConnect(){
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  // Tuning to reduce blocking and handle larger JSON payloads smoothly
  mqtt.setKeepAlive(20);
  mqtt.setSocketTimeout(1);
  mqtt.setBufferSize(1024);
  while(!mqtt.connected()){
    String cid = "esp32-imu-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    mqtt.connect(cid.c_str());
    if(!mqtt.connected()) delay(800);
  }
}
void ensureTime(){
  configTime(0,0,"pool.ntp.org","time.nist.gov");
  for(int i=0;i<50 && time(nullptr)<1600000000;i++) delay(200);
}

static inline float wrap_pi(float a){
  while(a>= M_PI) a-=2.0f*M_PI;
  while(a<-M_PI) a+=2.0f*M_PI;
  return a;
}
static inline float wrap_2pi(float a){
  while(a>=2.0f*M_PI) a-=2.0f*M_PI;
  while(a< 0.0f)      a+=2.0f*M_PI;
  return a;
}

// -------- IMU publisher (100 Hz) --------
void publishIMU(){
  mpu.update();

  float ax_g=mpu.getAccX(), ay_g=mpu.getAccY(), az_g=mpu.getAccZ();
  const float G=9.80665f;
  float ax=ax_g*G, ay=ay_g*G, az=az_g*G;

  float gx_deg=mpu.getGyroX(), gy_deg=mpu.getGyroY(), gz_deg=mpu.getGyroZ();
  float gz = gz_deg * (float)M_PI / 180.0f;

  float mx_r=mpu.getMagX(), my_r=mpu.getMagY(), mz_r=mpu.getMagZ();
  float mx_c=(mx_r-MAG.offsetX)*MAG.scaleX;
  float my_c=(my_r-MAG.offsetY)*MAG.scaleY;
  float mz_c=(mz_r-MAG.offsetZ)*MAG.scaleZ;

  float roll  = atan2f(ay_g, az_g);
  float pitch = atanf(-ax_g / sqrtf(ay_g*ay_g + az_g*az_g));

  float mxh = mx_c*cosf(pitch) + my_c*sinf(roll)*sinf(pitch) + mz_c*cosf(roll)*sinf(pitch);
  float myh = my_c*cosf(roll) - mz_c*sinf(roll);
  float heading_mag = atan2f(myh, mxh);
  float heading_tc  = wrap_2pi(heading_mag + DECLINATION_RAD);

  static uint32_t lastMs = millis();
  uint32_t now = millis();
  float dt = (now - lastMs) / 1000.0f;
  if(dt<=0.0f) dt = IMU_PERIOD_MS/1000.0f;
  lastMs = now;

  if(!yaw_init){ yaw_fused=heading_tc; yaw_init=true; }
  else{
    float yaw_gyro = wrap_2pi(yaw_fused + (-gz)*dt);
    float e = wrap_pi(heading_tc - yaw_gyro);
    // Compute complementary filter alpha from desired time constant
    float alpha = YAW_TAU_S / (YAW_TAU_S + dt);
    if(alpha < 0.0f) alpha = 0.0f; if(alpha > 1.0f) alpha = 1.0f;
    yaw_fused = wrap_2pi(yaw_gyro + (1.0f - alpha)*e);
  }

  String ts = iso8601_utc(time(nullptr));

  StaticJsonDocument<512> doc;
  doc["ax"]=ax; doc["ay"]=ay; doc["az"]=az;
  doc["gx"]=gx_deg; doc["gy"]=gy_deg; doc["gz"]=gz_deg;
  doc["mx"]=mx_c; doc["my"]=my_c; doc["mz"]=mz_c;
  doc["heading"]=yaw_fused;
  doc["roll"]=roll; doc["pitch"]=pitch;
  doc["ts"]=ts; doc["seq"]=seq++; doc["rate_hz"]=100;

  char payload[640]; size_t n=serializeJson(doc,payload,sizeof(payload));
  // Stream publish to avoid reliance on PubSubClient internal buffer
  if (mqtt.beginPublish(TOPIC_IMU, n, false)) {
    mqtt.write((const uint8_t*)payload, n);
    mqtt.endPublish();
  }
}

// -------- GPS helpers --------
void updateGpsCacheFromTiny(){
  GC.locValid = gps.location.isValid();
  GC.altValid = gps.altitude.isValid();
  GC.spdValid = gps.speed.isValid();
  GC.crsValid = gps.course.isValid();
  GC.dopValid = gps.hdop.isValid();

  if(GC.locValid){ GC.lat=gps.location.lat(); GC.lon=gps.location.lng(); }
  if(GC.altValid){ GC.altm=gps.altitude.meters(); }
  if(GC.spdValid){ GC.sog_kn=gps.speed.knots(); GC.sog_kmh=gps.speed.kmph(); }
  if(GC.crsValid){ GC.cog_deg=gps.course.deg(); }
  if(GC.dopValid){ GC.hdop=gps.hdop.hdop(); }
  if(gps.satellites.isValid()) GC.sats=gps.satellites.value();

  GC.lastUpdateMs = millis();
}

void publishGPS_payload(){
  // Build payload from cache (require lat/lon fields per schema)
  String ts = iso8601_utc(time(nullptr));

  StaticJsonDocument<384> doc;
  if(GC.locValid){ doc["lat"]=GC.lat; doc["lon"]=GC.lon; }
  else {            doc["lat"]=0.0;   doc["lon"]=0.0;   }

  doc["ts"]=ts;
  if(GC.altValid) doc["alt"]=GC.altm;
  if(GC.spdValid) doc["speed"]=GC.sog_kn;  // knots
  if(GC.crsValid) doc["cog"]=GC.cog_deg;   // degrees
  if(GC.dopValid) doc["hdop"]=GC.hdop;
  // Satellites used (from GGA). Satellites in view (from GSV) not available here.
  if(GC.sats>0) doc["sats_used"]=GC.sats;
  // Provide a coarse fix quality: 0=no fix, 1=GNSS fix. We don't infer DGPS/RTK here.
  doc["fix"] = GC.locValid ? 1 : 0;

  char payload[512]; size_t n=serializeJson(doc,payload,sizeof(payload));
  if (mqtt.beginPublish(TOPIC_GPS, n, false)) {
    mqtt.write((const uint8_t*)payload, n);
    mqtt.endPublish();
  }
}

// -------- GPS publisher policies --------
void handleGPS(){
  // Always feed TinyGPS++ with all incoming bytes
  while(GPS_PORT.available()){
    char c = GPS_PORT.read();
    if(gps.encode(c)){                 // a full sentence just got parsed
      updateGpsCacheFromTiny();
      if(GPS_PERIOD_MS==0){            // as-it-arrives
        publishGPS_payload();
      }
    }
  }

  // If fixed-rate publishing is enabled, publish on schedule using last cache
  if(GPS_PERIOD_MS>0){
    uint32_t now = millis();
    if(now - lastGpsSendMs >= GPS_PERIOD_MS){
      if(GC.lastUpdateMs!=0) publishGPS_payload();
      lastGpsSendMs = now;
    }
  }
}

// -------- Setup / Loop --------
void setup(){
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);
  wifiConnect(); mqttConnect(); ensureTime();

  if(!mpu.setup(0x68)){
    Serial.println("[MPU] not detected"); while(1) delay(1000);
  }
  GPS_PORT.begin(GPS_BAUD, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
}

void loop(){
  if(!mqtt.connected()) mqttConnect();
  mqtt.loop();

  uint32_t now = millis();
  if(now - lastImuSendMs >= IMU_PERIOD_MS){
    publishIMU();
    lastImuSendMs = now;
  }

  handleGPS();

  // Cooperative yield; does not throttle scheduled publishing
  delay(1);

  // Periodic status (WiFi) publish ~ 1 Hz
  uint32_t now2 = millis();
  if(now2 - lastStatusSendMs >= 1000){
    lastStatusSendMs = now2;
    long rssi = (WiFi.status()==WL_CONNECTED) ? WiFi.RSSI() : -127;
    const char* qual = "Unavailable";
    if(WiFi.status()==WL_CONNECTED){
      if(rssi >= -55) qual = "Excellent";
      else if(rssi >= -65) qual = "High";
      else if(rssi >= -72) qual = "Medium";
      else if(rssi >= -82) qual = "Poor";
      else qual = "Unavailable";
    }
    String ts = iso8601_utc(time(nullptr));
    StaticJsonDocument<192> doc;
    doc["ts"] = ts;
    doc["wifi_rssi"] = rssi;  // dBm
    doc["wifi_quality"] = qual; // Unavailable|Poor|Medium|High|Excellent
    char payload[256]; size_t n=serializeJson(doc,payload,sizeof(payload));
    if (mqtt.beginPublish(TOPIC_STATUS, n, false)) {
      mqtt.write((const uint8_t*)payload, n);
      mqtt.endPublish();
    }
  }
}
