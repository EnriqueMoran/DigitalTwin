import asyncio
import base64
import json
import os
import time
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt, pi, isfinite, degrees
from pathlib import Path
from typing import Dict, Any, Set, Optional, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sensor and system state
STATE: Dict[str, Any] = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "heading": None,
    "roll": None,
    "pitch": None,
    "cog": None,
    "estimated_speed": None,
    "estimated_speed_confidence": None,
    "true_speed": None,
    "rate_of_turn": None,
    "imu_temperature": None,
    "latency": None,
    "battery_status": None,
    # GPS & connectivity
    "gps_signal": None,
    "gps_fix_quality": None,
    "hdop": None,
    "sats_used": None,
    "sats_in_view": None,
    "avg_snr": None,
    # WiFi
    "wifi_quality": None,
    "wifi_rssi": None,
    "uptime": None,
    "radar_tracks": [],
}

# Explicit sensor and system state machines
SENSOR_STATES: Dict[str, str] = {"imu": "Not initialized", "gps": "Not initialized"}
SYSTEM_STATE: str = "Initializing"

# Track validity from last real (sensor/*) message for each sensor
_IMU_LAST_VALID: Optional[bool] = None
_GPS_LAST_VALID: Optional[bool] = None

# Baselines captured when simulation starts, to optionally restore on stop
_BASELINE_STATE: Dict[str, Optional[str]] = {"imu": None, "gps": None}
_BASELINE_LAST_TS: Dict[str, Optional[float]] = {"imu": None, "gps": None}

LAST_MESSAGE_TIME: float | None = None
# Track last time we received data from ESP32 (sensor/* topics)
ESP32_LAST_MESSAGE_TIME: float | None = None
# Per-sensor last times from ESP32 sensor/* topics only
SENSOR_IMU_LAST_TIME: float | None = None
SENSOR_GPS_LAST_TIME: float | None = None
WEBSOCKETS: Set[WebSocket] = set()
MQTT_CLIENT: mqtt.Client | None = None
EVENT_LOOP: asyncio.AbstractEventLoop | None = None
_last_broadcast: float = 0.0
# Service start time (monotonic) to compute uptime
_service_start_monotonic: float = time.monotonic()
_last_processed: float = 0.0
_esp32_start_monotonic: float | None = None

# Simulation gating flags: when True, ignore real sensor/* for that sensor
SIM_GPS_ACTIVE: bool = False
SIM_IMU_ACTIVE: bool = False

# Fixed heading offset for real IMU (sensor/*), radians
IMU_HEADING_OFFSET_RAD: float = - (pi / 2)  # -90 degrees
# Mirror E/W for real IMU if sensor axes produce opposite yaw handedness
IMU_MIRROR_EAST_WEST: bool = True

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

TOPICS_FILE = Path("/app/backend/shared/mqtt_topics.json")
with open(TOPICS_FILE) as f:
    _topics = json.load(f)["topics"]
SENSOR_TOPICS = [t for t in _topics if t.startswith("sensor/")]
LEGACY_TOPICS = [t for t in _topics if t.startswith("sim/")]
PROCESSED_TOPICS = [t for t in _topics if t.startswith("processed/")]
TOPIC_SENSOR_GPS = next(t for t in SENSOR_TOPICS if t.endswith("/gps"))
TOPIC_SENSOR_IMU = next(t for t in SENSOR_TOPICS if t.endswith("/imu"))
TOPIC_SENSOR_BATTERY = next(t for t in SENSOR_TOPICS if t.endswith("/battery"))
TOPIC_SENSOR_TRACK = next((t for t in SENSOR_TOPICS if t.endswith("/track")), None)
TOPIC_SENSOR_RADAR = next((t for t in SENSOR_TOPICS if t.endswith("/radar")), None)
TOPIC_SIM_GPS = next(t for t in LEGACY_TOPICS if t.endswith("/gps"))
TOPIC_SIM_IMU = next(t for t in LEGACY_TOPICS if t.endswith("/imu"))
TOPIC_SIM_BATTERY = next(t for t in LEGACY_TOPICS if t.endswith("/battery"))
TOPIC_PROCESSED_RADAR = next((t for t in PROCESSED_TOPICS if t.endswith("/radar")), None)

