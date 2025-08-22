"""Run a pre-defined simulation scenario.

This script publishes simulated GPS and IMU data based on a scenario described
in a JSON file under ``simulators/scenarios``.  The simulator data is published
on the MQTT topics ``sim/gps`` and ``sim/imu`` respectively.  An ``ESP32``
forwarder subscribes to these topics and republishes the messages to
``sensor/gps`` and ``sensor/imu`` mimicking the behaviour of the real ESP32
firmware.

The scenario and behaviour requirements are outlined in the repository task
instructions.  For simplicity the script selects the scenario internally rather
than via command line arguments.
"""

import json
import math
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

import paho.mqtt.client as mqtt

# Path to the scenario file bundled with the repository.  Change this value to
# switch scenarios.
SCENARIO_FILE = Path(__file__).resolve().parent.parent / "scenarios" / "sample.json"

# Mapping describing the typical motion characteristics for each sea state.
# The amplitudes are in degrees and frequencies are in Hertz and were derived
# from the specification provided in the task description.
WAVE_STATES: Dict[str, Dict[str, float]] = {
    "calm": {"amp": 1.0, "freq": 0.2},
    "choppy": {"amp": 10.0, "freq": 2.0},
    "moderate": {"amp": 15.0, "freq": 0.3},
    "rough": {"amp": 30.0, "freq": 1.0},
    "storm": {"amp": 45.0, "freq": 1.5},
}


def _iso_now() -> str:
    """Return the current timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance in metres between two geographic coordinates."""
    r = 6_371_000.0  # Earth radius in metres
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees from the start point to the end point."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


def _interp(p1: Dict[str, float], p2: Dict[str, float], f: float) -> Tuple[float, float]:
    """Linear interpolation between two latitude/longitude points."""
    lat = p1["lat"] + (p2["lat"] - p1["lat"]) * f
    lon = p1["lon"] + (p2["lon"] - p1["lon"]) * f
    return lat, lon


class ESP32Forwarder(threading.Thread):
    """Simple MQTT bridge that forwards simulator topics to sensor topics."""

    def __init__(self, host: str = "localhost", port: int = 1883):
        super().__init__(daemon=True)
        self._client = mqtt.Client()
        self._client.on_message = self._on_message
        self._host = host
        self._port = port
        self._stop = threading.Event()

    def _on_message(self, client, userdata, msg):
        if msg.topic == "sim/imu":
            client.publish("sensor/imu", msg.payload)
        elif msg.topic == "sim/gps":
            client.publish("sensor/gps", msg.payload)

    def run(self):
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.subscribe("sim/imu")
        self._client.subscribe("sim/gps")
        while not self._stop.is_set():
            self._client.loop(0.1)
        self._client.disconnect()

    def stop(self):
        self._stop.set()
        self.join()


def load_scenario(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_states(points: Iterable[Dict[str, float]], wave_cfg: Dict[str, float], dt: float = 1.0):
    """Yield successive (t, lat, lon, heading, roll, pitch) states."""
    t = 0.0
    for idx in range(len(points) - 1):
        start = points[idx]
        end = points[idx + 1]
        dist = _haversine(start["lat"], start["lon"], end["lat"], end["lon"])
        speed = start["speed"]
        if speed <= 0.0:
            continue
        dur = dist / speed
        heading = _bearing(start["lat"], start["lon"], end["lat"], end["lon"])
        steps = max(1, int(dur / dt))
        for step in range(steps):
            frac = min(step * dt / dur, 1.0)
            lat, lon = _interp(start, end, frac)
            amp = wave_cfg["amp"]
            freq = wave_cfg["freq"]
            roll = amp * math.sin(2 * math.pi * freq * t)
            pitch = amp * math.cos(2 * math.pi * freq * t)
            yield t, lat, lon, heading, roll, pitch
            t += dt
    # final point – boat stays with zero speed at last location
    last = points[-1]
    yield t, last["lat"], last["lon"], 0.0, 0.0, 0.0


def run():
    scenario = load_scenario(SCENARIO_FILE)
    wave_cfg = WAVE_STATES.get(scenario.get("wave_state", "calm"), WAVE_STATES["calm"])
    esp32 = ESP32Forwarder()
    esp32.start()

    client = mqtt.Client()
    client.connect("localhost", 1883, 60)

    seq = 0
    for t, lat, lon, heading, roll, pitch in generate_states(scenario["points"], wave_cfg):
        amp = wave_cfg["amp"]
        freq = wave_cfg["freq"]
        roll_rate = 2 * math.pi * freq * amp * math.cos(2 * math.pi * freq * t)
        pitch_rate = -2 * math.pi * freq * amp * math.sin(2 * math.pi * freq * t)

        imu_payload = {
            "ax": 0.0,
            "ay": 0.0,
            "az": 1.0,
            "gx": roll_rate,
            "gy": pitch_rate,
            "gz": 0.0,
            "ts": _iso_now(),
            "seq": seq,
        }
        gps_payload = {
            "lat": lat,
            "lon": lon,
            "ts": _iso_now(),
        }
        client.publish("sim/imu", json.dumps(imu_payload))
        client.publish("sim/gps", json.dumps(gps_payload))
        seq += 1
        time.sleep(1.0)

    esp32.stop()
    client.disconnect()


if __name__ == "__main__":
    run()
