import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np

# Conversion constant
MS_TO_KNOTS = 1.0 / 0.514444

# Default path to scenario file
DEFAULT_SCENARIO = Path(__file__).resolve().parent / "scenarios" / "main_scenario.json"


@dataclass
class WayPoint:
    lat: float
    lon: float
    speed: float  # m/s used until next waypoint


class ScenarioRoute:
    """Load a route scenario and provide motion information."""

    def __init__(self, path: Path = DEFAULT_SCENARIO):
        path = Path(path)
        if not path.is_absolute():
            path = (Path(__file__).resolve().parent / path).resolve()
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.wave_state = str(data.get("wave_state", "calm")).lower()
        pts = data.get("points", [])
        if not pts:
            raise ValueError("scenario must contain points")
        self.points: List[WayPoint] = [WayPoint(p["lat"], p["lon"], p.get("speed", 0.0)) for p in pts]

        # Pre-compute segments durations and bearings
        self.segments: List[dict] = []
        t = 0.0
        for i in range(len(self.points) - 1):
            p0 = self.points[i]
            p1 = self.points[i + 1]
            dist = self._distance(p0.lat, p0.lon, p1.lat, p1.lon)
            spd = max(p0.speed, 1e-6)
            dur = dist / spd
            bearing = self._bearing(p0.lat, p0.lon, p1.lat, p1.lon)
            seg = {
                "p0": p0,
                "p1": p1,
                "speed": spd,
                "bearing": bearing,
                "t0": t,
                "t1": t + dur,
            }
            self.segments.append(seg)
            t += dur
        self.total_time = t

        # Wave configuration
        self.wave_cfg = self._wave_config(self.wave_state)
        self._rng = random.Random(0)

    @staticmethod
    def _wave_config(state: str) -> dict:
        """Return wave configuration for a given state."""
        state = state.lower()
        cfgs = {
            "calm": {"amp": 0.5, "freq": 0.2, "spike_prob": 0.0, "spike_amp": 0.0},
            "choppy": {"amp": 10.0, "freq": 0.5, "spike_prob": 0.01, "spike_amp": 5.0},
            "moderate": {"amp": 15.0, "freq": 0.5, "spike_prob": 0.02, "spike_amp": 10.0},
            "rough": {"amp": 27.5, "freq": 0.7, "spike_prob": 0.05, "spike_amp": 15.0},
            "storm": {"amp": 45.0, "freq": 1.0, "spike_prob": 0.1, "spike_amp": 25.0},
        }
        return cfgs.get(state, cfgs["calm"])

    @staticmethod
    def _distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return haversine distance in metres."""
        R = 6371000.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @staticmethod
    def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return initial bearing from point 1 to point 2 in degrees (0..360)."""
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dlambda = math.radians(lon2 - lon1)
        y = math.sin(dlambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        brng = math.degrees(math.atan2(y, x))
        return (brng + 360.0) % 360.0

    def _segment_at(self, t: float) -> Tuple[dict, float]:
        if not self.segments:
            raise ValueError("scenario contains fewer than two points")
        if t >= self.total_time:
            seg = self.segments[-1]
            return seg, seg["t1"]
        for seg in self.segments:
            if seg["t0"] <= t < seg["t1"]:
                return seg, seg["t1"]
        return self.segments[-1], self.segments[-1]["t1"]

    def position(self, t: float) -> Tuple[float, float, float, float]:
        """Return (lat, lon, speed_m_s, course_deg) at time t."""
        seg, _ = self._segment_at(t)
        p0 = seg["p0"]
        p1 = seg["p1"]
        if t >= seg["t1"]:
            return p1.lat, p1.lon, 0.0, seg["bearing"]
        frac = (t - seg["t0"]) / max(seg["t1"] - seg["t0"], 1e-9)
        lat = p0.lat + frac * (p1.lat - p0.lat)
        lon = p0.lon + frac * (p1.lon - p0.lon)
        # Heading should always point toward the next waypoint from the current
        # interpolated position rather than staying constant for the entire
        # segment. Recompute bearing from the current position to the segment
        # end point so yaw continuously tracks the target waypoint.
        bearing = self._bearing(lat, lon, p1.lat, p1.lon)
        return lat, lon, seg["speed"], bearing

    def gps_motion(self, t: float) -> Tuple[float, float, float, float, float, float]:
        lat, lon, spd, bearing = self.position(t)
        return (
            lat,
            lon,
            0.0,
            spd * MS_TO_KNOTS,
            bearing,
            0.0,
        )

    @staticmethod
    def _euler_to_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        return np.array([
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ], dtype=float)

    def imu_motion(self, t: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (a_lin_world_ms2, omega_world_dps, R_world_to_sensor)."""
        _, _, _, yaw = self.position(t)
        yaw_rad = math.radians(yaw)

        amp = self.wave_cfg.get("amp", 0.0)
        freq = self.wave_cfg.get("freq", 0.5)
        roll = amp * math.sin(2 * math.pi * freq * t)
        pitch = (amp / 2.0) * math.sin(2 * math.pi * freq * t + math.pi / 2)

        # Optional spikes
        if self.wave_cfg.get("spike_prob", 0.0) > 0.0:
            if self._rng.random() < self.wave_cfg["spike_prob"]:
                roll += self.wave_cfg.get("spike_amp", 0.0) * (1 if self._rng.random() < 0.5 else -1)
                pitch += self.wave_cfg.get("spike_amp", 0.0) * (1 if self._rng.random() < 0.5 else -1)

        roll_rad = math.radians(roll)
        pitch_rad = math.radians(pitch)

        R = self._euler_to_matrix(roll_rad, pitch_rad, yaw_rad)

        # Angular rates (deg/s)
        roll_rate = amp * 2 * math.pi * freq * math.cos(2 * math.pi * freq * t)
        pitch_rate = (amp / 2.0) * 2 * math.pi * freq * math.cos(2 * math.pi * freq * t + math.pi / 2)
        omega = np.array([roll_rate, pitch_rate, 0.0], dtype=float)

        a_lin = np.zeros(3, dtype=float)
        return a_lin, omega, R