_prev_gps: Dict[str, Any] | None = None
_prev_imu_ts: float | None = None
_est_velocity: float = 0.0
_est_heading: float = 0.0
_radar_tracks_internal: list[Dict[str, Any]] = []

TRACK_DISTANCE_MAX = 5.0
TRACK_BEARING_MAX = 5.0
TRACK_HEADING_MAX = 5.0
TRACK_TIMEOUT = 5.0

# Shared directory where recordings will be stored/read
SHARED_DIR = Path("/app/backend/shared/recordings")

# Recording state
RECORDING_ACTIVE: bool = False
RECORDING_PAUSED: bool = False
RECORDING_TOPICS: Optional[List[str]] = None  # None => all
RECORDING_BUFFER: List[Dict[str, Any]] = []
RECORDING_FILE: Optional[Path] = None
RECORDING_START_TS: Optional[float] = None
RECORDING_COUNT: int = 0

# Replay state
REPLAY_ACTIVE: bool = False
REPLAY_PAUSED: bool = False
REPLAY_TOPICS: Optional[List[str]] = None  # None => all
REPLAY_FILE: Optional[Path] = None
REPLAY_TASK: Optional[asyncio.Task] = None
REPLAY_START_MONO: Optional[float] = None
REPLAY_BASE_TS: Optional[float] = None
REPLAY_MESSAGES: List[Dict[str, Any]] = []
REPLAY_COUNT: int = 0
REPLAY_IDX: int = 0


def _update_radar_track(distance: float, bearing: float, heading: float) -> None:
    now = time.time()
    for trk in _radar_tracks_internal:
        if (
            abs(trk["distance"] - distance) <= TRACK_DISTANCE_MAX
            and abs(trk["bearing"] - bearing) <= TRACK_BEARING_MAX
            and abs(trk["heading"] - heading) <= TRACK_HEADING_MAX
        ):
            trk.update({"distance": distance, "bearing": bearing, "heading": heading, "last_seen": now})
            break
    else:
        _radar_tracks_internal.append(
            {"distance": distance, "bearing": bearing, "heading": heading, "last_seen": now}
        )
    _radar_tracks_internal[:] = [t for t in _radar_tracks_internal if now - t["last_seen"] <= TRACK_TIMEOUT]
    STATE["radar_tracks"] = [
        {"distance": t["distance"], "bearing": t["bearing"], "heading": t["heading"]}
        for t in _radar_tracks_internal
    ]


def _parse_ts(ts: str | None) -> float:
    if not ts:
        return time.time()
    try:
        s = str(ts)
        # Support trailing 'Z' (UTC) by converting to +00:00 offset for fromisoformat
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return time.time()


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = radians(lat1), radians(lat2)
    dlambda = radians(lon2 - lon1)
    x = sin(dlambda) * cos(phi2)
    y = cos(phi1) * sin(phi2) - sin(phi1) * cos(phi2) * cos(dlambda)
    b = atan2(x, y)
    return (b + 2 * 3.141592653589793) % (2 * 3.141592653589793)


def _wrap2pi(a: float) -> float:
    return a % (2 * pi)


