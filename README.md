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

The project is split between onboard firmware, a containerized ground station, and several sensor simulators.

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
├─ ground/                        # ground station (processing and visualization)
│  ├─ app/                        # FastAPI services and business logic
│  │  ├─ config.py                # global parameters (IP, ports, battery curves…)
│  │  ├─ main.py                  # entry point: starts ingestion, estimation, and API
│  │  ├─ wiring.py                # “connection board”: shared instances (queue, services, state)
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
│  ├─ tests/                      # unit tests for services and utilities
│  ├─ requirements.txt            # Python dependencies
│  └─ Dockerfile                  # container definition
│
├─ docker-compose.yml             # orchestrates ground + simulators
└─ shared/                        # common definitions between boat and ground
   ├─ protocols/                  # JSON message formats, protocol constants
   └─ docs/                       # specification documentation, flow diagrams
```

## Running with Docker

Build and start the full environment (ground station plus simulators):

```bash
docker-compose up --build
```

This launches the ground station on port `8000` and separate containers for each simulator. Telemetry flows from the simulators to the ESP32 multiplexer simulator and finally to the ground station for processing and visualization.

### Running IMU simulator tests

The IMU simulator container can also execute its unit tests. Set the `RUN_TESTS` environment variable when starting the container to run the tests instead of the normal simulator application:

```bash
docker-compose run -e RUN_TESTS=1 imu_sim
```

Omitting `RUN_TESTS` (or setting it to any value other than `1`) runs the simulator normally.

## Future Plans

Long-term goals for the digital twin include:

- Adding onboard cameras for obstacle detection.
- Sending automated radio-control commands, turning the boat into a USV (Unmanned Surface Vehicle).
- Including a mission viewer to review completed runs.

This structure provides a foundation for further development of the digital twin and associated tooling.
