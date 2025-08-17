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

The project is split between onboard firmware and a ground station responsible for processing and visualization.

```
DigitalTwin/
├─ boat/                          # code running onboard (ESP32)
│  ├─ firmware/                   # Arduino/ESP-IDF sketches for ESP32
│  │  └─ telemetry.ino            # reads sensors and sends telemetry as JSON via WiFi/UDP
│  └─ docs/                       # wiring diagrams, sensor list, hardware notes
│
├─ ground/                        # ground station (processing and visualization)
│  ├─ app/
│  │  ├─ config.py                # global parameters (IP, ports, battery curves…)
│  │  ├─ main.py                  # entry point: starts ingestion, estimation, and API
│  │  ├─ wiring.py                # "connection board": shared instances (queue, services, state)
│  │  ├─ schemas.py               # Pydantic data models (raw Telemetry, processed State)
│  │  ├─ services/                # business logic (each ship system, but processed on ground)
│  │  │  ├─ ingest_udp.py         # receives telemetry from ESP32 over WiFi/UDP
│  │  │  ├─ state_estimator.py    # IMU/GPS fusion → roll, pitch, yaw, speed, heading
│  │  │  ├─ battery.py            # estimates SoC and autonomy from V/A
│  │  │  ├─ depth_mapper.py       # builds depth cloud/map with GPS+z points
│  │  │  └─ recorder.py           # saves telemetry/state into SQLite
│  │  ├─ api/
│  │  │  ├─ http.py               # FastAPI REST endpoints (e.g. /state)
│  │  │  └─ ws.py                 # WebSocket for live state streaming
│  │  └─ utils/
│  │     ├─ geo.py                # GPS → ENU (flat coordinate) conversions
│  │     └─ filters.py            # fusion algorithms (Madgwick/EKF, averages, EKF)
│  ├─ web/
│  │  ├─ index.html               # web interface (Three.js + data panels)
│  │  └─ app.js                   # JavaScript consuming API/WS and updating UI
│  ├─ scripts/
│  │  └─ replay.py                # replays a saved log → API (debug/replay)
│  ├─ simulations/
│  │  ├─ imu_sim.py               # generates roll/pitch/yaw test signals
│  │  ├─ gps_sim.py               # generates fake GPS paths
│  │  ├─ depth_sim.py             # simulates depth scans along a route
│  │  └─ battery_sim.py           # simulates voltage/current drain profiles
│  └─ tests/                      # unit tests for services and utilities
│
└─ shared/                        # common definitions between boat and ground
   ├─ protocols/                  # JSON message formats, protocol constants
   └─ docs/                       # specification documentation, flow diagrams
```

## Future Plans

Long-term goals for the digital twin include:

- Adding onboard cameras for obstacle detection.
- Sending automated radio-control commands, turning the boat into a USV (Unmanned Surface Vehicle).
- Including a mission viewer to review completed runs.

This structure provides a foundation for further development of the digital twin and associated tooling.