def _on_connect(client: mqtt.Client, userdata, flags, rc):
    for t in SENSOR_TOPICS + LEGACY_TOPICS + PROCESSED_TOPICS:
        client.subscribe(t)


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
    global LAST_MESSAGE_TIME, ESP32_LAST_MESSAGE_TIME, SENSOR_IMU_LAST_TIME, SENSOR_GPS_LAST_TIME
    global _prev_gps, _prev_imu_ts, _est_velocity, _last_processed, _est_heading
    global _IMU_LAST_VALID, _GPS_LAST_VALID, SENSOR_STATES
    # Process every incoming message; broadcast loop already throttles WS output
    now = time.monotonic()
    _last_processed = now
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        return
    LAST_MESSAGE_TIME = time.time()

    # Recording hook: capture raw payload and topic
    global RECORDING_ACTIVE, RECORDING_PAUSED, RECORDING_TOPICS, RECORDING_BUFFER, RECORDING_COUNT
    if RECORDING_ACTIVE and not RECORDING_PAUSED:
        try:
            if (not RECORDING_TOPICS) or (msg.topic in set(RECORDING_TOPICS)):
                RECORDING_BUFFER.append({
                    "timestamp": time.time(),
                    "topic": msg.topic,
                    "payload": base64.b64encode(msg.payload).decode("utf-8"),
                })
                RECORDING_COUNT += 1
        except Exception:
            pass

    if topic in (TOPIC_SENSOR_GPS, TOPIC_SIM_GPS):
        # Gate GPS source: when sim active, ignore real sensor/*; when not active, ignore sim/*
        if (topic == TOPIC_SENSOR_GPS and SIM_GPS_ACTIVE) or (topic == TOPIC_SIM_GPS and not SIM_GPS_ACTIVE):
            return
        # If this is a sensor/* GPS message, mark ESP32 last seen
        if topic == TOPIC_SENSOR_GPS:
            ESP32_LAST_MESSAGE_TIME = time.time()
            SENSOR_GPS_LAST_TIME = ESP32_LAST_MESSAGE_TIME
        lat = payload.get("lat")
        lon = payload.get("lon")
        alt = payload.get("alt")
        spd_knots = payload.get("speed")
        # Optional heading and COG (degrees) from GPS. Use these when available
        # to avoid noisy bearing estimates from position noise.
        # Convert to radians to keep internal units consistent.
        heading_deg = payload.get("heading")
        cog_deg = payload.get("cog")
        ts = _parse_ts(payload.get("ts"))
        STATE["latitude"] = lat
        STATE["longitude"] = lon
        STATE["altitude"] = alt
        # GPS signal metadata
        STATE["gps_signal"] = payload.get("fix")
        STATE["gps_fix_quality"] = payload.get("fix")
        if (hd := payload.get("hdop")) is not None:
            try:
                STATE["hdop"] = float(hd)
            except Exception:
                pass
        if (su := payload.get("sats_used")) is not None:
            try:
                STATE["sats_used"] = int(su)
            except Exception:
                pass
        if (sv := payload.get("sats_in_view")) is not None:
            try:
                STATE["sats_in_view"] = int(sv)
            except Exception:
                pass
        spd = spd_knots * 0.514444 if spd_knots is not None else None
        STATE["true_speed"] = spd
        try:
            STATE["latency"] = max(0.0, float(LAST_MESSAGE_TIME - ts))
        except Exception:
            pass
        if heading_deg is not None:
            try:
                STATE["heading"] = radians(float(heading_deg))
            except Exception:
                pass
        if cog_deg is not None:
            try:
                STATE["cog"] = radians(float(cog_deg))
            except Exception:
                pass

        if _prev_gps:
            dt = ts - _prev_gps["ts"]
            if dt > 0:
                dist = _haversine(_prev_gps["lat"], _prev_gps["lon"], lat, lon)
                if cog_deg is None:
                    STATE["cog"] = _bearing(_prev_gps["lat"], _prev_gps["lon"], lat, lon)
                if spd is None:
                    STATE["true_speed"] = dist / dt
        _prev_gps = {"lat": lat, "lon": lon, "ts": ts}

        # Update GPS sensor state/validity only for real sensor data
        if topic == TOPIC_SENSOR_GPS:
            # Valid when lat/lon are finite and non-zero AND required metadata present
            def _is_num(x):
                try:
                    return isinstance(x, (int, float)) and isfinite(float(x))
                except Exception:
                    return False
            lat_ok = _is_num(lat) and float(lat) != 0.0
            lon_ok = _is_num(lon) and float(lon) != 0.0
            have_fix = (payload.get("fix") is not None)
            have_hdop = (payload.get("hdop") is not None)
            have_su = (payload.get("sats_used") is not None)
            # 'sats_in_view' is optional; ignore for validity
            valid = lat_ok and lon_ok and have_fix and have_hdop and have_su
            _GPS_LAST_VALID = valid
            SENSOR_STATES["gps"] = "Running" if valid else "Degraded"

    elif topic in (TOPIC_SENSOR_IMU, TOPIC_SIM_IMU):
        # Gate IMU source similarly
        if (topic == TOPIC_SENSOR_IMU and SIM_IMU_ACTIVE) or (topic == TOPIC_SIM_IMU and not SIM_IMU_ACTIVE):
            return
        # If this is a sensor/* IMU message, mark ESP32 last seen
        if topic == TOPIC_SENSOR_IMU:
            ESP32_LAST_MESSAGE_TIME = time.time()
            SENSOR_IMU_LAST_TIME = ESP32_LAST_MESSAGE_TIME
        ax = payload.get("ax")
        ay = payload.get("ay")
        az = payload.get("az")
        gx = payload.get("gx")
        gy = payload.get("gy")
        gz = payload.get("gz")
        if gx is not None:
            gx = radians(gx)
        if gy is not None:
            gy = radians(gy)
        if gz is not None:
            gz = radians(gz)
        mx = payload.get("mx")
        my = payload.get("my")
        mz = payload.get("mz")
        ts = _parse_ts(payload.get("ts"))

        if ax is not None and ay is not None and az is not None:
            STATE["roll"] = -atan2(ay, az)
            STATE["pitch"] = -atan2(-ax, sqrt(ay * ay + az * az))
        STATE["rate_of_turn"] = gz
        if _prev_imu_ts is not None:
            dt = ts - _prev_imu_ts
            if dt > 0:
                if ax is not None and ay is not None and az is not None:
                    g = 9.80665
                    roll = STATE.get("roll") or 0.0
                    pitch = STATE.get("pitch") or 0.0
                    gx_s = -g * sin(pitch)
                    ax_lin = ax - gx_s
                    # Integrate forward (body x) acceleration
                    _est_velocity += ax_lin * dt
                    STATE["estimated_speed"] = _est_velocity
                    STATE["estimated_speed_confidence"] = 100.0
                if gz is not None:
                    _est_heading = (_est_heading - gz * dt) % (2 * pi)
        _prev_imu_ts = ts
        if (
            mx is not None
            and my is not None
            and mz is not None
            and STATE["roll"] is not None
            and STATE["pitch"] is not None
        ):
            roll = STATE["roll"]
            pitch = STATE["pitch"]
            heading_tc = atan2(
                my * cos(roll) - mz * sin(roll),
                mx * cos(pitch)
                + my * sin(roll) * sin(pitch)
                + mz * cos(roll) * sin(pitch),
            )
            STATE["heading"] = heading_tc % (2 * pi)
        else:
            STATE["heading"] = _est_heading

        # Apply heading corrections only for real IMU messages
        if topic == TOPIC_SENSOR_IMU and STATE["heading"] is not None:
            try:
                h = _wrap2pi(STATE["heading"] + IMU_HEADING_OFFSET_RAD)
                if IMU_MIRROR_EAST_WEST:
                    h = _wrap2pi(-h)  # swap E/W while keeping N/S
                STATE["heading"] = h
            except Exception:
                pass
        try:
            STATE["latency"] = max(0.0, float(LAST_MESSAGE_TIME - ts))
        except Exception:
            pass

        # Update IMU sensor state/validity only for real sensor data
        if topic == TOPIC_SENSOR_IMU:
            valid_vals = [ax, ay, az, gx, gy, gz]
            valid = all(
                (v is not None and isinstance(v, (int, float)) and isfinite(float(v)))
                for v in valid_vals
            )
            _IMU_LAST_VALID = valid
            SENSOR_STATES["imu"] = "Running" if valid else "Degraded"

    elif topic in (TOPIC_SENSOR_BATTERY, TOPIC_SIM_BATTERY):
        # If this is a sensor/* Battery message, mark ESP32 last seen
        if topic == TOPIC_SENSOR_BATTERY:
            ESP32_LAST_MESSAGE_TIME = time.time()
        soc = payload.get("soc")
        if soc is not None:
            if soc <= 1:
                soc *= 100.0
            STATE["battery_status"] = soc
        ts = _parse_ts(payload.get("ts"))
        try:
            STATE["latency"] = max(0.0, float(LAST_MESSAGE_TIME - ts))
        except Exception:
            pass

    elif topic == "sensor/status":
        ts = _parse_ts(payload.get("ts"))
        # WiFi signal
        try:
            STATE["wifi_rssi"] = int(payload.get("wifi_rssi"))
        except Exception:
            pass
        wq = payload.get("wifi_quality")
        if isinstance(wq, str):
            STATE["wifi_quality"] = wq
        STATE["latency"] = LAST_MESSAGE_TIME - ts

    elif TOPIC_SENSOR_TRACK and topic == TOPIC_SENSOR_TRACK:
        dist = payload.get("distance")
        bear = payload.get("bearing")
        head = payload.get("heading")
        if dist is not None and bear is not None and head is not None:
            _update_radar_track(float(dist), float(bear), float(head))

    elif (
        (TOPIC_SENSOR_RADAR and topic == TOPIC_SENSOR_RADAR)
        or (TOPIC_PROCESSED_RADAR and topic == TOPIC_PROCESSED_RADAR)
    ):
        tracks = payload if isinstance(payload, list) else payload.get("tracks")
        if isinstance(tracks, list):
            now_t = time.time()
            _radar_tracks_internal[:] = [
                {
                    "distance": float(t.get("distance", 0)),
                    "bearing": float(t.get("bearing", 0)),
                    "heading": float(t.get("heading", 0)),
                    "last_seen": now_t,
                }
                for t in tracks
            ]
            STATE["radar_tracks"] = [
                {"distance": t["distance"], "bearing": t["bearing"], "heading": t["heading"]}
                for t in _radar_tracks_internal
            ]

