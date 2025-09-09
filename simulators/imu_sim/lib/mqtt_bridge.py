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
    # Return ISO-8601 UTC timestamp with milliseconds and trailing 'Z'.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class IMUPublisher:
    def __init__(self, config_path: str = "./simulators/imu_sim/config.ini"):
        # Initialize config and IMU simulator
        self.config_path = Path(config_path)
        self.imu = MPU9250(str(self.config_path))

        # MQTT defaults
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

        self.log_messages: bool = False

        self._load_mqtt_config()
        self.control_topic = "land/imu"
        self.wave_cfg = {"amp": 0.0, "freq": 0.0, "spike_prob": 0.0, "spike_amp": 0.0}
        # Heading control from land/imu (degrees). When negative, yaw simulation disabled.
        self.heading = -1.0
        self._base_heading_deg = 0.0
        self._disable_yaw = True
        self._active = False
        self._sim_start = 0.0

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
        try:
            self.log_messages = mqtt_section.getboolean("log_messages", fallback=False)
        except Exception:
            self.log_messages = False

        LOG.debug(
            "MQTT config loaded: host=%s port=%s client_id=%s topic=%s qos=%s validate_schema=%s schema_path=%s log_messages=%s",
            self.broker_host,
            self.broker_port,
            self.client_id,
            self.topic,
            self.qos,
            self.validate_schema,
            str(self.schema_path) if self.schema_path else None,
            self.log_messages,
        )

    def _load_schema(self) -> None:
        # Load outgoing schema for the configured topic. If it fails, disable validation.
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
        # Read IMU config and initialize the internal simulators.
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
        # Prepare MQTT client and LWT
        self.client = mqtt.Client(client_id=self.client_id)
        try:
            lwt_payload = json.dumps({"status": "offline", "ts": now_iso()})
            self.client.will_set(self.status_topic, payload=lwt_payload, qos=1, retain=self.retain_status)
        except Exception:
            LOG.debug("Failed to set LWT")

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            LOG.info("Connected to broker %s:%s", self.broker_host, self.broker_port)
            if self.retain_status:
                try:
                    client.publish(self.status_topic, json.dumps({"status": "online", "ts": now_iso()}), qos=1, retain=True)
                except Exception:
                    LOG.debug("Failed to publish online status")
            try:
                client.subscribe(self.control_topic)
            except Exception:
                LOG.debug("Failed to subscribe to %s", self.control_topic)
        else:
            LOG.error("MQTT connect failed with rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        LOG.warning("Disconnected from broker (rc=%s)", rc)

    def _on_message(self, client, userdata, msg):
        if msg.topic != self.control_topic:
            return
        try:
            data = json.loads(msg.payload.decode())
        except Exception:
            return
        ctrl = str(data.get("control", "")).upper()
        if ctrl == "START":
            self.wave_cfg = {
                "amp": float(data.get("amp", 0.0)),
                "freq": float(data.get("freq", 0.0)),
                "spike_prob": float(data.get("spike_prob", 0.0)),
                "spike_amp": float(data.get("spike_amp", 0.0)),
            }
            if "heading" in data:
                try:
                    h = float(data.get("heading"))
                    self.heading = h
                    if h >= 0:
                        self._base_heading_deg = h
                        self._disable_yaw = False
                    else:
                        self._disable_yaw = True
                except Exception:
                    pass
            self._active = True
            self._sim_start = time.time()
            now = time.time()
            self._t_next_acc = now
            self._t_next_gyro = now
            self._t_next_mag = now
        elif ctrl == "STOP":
            self._active = False
        else:
            # Treat messages without START/STOP as parameter updates
            updated = False
            if "heading" in data:
                try:
                    h = float(data.get("heading"))
                    self.heading = h
                    if h >= 0:
                        self._base_heading_deg = h
                        self._disable_yaw = False
                    else:
                        self._disable_yaw = True
                    updated = True
                except Exception:
                    pass
            # Update wave configuration live if provided
            for k in ("amp", "freq", "spike_prob", "spike_amp"):
                if k in data:
                    try:
                        self.wave_cfg[k] = float(data.get(k, 0.0))
                        updated = True
                    except Exception:
                        pass
            # If we updated parameters during active run, keep running without restart

    def _motion(self, t: float):
        amp = float(self.wave_cfg.get("amp", 0.0))
        freq = float(self.wave_cfg.get("freq", 0.0))
        spike_prob = float(self.wave_cfg.get("spike_prob", 0.0))
        spike_amp = float(self.wave_cfg.get("spike_amp", 0.0))

        if spike_prob > 0.0 and np.random.random() < spike_prob:
            sign = 1.0 if np.random.random() < 0.5 else -1.0
            roll_spike = sign * spike_amp
            pitch_spike = sign * (0.6 * spike_amp)
            yaw_spike = sign * (0.3 * spike_amp)
        else:
            roll_spike = pitch_spike = yaw_spike = 0.0

        roll_deg = amp * np.sin(2.0 * np.pi * freq * t) + roll_spike
        pitch_deg = (amp / 2.0) * np.sin(2.0 * np.pi * freq * t + np.pi / 2.0) + pitch_spike

        if self._disable_yaw:
            yaw_wave_amp_deg = 0.0
            base_heading_deg = float(self._base_heading_deg)
        else:
            base_heading_deg = float(self._base_heading_deg)
            yaw_wave_amp_deg = max(0.2, amp * 0.03)
        yaw_wave = yaw_wave_amp_deg * np.sin(2.0 * np.pi * freq * t + np.pi / 3.0)
        yaw_deg = base_heading_deg + yaw_wave + yaw_spike

        roll_rad = np.radians(roll_deg)
        pitch_rad = np.radians(pitch_deg)
        yaw_rad = np.radians(yaw_deg)

        cr, sr = np.cos(roll_rad), np.sin(roll_rad)
        cp, sp = np.cos(pitch_rad), np.sin(pitch_rad)
        cy, sy = np.cos(yaw_rad), np.sin(yaw_rad)
        R = np.array([
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ], dtype=float)

        roll_rate = amp * 2.0 * np.pi * freq * np.cos(2.0 * np.pi * freq * t)
        pitch_rate = (amp / 2.0) * 2.0 * np.pi * freq * np.cos(2.0 * np.pi * freq * t + np.pi / 2.0)
        yaw_rate = yaw_wave_amp_deg * 2.0 * np.pi * freq * np.cos(2.0 * np.pi * freq * t + np.pi / 3.0)
        omega = np.array([roll_rate, pitch_rate, yaw_rate], dtype=float)

        a_lin = np.zeros(3, dtype=float)
        return a_lin, omega, R

    def start(self) -> None:
        # Start publishing loop (blocks until stop()).
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

        # Compute sample intervals from configured ODRs
        self._dt_acc = 1.0 / float(self.imu.accel_odr_hz)
        self._dt_gyro = 1.0 / float(self.imu.gyro_odr_hz)
        self._dt_mag = 1.0 / float(self.imu.mag_odr_hz)
        # Target publish cadence: 10 Hz (anchored)
        self._dt_pub = 0.1

        # Next-sample timestamps
        self._t_next_acc = time.time()
        self._t_next_gyro = time.time()
        self._t_next_mag = time.time()
        # Anchored publish scheduler
        self._t0_pub = time.monotonic()
        self._last_pub_tick = -1

        # Last sampled values
        last_acc = [0.0, 0.0, 0.0]
        last_gyro = [0.0, 0.0, 0.0]
        last_mag = [0.0, 0.0, 0.0]

        # Last sample timestamps (seconds since epoch)
        last_acc_ts = 0.0
        last_gyro_ts = 0.0
        last_mag_ts = 0.0

        self._running = True
        LOG.info(
            "Starting IMU publisher: accel ODR=%.1fHz gyro ODR=%.1fHz mag ODR=%.1fHz -> topic %s (qos=%d)",
            float(self.imu.accel_odr_hz),
            float(self.imu.gyro_odr_hz),
            float(self.imu.mag_odr_hz),
            self.topic,
            self.qos,
        )

        try:
            while self._running:
                if not self._active:
                    time.sleep(0.1)
                    continue
                now_t = time.time()
                sim_t = now_t - self._sim_start
                sampled = False

                # Compute motion only when a sensor needs sampling
                if now_t >= self._t_next_acc or now_t >= self._t_next_gyro or now_t >= self._t_next_mag:
                    a_lin, omega, R = self._motion(sim_t)

                # Sample accelerometer when scheduled
                if now_t >= self._t_next_acc:
                    _, a_g = self.imu.sample_accel(a_lin, R)
                    last_acc = [float(a_g[0]), float(a_g[1]), float(a_g[2])]
                    last_acc_ts = now_t
                    self._t_next_acc += self._dt_acc
                    sampled = True

                # Sample gyroscope when scheduled
                if now_t >= self._t_next_gyro:
                    _, w = self.imu.sample_gyro(omega, R)
                    last_gyro = [float(w[0]), float(w[1]), float(w[2])]
                    last_gyro_ts = now_t
                    self._t_next_gyro += self._dt_gyro
                    sampled = True

                # Sample magnetometer when scheduled
                if now_t >= self._t_next_mag:
                    _, m = self.imu.sample_mag(R)
                    last_mag = [float(m[0]), float(m[1]), float(m[2])]
                    last_mag_ts = now_t
                    self._t_next_mag += self._dt_mag
                    sampled = True

                # Publish at fixed cadence (10 Hz) using latest samples (anchored)
                now_m = time.monotonic()
                tick = int((now_m - self._t0_pub) / self._dt_pub)
                if tick > self._last_pub_tick:
                    latest_sample_ts = max(last_acc_ts, last_gyro_ts, last_mag_ts) or now_t
                    ts_iso = datetime.fromtimestamp(latest_sample_ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

                    payload = {
                        "ax": last_acc[0],
                        "ay": last_acc[1],
                        "az": last_acc[2],
                        "gx": last_gyro[0],
                        "gy": last_gyro[1],
                        "gz": last_gyro[2],
                        "mx": last_mag[0],
                        "my": last_mag[1],
                        "mz": last_mag[2],
                        "ts": ts_iso,
                        "seq": int(self._seq),
                    }
                    self._seq += 1

                    if self.validate_schema and self._schema is not None:
                        try:
                            validate(instance=payload, schema=self._schema)
                        except ValidationError as ve:
                            LOG.warning("Outgoing payload failed schema validation: %s", ve.message)
                            self._t_next_pub += self._dt_pub
                            continue

                    if self.log_messages:
                        try:
                            log_msg = {"topic": self.topic, "ts_local": now_iso(), "payload": payload}
                            LOG.info(json.dumps(log_msg, separators=(",", ":"), ensure_ascii=False))
                        except Exception:
                            LOG.debug("Failed to log outgoing message")

                    try:
                        self.client.publish(self.topic, json.dumps(payload, separators=(",", ":")), qos=self.qos, retain=False)
                        LOG.debug("Published seq=%s to %s", payload["seq"], self.topic)
                    except Exception as e:
                        LOG.warning("Failed to publish: %s", e)
                    self._last_pub_tick = tick

                # Sleep until the next scheduled event (include publish cadence)
                next_pub_time = self._t0_pub + (self._last_pub_tick + 1) * self._dt_pub
                next_events = [self._t_next_acc, self._t_next_gyro, self._t_next_mag, next_pub_time]
                sleep_until = min(next_events) - time.time()
                if sleep_until > 0:
                    time.sleep(min(max(sleep_until, 0.001), 0.1))
                else:
                    time.sleep(0.001)

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
