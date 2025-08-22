import asyncio
import json
import os
import time
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

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "boat/+/+")


def _on_connect(client: mqtt.Client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC)


def _on_message(client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
    global LAST_MESSAGE_TIME
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        return
    LAST_MESSAGE_TIME = time.time()
    for key in STATE.keys():
        if key in payload:
            STATE[key] = payload[key]
    if EVENT_LOOP:
        data = {"sensors": STATE, "last_message_time": LAST_MESSAGE_TIME}
        for ws in list(WEBSOCKETS):
            asyncio.run_coroutine_threadsafe(ws.send_json(data), EVENT_LOOP)


async def _broadcast_loop():
    while True:
        data = {"sensors": STATE, "last_message_time": LAST_MESSAGE_TIME}
        to_remove = []
        for ws in WEBSOCKETS:
            try:
                await ws.send_json(data)
            except Exception:
                to_remove.append(ws)
        for ws in to_remove:
            WEBSOCKETS.discard(ws)
        await asyncio.sleep(1)


@app.on_event("startup")
async def startup_event():
    global MQTT_CLIENT, EVENT_LOOP
    EVENT_LOOP = asyncio.get_running_loop()
    MQTT_CLIENT = mqtt.Client()
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