async def _broadcast_loop():
    global _last_broadcast, _esp32_start_monotonic, SYSTEM_STATE
    while True:
        now = time.monotonic()
        if now - _last_broadcast >= 0.1:
            _last_broadcast = now
            # Service uptime should be monotonic and independent of ESP32 connectivity
            try:
                STATE["uptime"] = int(max(0, time.monotonic() - _service_start_monotonic))
            except Exception:
                pass

            # Update time-based availability for sensors when not simulated
            now_sec = time.time()
            if not SIM_IMU_ACTIVE:
                if SENSOR_IMU_LAST_TIME is None:
                    # Remains Not initialized until first real data arrives
                    pass
                elif now_sec - SENSOR_IMU_LAST_TIME > 10:
                    SENSOR_STATES["imu"] = "Unavailable"
            else:
                SENSOR_STATES["imu"] = "Simulated"

            if not SIM_GPS_ACTIVE:
                if SENSOR_GPS_LAST_TIME is None:
                    pass
                elif now_sec - SENSOR_GPS_LAST_TIME > 10:
                    SENSOR_STATES["gps"] = "Unavailable"
            else:
                SENSOR_STATES["gps"] = "Simulated"

            # Compute system state
            if SIM_IMU_ACTIVE or SIM_GPS_ACTIVE:
                SYSTEM_STATE = "Simulation"
            else:
                # If ESP32 connectivity lost for >10s (after having seen it), mark system Unavailable
                if ESP32_LAST_MESSAGE_TIME is not None and (now_sec - ESP32_LAST_MESSAGE_TIME > 10):
                    SYSTEM_STATE = "Unavailable"
                else:
                    imu_state = SENSOR_STATES.get("imu", "Not initialized")
                    gps_state = SENSOR_STATES.get("gps", "Not initialized")
                    both_not_init = imu_state == "Not initialized" and gps_state == "Not initialized"
                    both_running = imu_state == "Running" and gps_state == "Running"
                    if both_not_init:
                        SYSTEM_STATE = "Initializing"
                    elif both_running:
                        SYSTEM_STATE = "OK"
                    else:
                        # As long as not both Not initialized
                        SYSTEM_STATE = "Degraded"

            # Snapshot data to send, include per-sensor last times from sensor/* only
            data = {
                "sensors": STATE,
                "last_message_time": LAST_MESSAGE_TIME,
                "system_state": SYSTEM_STATE,
                "sensor_states": {
                    "imu": SENSOR_STATES.get("imu"),
                    "gps": SENSOR_STATES.get("gps"),
                },
                "sensor_last": {
                    "imu": SENSOR_IMU_LAST_TIME,
                    "gps": SENSOR_GPS_LAST_TIME,
                },
            }

            # Send concurrently to avoid one slow client blocking others
            sockets = list(WEBSOCKETS)
            if sockets:
                results = await asyncio.gather(
                    *(ws.send_json(data) for ws in sockets),
                    return_exceptions=True,
                )
                for ws, res in zip(sockets, results):
                    if isinstance(res, Exception):
                        try:
                            WEBSOCKETS.discard(ws)
                        except Exception:
                            pass
        await asyncio.sleep(0.01)


