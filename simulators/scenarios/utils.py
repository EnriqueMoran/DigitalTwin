import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

# Mapping describing the typical motion characteristics for each sea state.
WAVE_STATES: Dict[str, Dict[str, float]] = {
    "calm": {"amp": 1.0, "freq": 0.2},
    "choppy": {"amp": 10.0, "freq": 2.0},
    "moderate": {"amp": 15.0, "freq": 0.3},
    "rough": {"amp": 30.0, "freq": 1.0},
    "storm": {"amp": 45.0, "freq": 1.5},
}


def iso_now() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def load_scenario(path: Path) -> Dict:
    """Load a scenario JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great circle distance in metres between two geographic coordinates."""
    r = 6_371_000.0  # Earth radius in metres
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees from the start point to the end point."""
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360.0) % 360.0


def interp(p1: Dict[str, float], p2: Dict[str, float], f: float) -> Tuple[float, float]:
    """Linear interpolation between two latitude/longitude points."""
    lat = p1["lat"] + (p2["lat"] - p1["lat"]) * f
    lon = p1["lon"] + (p2["lon"] - p1["lon"]) * f
    return lat, lon


def generate_states(points: Iterable[Dict[str, float]], wave_cfg: Dict[str, float], dt: float = 1.0):
    """Yield successive (t, lat, lon, heading, roll, pitch) states."""
    t = 0.0
    for idx in range(len(points) - 1):
        start = points[idx]
        end = points[idx + 1]
        dist = haversine(start["lat"], start["lon"], end["lat"], end["lon"])
        speed = start["speed"]
        if speed <= 0.0:
            continue
        dur = dist / speed
        heading = bearing(start["lat"], start["lon"], end["lat"], end["lon"])
        steps = max(1, int(dur / dt))
        for step in range(steps):
            frac = min(step * dt / dur, 1.0)
            lat, lon = interp(start, end, frac)
            amp = wave_cfg["amp"]
            freq = wave_cfg["freq"]
            roll = amp * math.sin(2 * math.pi * freq * t)
            pitch = amp * math.cos(2 * math.pi * freq * t)
            yield t, lat, lon, heading, roll, pitch
            t += dt
    last = points[-1]
    yield t, last["lat"], last["lon"], 0.0, 0.0, 0.0
