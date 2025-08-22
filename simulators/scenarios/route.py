import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Waypoint:
    lat: float
    lon: float
    speed: float  # m/s


class Scenario:
    """Simple route scenario loaded from a JSON file."""

    def __init__(self, filename: str = "simulators/scenarios/main_scenario.json"):
        path = Path(filename)
        data = json.loads(path.read_text()) if path.exists() else {"points": []}
        self.wave_state: str = data.get("wave_state", "calm")
        pts = data.get("points", [])
        self.points = [Waypoint(**p) for p in pts] if pts else [Waypoint(0.0, 0.0, 0.0)]
        self._build_segments()

    # ------------------------------------------------------------------
    def _build_segments(self) -> None:
        self.segments: list[tuple] = []
        t = 0.0
        for i in range(len(self.points) - 1):
            p0, p1 = self.points[i], self.points[i + 1]
            dist = self._haversine(p0.lat, p0.lon, p1.lat, p1.lon)
            speed = p0.speed
            dur = dist / speed if speed > 0 else 0.0
            bearing = self._bearing(p0.lat, p0.lon, p1.lat, p1.lon)
            self.segments.append((t, t + dur, p0, p1, speed, bearing))
            t += dur
        self.total_time = t

    # ------------------------------------------------------------------
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6_371_000.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = phi2 - phi1
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dlambda = math.radians(lon2 - lon1)
        y = math.sin(dlambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
        brng = math.degrees(math.atan2(y, x))
        return (brng + 360.0) % 360.0

    # ------------------------------------------------------------------
    def state_at(self, t: float) -> tuple[float, float, float, float]:
        """Return (lat, lon, speed_m_s, heading_deg) at time ``t``."""
        if not self.segments:
            p = self.points[0]
            return p.lat, p.lon, 0.0, 0.0
        for start, end, p0, p1, speed, bearing in self.segments:
            if t <= end:
                frac = 0.0 if end - start <= 0 else (t - start) / (end - start)
                lat = p0.lat + (p1.lat - p0.lat) * frac
                lon = p0.lon + (p1.lon - p0.lon) * frac
                return lat, lon, speed, bearing
        # past the end -> stay at last point
        *_, last_p1, _, last_bearing = self.segments[-1][2:]
        return last_p1.lat, last_p1.lon, 0.0, last_bearing