def _sanitize_filename(name: str) -> str:
    # Replace spaces and disallow path separators
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name.strip())
    if not safe:
        safe = "recording"
    if not safe.lower().endswith(".json"):
        safe += ".json"
    return safe


@app.get("/topics")
async def list_topics() -> Dict[str, Any]:
    return {"topics": list(_topics.keys())}


@app.get("/recordings")
async def list_recordings() -> Dict[str, Any]:
    try:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        files = [p.name for p in SHARED_DIR.glob("*.json") if p.is_file()]
    except Exception:
        files = []
    return {"files": sorted(files)}


@app.get("/recording/status")
async def recording_status() -> Dict[str, Any]:
    return {
        "active": RECORDING_ACTIVE,
        "paused": RECORDING_PAUSED,
        "count": RECORDING_COUNT,
        "file": str(RECORDING_FILE) if RECORDING_FILE else None,
        "topics": RECORDING_TOPICS or [],
        "started_at": RECORDING_START_TS,
    }


@app.post("/recording/start")
async def recording_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    global RECORDING_ACTIVE, RECORDING_PAUSED, RECORDING_BUFFER, RECORDING_FILE, RECORDING_TOPICS
    global RECORDING_START_TS, RECORDING_COUNT
    name = str(payload.get("filename", "recording")).strip()
    topics = payload.get("topics")
    topics_list = None
    if isinstance(topics, list) and topics:
        topics_list = [str(t) for t in topics]
    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    fname = _sanitize_filename(name)
    RECORDING_FILE = SHARED_DIR / fname
    RECORDING_BUFFER = []
    RECORDING_TOPICS = topics_list
    RECORDING_START_TS = time.time()
    RECORDING_COUNT = 0
    RECORDING_ACTIVE = True
    RECORDING_PAUSED = False
    return {"status": "ok", "file": RECORDING_FILE.name}


