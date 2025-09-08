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

| Topic | Emisor | Receptor | Contenido |
|-------|--------|----------|-----------|
| `sim/imu` | Simulador | ESP32 | Simulated IMU values |
| `sim/gps` | Simulador | ESP32 | Simulated GPS location |
| `sim/battery` | Simulador | ESP32 | Simulated Battery condition |
| `sensor/imu` | ESP32 | Estación | Re published IMU values from ESP32 |
| `sensor/gps` | ESP32 | Estación | Re published GPS location from ESP32 |
| `sensor/battery` | ESP32 | Estación | Re published Battery condition from ESP32 |
| `sensor/track` | Radar | Estación | Radar track detections |
| `sensor/radar` | Radar | Estación | Radar track list |
| `processed/radar` | Estación | Clientes | Processed radar tracks |

## Future plans

- Integrate onboard cameras for obstacle detection
- Add autonomous control for unmanned surface vehicle operation
- Provide a mission viewer for analysing completed runs
