import asyncio
import json
import os
import time
from datetime import datetime
from math import atan2, cos, radians, sin, sqrt, pi
from typing import Dict, Any, Set

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
    "yaw": None,
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
    "gps_signal": None,
    "uptime": None,
}

LAST_MESSAGE_TIME: float | None = None
WEBSOCKETS: Set[WebSocket] = set()
MQTT_CLIENT: mqtt.Client | None = None
EVENT_LOOP: asyncio.AbstractEventLoop | None = None
_last_broadcast: float = 0.0
_last_processed: float = 0.0

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensor/#")

_prev_gps: Dict[str, Any] | None = None
_prev_imu_ts: float | None = None
_est_velocity: float = 0.0
_est_heading: float = 0.0


def _parse_ts(ts: str | None) -> float:
    if not ts:
        return time.time()
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
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


def _on_connect(client: mqtt.Client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC)


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
    global LAST_MESSAGE_TIME, _prev_gps, _prev_imu_ts, _est_velocity, _last_processed, _est_heading
    now = time.monotonic()
    if now - _last_processed < 0.1:
        return
    _last_processed = now
    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        return
    LAST_MESSAGE_TIME = time.time()

    if topic == "sensor/gps":
        lat = payload.get("lat")
        lon = payload.get("lon")
        alt = payload.get("alt")
        ts = _parse_ts(payload.get("ts"))
        STATE["latitude"] = lat
        STATE["longitude"] = lon
        STATE["altitude"] = alt
        STATE["gps_signal"] = payload.get("fix")
        STATE["latency"] = LAST_MESSAGE_TIME - ts
        if _prev_gps:
            dt = ts - _prev_gps["ts"]
            if dt > 0:
                dist = _haversine(_prev_gps["lat"], _prev_gps["lon"], lat, lon)
                STATE["true_speed"] = dist / dt
                STATE["cog"] = _bearing(_prev_gps["lat"], _prev_gps["lon"], lat, lon)
        _prev_gps = {"lat": lat, "lon": lon, "ts": ts}

    elif topic == "sensor/imu":
        ax = payload.get("ax")
        ay = payload.get("ay")
        az = payload.get("az")
        gx = payload.get("gx")
        gy = payload.get("gy")
        gz = payload.get("gz")
        mx = payload.get("mx")
        my = payload.get("my")
        mz = payload.get("mz")
        ts = _parse_ts(payload.get("ts"))
        STATE["roll"] = atan2(ay, az)
        STATE["pitch"] = atan2(-ax, sqrt(ay * ay + az * az))
        STATE["rate_of_turn"] = gz
        if _prev_imu_ts is not None:
            dt = ts - _prev_imu_ts
            if dt > 0:
                if ax is not None:
                    _est_velocity += ax * dt
                    STATE["estimated_speed"] = _est_velocity
                    STATE["estimated_speed_confidence"] = 1.0
                if gz is not None:
                    _est_heading = (_est_heading + gz * dt) % (2 * pi)
                    STATE["yaw"] = _est_heading
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
            STATE["heading"] = STATE.get("yaw")
        STATE["latency"] = LAST_MESSAGE_TIME - ts

    elif topic == "sensor/battery":
        STATE["battery_status"] = payload.get("soc")
        ts = _parse_ts(payload.get("ts"))
        STATE["latency"] = LAST_MESSAGE_TIME - ts

    elif topic == "sensor/status":
        ts = _parse_ts(payload.get("ts"))
        STATE["latency"] = LAST_MESSAGE_TIME - ts

async def _broadcast_loop():
    global _last_broadcast
    while True:
        now = time.monotonic()
        if now - _last_broadcast >= 0.1:
            _last_broadcast = now
            data = {"sensors": STATE, "last_message_time": LAST_MESSAGE_TIME}
            to_remove = []
            for ws in list(WEBSOCKETS):
                try:
                    await asyncio.wait_for(ws.send_json(data), timeout=0.1)
                except Exception:
                    to_remove.append(ws)
            for ws in to_remove:
                WEBSOCKETS.discard(ws)
        await asyncio.sleep(0.01)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