@app.post("/recording/pause")
async def recording_pause() -> Dict[str, str]:
    global RECORDING_PAUSED
    if RECORDING_ACTIVE:
        RECORDING_PAUSED = True
    return {"status": "ok"}


@app.post("/recording/resume")
async def recording_resume() -> Dict[str, str]:
    global RECORDING_PAUSED
    if RECORDING_ACTIVE:
        RECORDING_PAUSED = False
    return {"status": "ok"}


@app.post("/recording/stop")
async def recording_stop() -> Dict[str, Any]:
    global RECORDING_ACTIVE, RECORDING_BUFFER, RECORDING_FILE
    if not RECORDING_ACTIVE:
        return {"status": "ok", "file": None, "count": 0}
    try:
        data = list(RECORDING_BUFFER)
        with RECORDING_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f)
        count = len(data)
    except Exception:
        count = 0
    finally:
        RECORDING_ACTIVE = False
        RECORDING_BUFFER = []
        file_name = RECORDING_FILE.name if RECORDING_FILE else None
        RECORDING_FILE = None
    return {"status": "ok", "file": file_name, "count": count}


async def _replay_runner():
    global REPLAY_ACTIVE, REPLAY_PAUSED, REPLAY_COUNT, REPLAY_IDX, REPLAY_START_MONO, REPLAY_BASE_TS
    try:
        REPLAY_START_MONO = time.monotonic()
        # base timestamp of first message
        if not REPLAY_MESSAGES:
            REPLAY_ACTIVE = False
            return
        REPLAY_BASE_TS = float(REPLAY_MESSAGES[0].get("timestamp", 0.0))
        REPLAY_IDX = 0
        while REPLAY_ACTIVE and REPLAY_IDX < len(REPLAY_MESSAGES):
            if REPLAY_PAUSED:
                await asyncio.sleep(0.05)
                continue
            msg = REPLAY_MESSAGES[REPLAY_IDX]
            t_rel = float(msg.get("timestamp", 0.0)) - float(REPLAY_BASE_TS or 0.0)
            target = (REPLAY_START_MONO or time.monotonic()) + max(0.0, t_rel)
            # wait until target time
            while not REPLAY_PAUSED and time.monotonic() < target and REPLAY_ACTIVE:
                await asyncio.sleep(0.01)
            if not REPLAY_ACTIVE:
                break
            if REPLAY_PAUSED:
                # Adjust base so timing resumes smoothly after pause
                REPLAY_START_MONO = time.monotonic() - max(0.0, t_rel)
                await asyncio.sleep(0.05)
                continue
            topic = str(msg.get("topic"))
            if (not REPLAY_TOPICS) or (topic in set(REPLAY_TOPICS)):
                try:
                    b = base64.b64decode(str(msg.get("payload", "")).encode("utf-8"))
                    if MQTT_CLIENT:
                        MQTT_CLIENT.publish(topic, b)
                    REPLAY_COUNT += 1
                except Exception:
                    pass
            REPLAY_IDX += 1
    finally:
        REPLAY_ACTIVE = False


