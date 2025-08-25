import json
import math
import os
import random
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

import paho.mqtt.client as mqtt

R_EARTH = 6371000.0


def _deg_per_meter_lat() -> float:
    return 180.0 / math.pi / R_EARTH


def _deg_per_meter_lon(lat: float) -> float:
    return 180.0 / math.pi / (R_EARTH * math.cos(math.radians(lat)))


def _distance_and_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R_EARTH * c
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return distance, bearing


@dataclass
class Track:
    lat: float
    lon: float
    heading: float
    speed: float

    def step(self, dt: float) -> None:
        dist = self.speed * dt
        lat_inc = dist * _deg_per_meter_lat() * math.cos(math.radians(self.heading))
        lon_inc = dist * _deg_per_meter_lon(self.lat) * math.sin(math.radians(self.heading))
        self.lat += lat_inc
        self.lon += lon_inc


class RadarSimulator:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.topic = "sensor/radar"
        self.freq = 1.0
        self.noise_prob = 0.0
        self.noise_m = 0.0
        self.origin_lat = 0.0
        self.origin_lon = 0.0
        self.tracks: List[Track] = []
        self._load_config()
        host = os.getenv("MQTT_HOST", "mosquitto")
        port = int(os.getenv("MQTT_PORT", "1883"))
        self.client = mqtt.Client()
        self.client.connect(host, port, 60)
        self.running = False

    def _load_config(self) -> None:
        with self.config_path.open() as fh:
            cfg = json.load(fh)
        self.topic = cfg.get("topic", "sensor/radar")
        self.freq = float(cfg.get("frequency_hz", 1.0))
        noise = cfg.get("noise", {})
        self.noise_prob = float(noise.get("probability", 0.0))
        self.noise_m = float(noise.get("position_m", 0.0))
        origin = cfg.get("origin", {})
        self.origin_lat = float(origin.get("lat", 0.0))
        self.origin_lon = float(origin.get("lon", 0.0))
        self.tracks = [
            Track(
                lat=float(t["lat"]),
                lon=float(t["lon"]),
                heading=float(t.get("heading", 0.0)),
                speed=float(t.get("speed", 0.0)),
            )
            for t in cfg.get("tracks", [])
        ]

    def _maybe_noisy(self, lat: float, lon: float) -> tuple[float, float]:
        if self.noise_prob <= 0.0 or self.noise_m <= 0.0:
            return lat, lon
        if random.random() > self.noise_prob:
            return lat, lon
        dx = random.uniform(-self.noise_m, self.noise_m)
        dy = random.uniform(-self.noise_m, self.noise_m)
        lat += dy * _deg_per_meter_lat()
        lon += dx * _deg_per_meter_lon(lat)
        return lat, lon

    def _build_message(self) -> str:
        tracks_msg = []
        for trk in self.tracks:
            lat, lon = self._maybe_noisy(trk.lat, trk.lon)
            distance, bearing = _distance_and_bearing(self.origin_lat, self.origin_lon, lat, lon)
            tracks_msg.append(
                {
                    "distance": distance,
                    "bearing": bearing,
                    "heading": trk.heading,
                }
            )
        return json.dumps({"tracks": tracks_msg})

    def start(self) -> None:
        self.running = True
        interval = 1.0 / self.freq if self.freq > 0 else 1.0
        while self.running:
            t0 = time.time()
            for trk in self.tracks:
                trk.step(interval)
            msg = self._build_message()
            self.client.publish(self.topic, msg)
            elapsed = time.time() - t0
            time.sleep(max(0.0, interval - elapsed))

    def stop(self) -> None:
        self.running = False
        self.client.disconnect()


def main() -> None:
    cfg = os.getenv("RADAR_SIM_CONFIG", "./simulators/radar_sim/config.json")
    sim = RadarSimulator(cfg)

    def _sig(*_):
        sim.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    sim.start()


if __name__ == "__main__":
    main()
