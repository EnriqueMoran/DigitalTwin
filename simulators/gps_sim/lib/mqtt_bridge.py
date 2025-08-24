import json
import logging
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import paho.mqtt.client as mqtt
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError

from simulators.gps_sim.lib.gps_sim import NEOM8N
from simulators.route import ScenarioRoute

LOG = logging.getLogger("gps_sim.bridge")

KNOTS_TO_MS = 0.514444


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class GPSPublisher:
    def __init__(self, config_path: str = "./simulators/gps_sim/config.ini"):
        self.config_path = Path(config_path)
        self.gps = NEOM8N(str(self.config_path))

        # MQTT / publishing configuration (defaults)
        self.broker_host: str = "localhost"
        self.broker_port: int = 1883
        self.client_id: str = "gps_sim"
        self.retain_status: bool = True
        self.topic: str = "sim/gps"
        self.qos: int = 0
        self.status_topic: str = "sensor/status"
        self.validate_schema: bool = False
        self.schema_path: Optional[Path] = None
        self._schema: Optional[Dict[str, Any]] = None
        self._validator: Optional[Draft7Validator] = None

        self.client: Optional[mqtt.Client] = None
        self._running = False

        self.log_messages: bool = False

        self._load_mqtt_config()

        # Load navigation scenario defining route and wave state
        scen_path = Path(__file__).resolve().parents[2] / "scenarios" / "main_scenario.json"
        try:
            self.route = ScenarioRoute(scen_path)
            LOG.info("Loaded scenario from %s", scen_path)
        except Exception as e:
            LOG.error("Failed to load scenario %s: %s", scen_path, e)
            raise

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

        self.client_id = mqtt_section.get("client_id", "gps_sim")
        self.retain_status = mqtt_section.getboolean("retain_status", fallback=True)
        self.topic = mqtt_section.get("topic", "sim/gps")
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
        self._validator = Draft7Validator(schema)
        LOG.info("Loaded schema for topic %s from %s", self.topic, self.schema_path)

    def read_and_init_gps(self, seed: Optional[int] = 1) -> None:
        """
        Read GPS configuration and initialize simulator RNG/scheduling.
        """
        LOG.info("Reading GPS config from %s", self.config_path)
        self.gps.read_config()
        self.gps.init_sim(seed=seed)

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
        """
        Start publishing GPS measurements at the configured publish_rate_hz.
        Must call read_and_init_gps() first.
        """
        if not hasattr(self.gps, "_rng"):
            raise RuntimeError("Call read_and_init_gps() before start()")

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

        # publishing scheduling: use gps.publish_rate_hz if present, otherwise fallback to update_rate_hz
        try:
            pub_hz = float(self.gps.publish_rate_hz) if getattr(self.gps, "publish_rate_hz", None) else float(self.gps.update_rate_hz)
        except Exception:
            pub_hz = 1.0

        if pub_hz <= 0.0:
            pub_hz = 1.0

        dt_pub = 1.0 / float(pub_hz)
        t_next = time.time()
        sim_start = time.time()

        self._running = True
        LOG.info("Starting GPS publisher: publish_rate=%.2fHz -> topic %s (qos=%d)", pub_hz, self.topic, self.qos)

        try:
            while self._running:
                now_t = time.time()
                sim_t = now_t - sim_start
                if now_t >= t_next:
                    # Produce one sample at sim_t using scenario-defined motion
                    sample = self.gps.sample(sim_t, motion_provider=self.route.gps_motion)
                    meas = sample.get("meas", {})
                    speed_knots = meas.get("speed_knots")
                    meas_out = {
                        "lat": meas.get("lat"),
                        "lon": meas.get("lon"),
                        "alt": meas.get("alt"),
                        "speed": speed_knots * KNOTS_TO_MS if speed_knots is not None else None,
                        "fix": meas.get("fix_type"),
                        "ts": meas.get("ts"),
                    }

                    # Optional validation
                    if self.validate_schema and self._validator is not None:
                        try:
                            self._validator.validate(meas_out)
                        except ValidationError as ve:
                            LOG.warning("Outgoing GPS payload failed schema validation: %s", ve.message)
                            # skip this publish (sleep until next tick to avoid busy-loop)
                            t_next += dt_pub
                            time.sleep(dt_pub)
                            continue

                    # Optional logging of outgoing message
                    if self.log_messages:
                        try:
                            log_msg = {"topic": self.topic, "ts_local": now_iso(), "payload": meas_out}
                            LOG.info(json.dumps(log_msg, separators=(",", ":"), ensure_ascii=False))
                        except Exception:
                            LOG.debug("Failed to log outgoing message")

                    # Publish
                    try:
                        self.client.publish(self.topic, json.dumps(meas_out, separators=(",", ":")), qos=self.qos, retain=False)
                        LOG.debug("Published to %s", self.topic)
                    except Exception as e:
                        LOG.warning("Failed to publish GPS payload: %s", e)

                    # If NMEA sentences present and protocol==nmea we could optionally publish them to another topic;
                    # for now we keep to the single JSON topic as per project style.

                    # advance schedule
                    t_next += dt_pub
                else:
                    # sleep until next scheduled publish to avoid busy-loop
                    sleep_dur = t_next - now_t
                    if sleep_dur > 0:
                        time.sleep(min(sleep_dur, dt_pub))
        except KeyboardInterrupt:
            LOG.info("Keyboard interrupt received; stopping")
        finally:
            self.stop()

    def stop(self) -> None:
        LOG.info("Stopping GPS MQTT publisher")
        self._running = False
        try:
            if self.client:
                if self.retain_status:
                    try:
                        self.client.publish(self.status_topic, json.dumps({"status": "offline", "ts": now_iso()}), qos=1, retain=True)
                    except Exception:
                        LOG.debug("Failed to publish offline status")
                self.client.loop_stop()
                self.client.disconnect()
        except Exception as e:
            LOG.debug("Exception while disconnecting MQTT client: %s", e)
