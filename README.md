# Digital Twin of RC Warship

This repository contains a digital twin of a radio‑controlled warship. The physical craft (60.5 × 8.5 × 17 cm) is based on an ESP32 microcontroller with multiple sensors. The project mirrors that setup with containerised simulators, an MQTT broker and a web human–machine interface (HMI).

3D Model source: https://sketchfab.com/3d-models/type-055-renhai-class-destroyer-free-c0a3c5cb49fd4b688b65e4f3a18b5917

<img src="./hmi_example.gif" alt="App features" style="display:block; width:100%; height:auto; margin:0 auto;" />


## Features

- Battery discharge model and seabed depth map
- ESP32 telemetry multiplexer
- MQTT broker (Mosquitto)
- FastAPI backend with React frontend
- Dockerised sensor simulators (ESP32, MPU9250, NEO M8N)
- MQTT recorder with replay capability

## Repository structure

```text
DigitalTwin/
├─ boat/            ESP32 firmware and hardware documentation
├─ simulators/      sensor simulators and ESP32 multiplexer
├─ hmi/             FastAPI backend and React user interface
├─ mosquitto/       MQTT broker configuration
├─ mqtt_recorder/   recording and replay service
├─ shared/          protocol definitions shared by all components
└─ docker-compose.yml  orchestration for the full stack
```

## Requirements

- Docker 24+ with Docker Compose v2


## Quick start

Launch the entire system:

```bash
docker compose up --build
```

The backend is available at <http://localhost:8001> and the frontend at <http://localhost:3000>. Telemetry from the simulators flows through Mosquitto to the HMI for processing and visualisation.

Run a single service:

```bash
docker compose up --build imu_sim
```

## MQTT Topics

Below is a concise reference of topics, directions and message fields. Types are indicative.

- land/imu: IMU simulation control
  - Publisher: Station (backend/UI)
  - Subscriber: IMU simulator
  - QoS: 0
  - Fields:
    - amp: number (roll/pitch amplitude, degrees)
    - freq: number (oscillation frequency, Hz)
    - spike_prob: number (0–1 probability of spikes)
    - spike_amp: number (spike amplitude, degrees)
    - heading: number (base heading, degrees; negative disables yaw)
    - control: string (START | STOP)

- land/gps: GPS simulation control
  - Publisher: Station (backend/UI)
  - Subscriber: GPS simulator
  - QoS: 0
  - Fields:
    - lat: number (degrees)
    - lon: number (degrees)
    - hdg: number (course/heading, degrees)
    - spd: number (speed over ground, knots)
    - next_lat: number (degrees)
    - next_lon: number (degrees)
    - control: string (VECTOR | ROUTE | STOP)

- sim/imu: Simulated IMU values
  - Publisher: IMU simulator
  - Subscriber: ESP32 multiplexer
  - QoS: 0
  - Fields (required):
    - ax, ay, az: number (accelerometer, g)
    - gx, gy, gz: number (gyroscope, deg/s)
    - ts: string (ISO-8601 timestamp, UTC)
    - seq: integer (monotonic sequence)
  - Fields (optional):
    - mx, my, mz: number (magnetometer, µT)

- sim/gps: Simulated GPS location
  - Publisher: GPS simulator
  - Subscriber: ESP32 multiplexer
  - QoS: 1
  - Fields:
    - lat, lon: number (degrees)
    - alt: number (meters)
    - speed: number (knots)
    - fix: integer (GNSS fix quality)
    - hdop: number (horizontal dilution of precision)
    - sats_used: integer (satellites used in fix)
    - sats_in_view: integer (satellites in view)
    - ts: string (ISO-8601 timestamp, UTC)

- sim/battery: Simulated battery condition
  - Publisher: Battery simulator
  - Subscriber: ESP32 multiplexer
  - QoS: 1
  - Fields:
    - v: number (volts)
    - soc: number (state of charge, 0–1 or 0–100)
    - ts: string (ISO-8601 timestamp, UTC)

- sensor/imu: Re-published IMU values from ESP32
  - Publisher: ESP32 multiplexer
  - Subscriber: Station (backend)
  - QoS: 0
  - Fields: same as sim/imu

- sensor/gps: Re-published GPS values from ESP32
  - Publisher: ESP32 multiplexer
  - Subscriber: Station (backend)
  - QoS: 1
  - Fields: same as sim/gps (may include optional heading/cog in degrees)

- sensor/battery: Re-published battery values from ESP32
  - Publisher: ESP32 multiplexer
  - Subscriber: Station (backend)
  - QoS: 1
  - Fields: same as sim/battery

- sensor/track: Radar track detections
  - Publisher: Radar
  - Subscriber: Station (backend)
  - QoS: 0
  - Fields:
    - distance: number (meters)
    - bearing: number (degrees)
    - heading: number (degrees)

- sensor/radar: Radar track list
  - Publisher: Radar
  - Subscriber: Station (backend)
  - QoS: 0
  - Fields:
    - tracks: array of { distance: number, bearing: number, heading: number }

- processed/radar: Processed radar tracks
  - Publisher: Station (backend)
  - Subscriber: Clients (HMI)
  - QoS: 0
  - Fields: same as sensor/radar

- sensor/status: ESP32 status (WiFi, time)
  - Publisher: ESP32 multiplexer
  - Subscriber: Station (backend)
  - QoS: 0
  - Fields:
    - ts: string (ISO-8601 timestamp, UTC)
    - wifi_rssi: integer (dBm)
    - wifi_quality: string (Unavailable | Poor | Medium | High | Excellent)

## Future plans

- Integrate onboard cameras for obstacle detection
- Add autonomous control for unmanned surface vehicle operation
- Provide a mission viewer for analysing completed runs
