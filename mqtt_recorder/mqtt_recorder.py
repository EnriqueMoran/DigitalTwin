import os
import json
import time
import base64
import signal
from typing import List, Dict, Any

import paho.mqtt.client as mqtt

CONFIG_PATH = os.getenv("MQTT_RECORDER_CONFIG", "config.json")

def load_config(path: str) -> Dict[str, Any]:
    with open(path, 'r') as f:
        return json.load(f)

def encode_payload(payload: bytes) -> str:
    return base64.b64encode(payload).decode('utf-8')

def decode_payload(payload: str) -> bytes:
    return base64.b64decode(payload.encode('utf-8'))


def record_mode(client: mqtt.Client, save_file: str) -> None:
    messages: List[Dict[str, Any]] = []

    def on_message(_client, _userdata, msg):
        messages.append({
            'timestamp': time.time(),
            'topic': msg.topic,
            'payload': encode_payload(msg.payload),
        })

    def handle_exit(signum, frame):
        if save_file:
            with open(save_file, 'w') as f:
                json.dump(messages, f)
        exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    client.on_message = on_message
    client.subscribe('#')
    client.loop_forever()


def matches_topic(topic_filters: List[str], topic: str) -> bool:
    if not topic_filters:
        return True
    return any(mqtt.topic_matches_sub(filt, topic) for filt in topic_filters)


def replay_mode(client: mqtt.Client, load_file: str, topics: List[str]) -> None:
    with open(load_file, 'r') as f:
        messages = json.load(f)

    messages.sort(key=lambda m: m['timestamp'])
    if not messages:
        return

    start_time = messages[0]['timestamp']
    replay_start = time.time()

    for msg in messages:
        if not matches_topic(topics, msg['topic']):
            continue

        target_time = replay_start + (msg['timestamp'] - start_time)
        while time.time() < target_time:
            time.sleep(0.01)
        client.publish(msg['topic'], decode_payload(msg['payload']))


if __name__ == '__main__':
    config = load_config(CONFIG_PATH)
    host = config.get('host', 'mosquitto')
    port = int(config.get('port', 1883))
    mode = config.get('mode', 'record')
    save_file = config.get('save_file', '/data/recording.json')
    load_file = config.get('load_file', '/data/recording.json')
    topics = config.get('topics', [])

    client = mqtt.Client()
    client.connect(host, port)

    if mode == 'record':
        record_mode(client, save_file)
    elif mode == 'replay':
        replay_mode(client, load_file, topics)
    else:
        raise ValueError(f"Unknown mode: {mode}")