@app.get("/replay/status")
async def replay_status() -> Dict[str, Any]:
    return {
        "active": REPLAY_ACTIVE,
        "paused": REPLAY_PAUSED,
        "count": REPLAY_COUNT,
        "file": REPLAY_FILE.name if REPLAY_FILE else None,
        "topics": REPLAY_TOPICS or [],
        "index": REPLAY_IDX,
        "total": len(REPLAY_MESSAGES),
    }


@app.post("/replay/start")
async def replay_start(payload: Dict[str, Any]) -> Dict[str, Any]:
    global REPLAY_ACTIVE, REPLAY_PAUSED, REPLAY_TOPICS, REPLAY_FILE, REPLAY_TASK
    global REPLAY_MESSAGES, REPLAY_COUNT, REPLAY_IDX
    name = str(payload.get("filename", "")).strip()
    topics = payload.get("topics")
    topics_list = None
    if isinstance(topics, list) and topics:
        topics_list = [str(t) for t in topics]
    if not name:
        return {"status": "error", "error": "filename required"}
    fpath = SHARED_DIR / name
    if not fpath.is_file():
        return {"status": "error", "error": "file not found"}
    try:
        with fpath.open("r", encoding="utf-8") as f:
            REPLAY_MESSAGES = json.load(f)
    except Exception as e:
        return {"status": "error", "error": f"failed to read file: {e}"}
    REPLAY_FILE = fpath
    REPLAY_TOPICS = topics_list
    REPLAY_COUNT = 0
    REPLAY_IDX = 0
    REPLAY_ACTIVE = True
    REPLAY_PAUSED = False
    # Launch task
    if REPLAY_TASK and not REPLAY_TASK.done():
        try:
            REPLAY_TASK.cancel()
        except Exception:
            pass
    REPLAY_TASK = asyncio.create_task(_replay_runner())
    return {"status": "ok"}


@app.post("/replay/pause")
async def replay_pause() -> Dict[str, str]:
    global REPLAY_PAUSED
    if REPLAY_ACTIVE:
        REPLAY_PAUSED = True
    return {"status": "ok"}


@app.post("/replay/resume")
async def replay_resume() -> Dict[str, str]:
    global REPLAY_PAUSED, REPLAY_START_MONO
    if REPLAY_ACTIVE:
        REPLAY_PAUSED = False
        # Reset base to now so subsequent timing is relative to remaining schedule
        if REPLAY_IDX < len(REPLAY_MESSAGES):
            cur_ts = float(REPLAY_MESSAGES[REPLAY_IDX].get("timestamp", 0.0))
            REPLAY_START_MONO = time.monotonic() - (cur_ts - float(REPLAY_BASE_TS or 0.0))
    return {"status": "ok"}


@app.post("/replay/stop")
async def replay_stop() -> Dict[str, Any]:
    global REPLAY_ACTIVE, REPLAY_TASK
    REPLAY_ACTIVE = False
    if REPLAY_TASK and not REPLAY_TASK.done():
        try:
            REPLAY_TASK.cancel()
        except Exception:
            pass
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    global MQTT_CLIENT, EVENT_LOOP
    EVENT_LOOP = asyncio.get_running_loop()
    MQTT_CLIENT = mqtt.Client()
    MQTT_CLIENT.max_queued_messages_set(1)
    MQTT_CLIENT.on_connect = _on_connect
    MQTT_CLIENT.on_message = _on_message
    MQTT_CLIENT.connect(MQTT_HOST, MQTT_PORT, 60)
    MQTT_CLIENT.loop_start()
    asyncio.create_task(_broadcast_loop())


@app.on_event("shutdown")
async def shutdown_event():
    if MQTT_CLIENT:
        MQTT_CLIENT.loop_stop()
        MQTT_CLIENT.disconnect()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    WEBSOCKETS.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        WEBSOCKETS.discard(ws)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/sim/imu")
