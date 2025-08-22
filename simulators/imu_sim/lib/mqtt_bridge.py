import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import paho.mqtt.client as mqtt

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from simulators.imu_sim.lib.imu_sim import MPU9250

LOG = logging.getLogger("imu_sim.bridge")


def now_iso() -> str:
    """Return ISO-8601 UTC timestamp with milliseconds and trailing 'Z'."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class IMUPublisher:
    def __init__(self, config_path: str = "./simulators/imu_sim/config.ini"):
        self.config_path = Path(config_path)
        self.imu = MPU9250(str(self.config_path))

        self.broker_host: str = "localhost"
        self.broker_port: int = 1883
        self.client_id: str = "imu_sim"
        self.retain_status: bool = True
        self.topic: str = "sim/imu"
        self.qos: int = 0
        self.status_topic: str = "sensor/status"
        self.validate_schema: bool = False
        self.schema_path: Optional[Path] = None
        self._schema: Optional[Dict[str, Any]] = None

        self.client: Optional[mqtt.Client] = None
        self._running = False
        self._seq = 0

        self._load_mqtt_config()


    def _load_mqtt_config(self) -> None:
        import configparser
        cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
        try:
            cp.read(self.config_path)
            mqtt_section = cp["mqtt"] if "mqtt" in cp else {}
        except Exception:
            mqtt_section = {}

        self.broker_host = mqtt_section.get("host", "localhost")
        try:
            self.broker_port = int(mqtt_section.get("port", "1883"))
        except Exception:
            self.broker_port = 1883

        self.client_id = mqtt_section.get("client_id", "imu_sim")
        self.retain_status = mqtt_section.getboolean("retain_status", fallback=True)
        self.topic = mqtt_section.get("topic", "sim/imu")
        try:
            self.qos = int(mqtt_section.get("qos", "0"))
        except Exception:
            self.qos = 0

        self.validate_schema = mqtt_section.getboolean("validate_schema", fallback=False)
        schema_path_cfg = mqtt_section.get("schema_path", "").strip()
        if schema_path_cfg:
            sp = Path(schema_path_cfg)
            if not sp.is_absolute():
                sp = (self.config_path.parent / sp).resolve()
            self.schema_path = sp
        else:
            self.schema_path = None

        self.status_topic = mqtt_section.get("status_topic", "sensor/status")

        LOG.debug(
            "MQTT config loaded: host=%s port=%s client_id=%s topic=%s qos=%s validate_schema=%s schema_path=%s",
            self.broker_host,
            self.broker_port,
            self.client_id,
            self.topic,
            self.qos,
            self.validate_schema,
            str(self.schema_path) if self.schema_path else None,
        )


    def _load_schema(self) -> None:
        """Load outgoing schema for the configured topic. If it fails, disable validation."""
        if not self.schema_path:
            LOG.error("validate_schema requested but schema_path not provided in INI")
            self.validate_schema = False
            return

        try:
            with self.schema_path.open("r", encoding="utf-8") as fh:
                top_spec = json.load(fh)
        except Exception as e:
            LOG.error("Failed to open schema file '%s': %s. Disabling schema validation.", self.schema_path, e)
            self.validate_schema = False
            return

        topics = top_spec.get("topics", {})
        tinfo = topics.get(self.topic)
        if not tinfo:
            LOG.error("Schema file does not contain topic %s. Disabling validation.", self.topic)
            self.validate_schema = False
            return

        schema = tinfo.get("schema")
        if not schema:
            LOG.error("No 'schema' entry for topic %s in schema file. Disabling validation.", self.topic)
            self.validate_schema = False
            return

        self._schema = schema
        LOG.info("Loaded schema for topic %s from %s", self.topic, self.schema_path)

    def read_and_init_imu(self,
                          accel_seed: Optional[int] = 1,
                          gyro_seed: Optional[int] = 1,
                          mag_seed: Optional[int] = 1,
                          accel_lpf_hz: float = 100.0,
                          gyro_lpf_hz: float = 98.0) -> None:
        """Read IMU config and initialize the internal simulators."""
        LOG.info("Reading IMU config from %s", self.config_path)
        self.imu.read_config()
        self.imu.init_all_sims(
            accel_seed=accel_seed,
            gyro_seed=gyro_seed,
            mag_seed=mag_seed,
            accel_lpf_cut_hz=accel_lpf_hz,
            gyro_lpf_cut_hz=gyro_lpf_hz,
        )


    def _setup_mqtt_client(self) -> None:
        self.client = mqtt.Client(client_id=self.client_id)
        try:
            lwt_payload = json.dumps({"status": "offline", "ts": now_iso()})
            self.client.will_set(self.status_topic, payload=lwt_payload, qos=1, retain=self.retain_status)
        except Exception:
            LOG.debug("Failed to set LWT")

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect


    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            LOG.info("Connected to broker %s:%s", self.broker_host, self.broker_port)
            if self.retain_status:
                try:
                    client.publish(self.status_topic, json.dumps({"status": "online", "ts": now_iso()}), qos=1, retain=True)
                except Exception:
                    LOG.debug("Failed to publish online status")
        else:
            LOG.error("MQTT connect failed with rc=%s", rc)


    def _on_disconnect(self, client, userdata, rc):
        LOG.warning("Disconnected from broker (rc=%s)", rc)


    def start(self) -> None:
        """Start publishing loop (blocks until stop())."""
        if not hasattr(self.imu, "_accel_sim") or not hasattr(self.imu, "_gyro_sim"):
            raise RuntimeError("Call read_and_init_imu() before start()")

        if self.validate_schema and self._schema is None:
            self._load_schema()

        self._setup_mqtt_client()
        LOG.info("Connecting to MQTT broker %s:%d", self.broker_host, self.broker_port)
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_start()

        try:
            if self.retain_status:
                self.client.publish(self.status_topic, json.dumps({"status": "online", "ts": now_iso()}), qos=1, retain=True)
        except Exception:
            LOG.debug("Failed to publish online status on start")

        dt_acc = 1.0 / float(self.imu.accel_odr_hz)
        dt_gyro = 1.0 / float(self.imu.gyro_odr_hz)
        t_next_acc = time.time()
        t_next_gyro = time.time()
        last_acc = [0.0, 0.0, 0.0]
        last_gyro = [0.0, 0.0, 0.0]

        self._running = True
        LOG.info("Starting IMU publisher: accel ODR=%.1fHz gyro ODR=%.1fHz -> topic %s (qos=%d)",
                 float(self.imu.accel_odr_hz), float(self.imu.gyro_odr_hz), self.topic, self.qos)

        try:
            while self._running:
                now_t = time.time()

                if now_t >= t_next_acc:
                    _, a_g = self.imu.sample_accel(np.zeros(3), np.eye(3))
                    last_acc = [float(a_g[0]), float(a_g[1]), float(a_g[2])]
                    t_next_acc += dt_acc

                if now_t >= t_next_gyro:
                    _, w = self.imu.sample_gyro(np.zeros(3), np.eye(3))
                    last_gyro = [float(w[0]), float(w[1]), float(w[2])]
                    t_next_gyro += dt_gyro

                payload = {
                    "ax": last_acc[0],
                    "ay": last_acc[1],
                    "az": last_acc[2],
                    "gx": last_gyro[0],
                    "gy": last_gyro[1],
                    "gz": last_gyro[2],
                    "ts": now_iso(),
                    "seq": int(self._seq),
                }
                self._seq += 1

                if self.validate_schema and self._schema is not None:
                    try:
                        validate(instance=payload, schema=self._schema)
                    except ValidationError as ve:
                        LOG.warning("Outgoing payload failed schema validation: %s", ve.message)
                        time.sleep(0.0005)
                        continue

                try:
                    self.client.publish(self.topic, json.dumps(payload, separators=(",", ":")), qos=self.qos, retain=False)
                    LOG.debug("Published seq=%s to %s", payload["seq"], self.topic)
                except Exception as e:
                    LOG.warning("Failed to publish: %s", e)

                time.sleep(0.0005)
        except KeyboardInterrupt:
            LOG.info("Keyboard interrupt received; stopping")
        finally:
            self.stop()


    def stop(self) -> None:
        LOG.info("Stopping IMU MQTT publisher")
        self._running = False
        try:
            if self.client:
                if self.retain_status:
                    self.client.publish(self.status_topic, json.dumps({"status": "offline", "ts": now_iso()}), qos=1, retain=True)
                self.client.loop_stop()
                self.client.disconnect()
        except Exception as e:
            LOG.debug("Exception while disconnecting MQTT client: %s", e)
