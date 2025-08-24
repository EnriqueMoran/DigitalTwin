# Digital Twin of RC Warship

This repository hosts the code and documentation for a digital twin of a radio-controlled warship replica.
The physical model measures **60.5 × 8.5 × 17 cm** and is equipped with sensors and communication hardware based on an ESP32 microcontroller.

The initial digital twin models the following parameters and systems:

- Roll
- Pitch
- Yaw
- Position
- Speed over water
- Battery autonomy
- Seabed depth map

The project is split between onboard firmware, a containerized HMI, and several sensor simulators.

```text
DigitalTwin/
├─ boat/                          # code running onboard (ESP32)
│  ├─ firmware/                   # Arduino/ESP-IDF sketches for ESP32
│  │  └─ telemetry.ino            # reads sensors and sends telemetry as JSON via WiFi/UDP
│  └─ docs/                       # wiring diagrams, sensor list, hardware notes
│
├─ simulators/                    # dockerized simulators
│  ├─ imu_sim/                    # IMU (roll, pitch, yaw, accel, gyro, mag)
│  ├─ gps_sim/                    # GPS (lat, lon, speed)
│  ├─ battery_sim/                # battery voltage/current curve
│  └─ esp32_sim/                  # collects sensors and forwards telemetry
│
├─ hmi/                           # human–machine interface (backend + frontend)
│  ├─ backend/                    # FastAPI backend services and API
│  └─ frontend/                   # React UI
│
├─ docker-compose.yml             # orchestrates HMI + simulators
└─ shared/                        # common definitions between boat and HMI
   ├─ protocols/                  # JSON message formats, protocol constants
   └─ docs/                       # specification documentation, flow diagrams
```

## Running with Docker

Build and start the full environment (HMI plus simulators):

```bash
docker-compose up --build
```

This launches the HMI backend on port `8001` and the frontend on `3000` alongside containers for each simulator. Telemetry flows from the simulators to the ESP32 multiplexer simulator and finally to the HMI for processing and visualization.

Build and start one single component:
```bash
docker compose up --build imu_sim
```



## Future Plans

Long-term goals for the digital twin include:

- Adding onboard cameras for obstacle detection.
- Sending automated radio-control commands, turning the boat into a USV (Unmanned Surface Vehicle).
- Including a mission viewer to review completed runs.

This structure provides a foundation for further development of the digital twin and associated tooling.