async def sim_imu(payload: Dict[str, Any]) -> Dict[str, str]:
    global SIM_IMU_ACTIVE, SENSOR_STATES, _BASELINE_STATE, _BASELINE_LAST_TS
    # Update IMU simulation state based on control flag (if provided)
    try:
        ctrl_raw = payload.get("control")
        if isinstance(ctrl_raw, str):
            ctrl = ctrl_raw.strip().upper()
            if ctrl == "START":
                SIM_IMU_ACTIVE = True
                # Capture baseline to restore later
                _BASELINE_STATE["imu"] = SENSOR_STATES.get("imu")
                _BASELINE_LAST_TS["imu"] = SENSOR_IMU_LAST_TIME
                SENSOR_STATES["imu"] = "Simulated"
            elif ctrl == "STOP":
                SIM_IMU_ACTIVE = False
                # Restore logical state based on whether new real data arrived
                base_ts = _BASELINE_LAST_TS.get("imu")
                last_ts = SENSOR_IMU_LAST_TIME
                now_sec = time.time()
                if last_ts is None:
                    SENSOR_STATES["imu"] = "Not initialized"
                elif base_ts is not None and last_ts == base_ts:
                    # No new data since sim started; restore previous baseline
                    SENSOR_STATES["imu"] = _BASELINE_STATE.get("imu") or "Not initialized"
                else:
                    if now_sec - last_ts > 10:
                        SENSOR_STATES["imu"] = "Unavailable"
                    else:
                        SENSOR_STATES["imu"] = "Running" if _IMU_LAST_VALID else "Degraded"
    except Exception:
        pass
    if MQTT_CLIENT:
        heading = STATE.get("heading")
        try:
            h = float(heading)
            if not isfinite(h):
                h = -1.0
        except Exception:
            h = -1.0
        # STATE["heading"] is stored in radians. IMU simulator expects degrees for baseline.
        try:
            if h >= 0:
                h = float(degrees(h))
        except Exception:
            pass
        out = {**payload, "heading": h}
        MQTT_CLIENT.publish("land/imu", json.dumps(out))
    return {"status": "ok"}


@app.post("/sim/gps")
async def sim_gps(payload: Dict[str, Any]) -> Dict[str, str]:
    global SIM_GPS_ACTIVE, SENSOR_STATES, _BASELINE_STATE, _BASELINE_LAST_TS
    # Update GPS simulation state based on control flag
    try:
        ctrl_raw = payload.get("control")
        if isinstance(ctrl_raw, str):
            ctrl = ctrl_raw.strip().upper()
            if ctrl in ("VECTOR", "ROUTE"):
                SIM_GPS_ACTIVE = True
                _BASELINE_STATE["gps"] = SENSOR_STATES.get("gps")
                _BASELINE_LAST_TS["gps"] = SENSOR_GPS_LAST_TIME
                SENSOR_STATES["gps"] = "Simulated"
            elif ctrl == "STOP":
                SIM_GPS_ACTIVE = False
                base_ts = _BASELINE_LAST_TS.get("gps")
                last_ts = SENSOR_GPS_LAST_TIME
                now_sec = time.time()
                if last_ts is None:
                    SENSOR_STATES["gps"] = "Not initialized"
                elif base_ts is not None and last_ts == base_ts:
                    SENSOR_STATES["gps"] = _BASELINE_STATE.get("gps") or "Not initialized"
                else:
                    if now_sec - last_ts > 10:
                        SENSOR_STATES["gps"] = "Unavailable"
                    else:
                        SENSOR_STATES["gps"] = "Running" if _GPS_LAST_VALID else "Degraded"
    except Exception:
        pass
    if MQTT_CLIENT:
        MQTT_CLIENT.publish("land/gps", json.dumps(payload))
        # Also update IMU baseline heading so it can simulate small yaw variations.
        try:
            ctrl = str(payload.get("control", "")).upper()
            hdg_val = payload.get("hdg")
            if ctrl == "VECTOR" and hdg_val is not None:
                imu_msg = {"heading": float(hdg_val)}
            else:
                # For ROUTE or STOP (or missing hdg), disable yaw simulation
                imu_msg = {"heading": -1}
            MQTT_CLIENT.publish("land/imu", json.dumps(imu_msg))
        except Exception:
            pass
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
