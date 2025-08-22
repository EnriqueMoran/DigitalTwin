import logging
import signal
import sys
import threading
import time

import paho.mqtt.client as mqtt

LOG = logging.getLogger("esp32_sim.app")


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
        elif msg.topic == "sim/battery":
            client.publish("sensor/battery", msg.payload)

    def run(self) -> None:
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.subscribe("sim/imu")
        self._client.subscribe("sim/gps")
        self._client.subscribe("sim/battery")
        while not self._stop.is_set():
            self._client.loop(0.1)
        self._client.disconnect()

    def stop(self) -> None:
        self._stop.set()
        self.join()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    forwarder = ESP32Forwarder()

    def _sig(sig, frame):
        LOG.info("Signal %s received, shutting down", sig)
        forwarder.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    forwarder.start()
    while forwarder.is_alive():
        time.sleep(0.5)


if __name__ == "__main__":
    main()
