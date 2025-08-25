import json
import logging
import time

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import paho.mqtt.client as mqtt

from jsonschema import validate
from jsonschema.exceptions import ValidationError

from simulators.esp32_sim.lib.configparser import ESP32Parser

LOG = logging.getLogger("esp32_sim")


def now_iso() -> str:
    """Return ISO-8601 UTC timestamp with milliseconds and trailing 'Z'."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class ESP32:
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = config_file
        self._broker_host: Optional[str] = None
        self._broker_port: Optional[int] = None

        self._client_id: Optional[str] = None
        self._retain_status: bool = True

        self._imu_in: Optional[str]  = None
        self._gps_in: Optional[str]  = None
        self._batt_in: Optional[str] = None

        self._imu_out: Optional[str]  = None
        self._gps_out: Optional[str]  = None
        self._batt_out: Optional[str] = None

        self._status_topic: Optional[str] = None

        self._qos_imu: int  = 0
        self._qos_gps: int  = 1
        self._qos_batt: int = 1

        self._validate_schema: bool = True
        self._schema_path: Optional[str] = None
        self._schemas_exact: Dict[str, Dict[str, Any]] = {}

        self.client: Optional[mqtt.Client] = None

        self.running  = False
        self._pub_seq = 0
        self._last_recv = {"imu": None, "gps": None, "battery": None}

        self._log_messages: bool = False


    @property
    def broker_host(self) -> Optional[str]:
        return self._broker_host

    @broker_host.setter
    def broker_host(self, val: str) -> None:
        if not isinstance(val, str):
            raise TypeError("broker_host must be a string")
        self._broker_host = val

    @property
    def broker_port(self) -> Optional[int]:
        return self._broker_port

    @broker_port.setter
    def broker_port(self, val: int) -> None:
        if not isinstance(val, int) or val <= 0:
            raise TypeError("broker_port must be a positive integer")
        self._broker_port = val

    @property
    def client_id(self) -> Optional[str]:
        return self._client_id

    @client_id.setter
    def client_id(self, val: str) -> None:
        if not isinstance(val, str):
            raise TypeError("client_id must be a string")
        self._client_id = val

    @property
    def retain_status(self) -> bool:
        return self._retain_status

    @retain_status.setter
    def retain_status(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("retain_status must be a boolean")
        self._retain_status = val

    def _check_topic(self, v: str) -> str:
        if not isinstance(v, str) or len(v.strip()) == 0:
            raise TypeError("topic must be a non-empty string")
        return v

    @property
    def imu_in(self) -> Optional[str]:
        return self._imu_in

    @imu_in.setter
    def imu_in(self, val: str) -> None:
        self._imu_in = self._check_topic(val)

    @property
    def gps_in(self) -> Optional[str]:
        return self._gps_in

    @gps_in.setter
    def gps_in(self, val: str) -> None:
        self._gps_in = self._check_topic(val)

    @property
    def batt_in(self) -> Optional[str]:
        return self._batt_in

    @batt_in.setter
    def batt_in(self, val: str) -> None:
        self._batt_in = self._check_topic(val)

    @property
    def imu_out(self) -> Optional[str]:
        return self._imu_out

    @imu_out.setter
    def imu_out(self, val: str) -> None:
        self._imu_out = self._check_topic(val)

    @property
    def gps_out(self) -> Optional[str]:
        return self._gps_out

    @gps_out.setter
    def gps_out(self, val: str) -> None:
        self._gps_out = self._check_topic(val)

    @property
    def batt_out(self) -> Optional[str]:
        return self._batt_out

    @batt_out.setter
    def batt_out(self, val: str) -> None:
        self._batt_out = self._check_topic(val)

    @property
    def status_topic(self) -> Optional[str]:
        return self._status_topic

    @status_topic.setter
    def status_topic(self, val: str) -> None:
        self._status_topic = self._check_topic(val)

    @property
    def qos_imu(self) -> int:
        return self._qos_imu

    @qos_imu.setter
    def qos_imu(self, val: int) -> None:
        if not isinstance(val, int) or val < 0:
            raise TypeError("qos_imu must be a non-negative integer")
        self._qos_imu = val

    @property
    def qos_gps(self) -> int:
        return self._qos_gps

    @qos_gps.setter
    def qos_gps(self, val: int) -> None:
        if not isinstance(val, int) or val < 0:
            raise TypeError("qos_gps must be a non-negative integer")
        self._qos_gps = val

    @property
    def qos_batt(self) -> int:
        return self._qos_batt

    @qos_batt.setter
    def qos_batt(self, val: int) -> None:
        if not isinstance(val, int) or val < 0:
            raise TypeError("qos_batt must be a non-negative integer")
        self._qos_batt = val

    @property
    def validate_schema(self) -> bool:
        return self._validate_schema

    @validate_schema.setter
    def validate_schema(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("validate_schema must be a boolean")
        self._validate_schema = val

    @property
    def schema_path(self) -> Optional[str]:
        return self._schema_path

    @schema_path.setter
    def schema_path(self, val: str) -> None:
        if not isinstance(val, str) or not val:
            raise TypeError("schema_path must be a non-empty string")
        self._schema_path = val

    @property
    def log_messages(self) -> bool:
        return self._log_messages

    @log_messages.setter
    def log_messages(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("log_messages must be a boolean")
        self._log_messages = val


    def read_config(self) -> None:
        parser = ESP32Parser(self.config_file)

        self.broker_host = parser.parse_broker_host()
        self.broker_port = parser.parse_broker_port()

        self.client_id = parser.parse_client_id()
        self.retain_status = parser.parse_retain_status()

        topics = parser.get_topics_map()
        self.imu_in  = topics.get("imu_in")
        self.gps_in  = topics.get("gps_in")
        self.batt_in = topics.get("battery_in")

        self.imu_out  = topics.get("imu_out")
        self.gps_out  = topics.get("gps_out")
        self.batt_out = topics.get("battery_out")

        self.status_topic = topics.get("status_topic")

        qos_map = parser.get_qos_map()
        self.qos_imu  = qos_map.get("imu", 0)
        self.qos_gps  = qos_map.get("gps", 1)
        self.qos_batt = qos_map.get("battery", 1)

        self.validate_schema = parser.parse_validate_schema()
        self.schema_path = parser.parse_schema_path()
        self.log_messages = parser.parse_log_messages()

        self.client = mqtt.Client(client_id=self.client_id, clean_session=True)
        lwt_payload = json.dumps({"status": "offline", "ts": now_iso()})
        self.client.will_set(self.status_topic, payload=lwt_payload, qos=1, retain=True)

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        if self.validate_schema:
            self._load_schemas_exact()


    def _load_schemas_exact(self) -> None:
        try:
            schema_file = Path(self.schema_path)
            if not schema_file.is_file():
                cfg_dir = Path(self.config_file).resolve().parent
                candidate = cfg_dir / self.schema_path
                if candidate.is_file():
                    schema_file = candidate
                else:
                    schema_file = Path(__file__).resolve().parent.parent / self.schema_path

            with schema_file.open("r", encoding="utf-8") as fh:
                top_spec = json.load(fh)
        except Exception as e:
            LOG.error(
                "Failed to open schema file '%s': %s. Schema validation requested but no schemas loaded.",
                self.schema_path, e
            )
            self._schemas_exact = {}
            self._schemas_loaded = False
            return

        topics_map = top_spec.get("topics", {})
        count = 0
        for tname, tinfo in topics_map.items():
            if not isinstance(tinfo, dict):
                continue
            sch = tinfo.get("schema")
            if sch:
                self._schemas_exact[tname] = sch
                count += 1
        self._schemas_loaded = True
        LOG.info("Loaded %d exact schemas from %s", count, self.schema_path)


    def _find_schema_for_topic(self, topic: str) -> Optional[Dict[str, Any]]:
        return self._schemas_exact.get(topic)


    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            LOG.info("Connected to broker %s:%s", self.broker_host, self.broker_port)
            client.subscribe(self.imu_in)
            client.subscribe(self.gps_in)
            client.subscribe(self.batt_in)
            LOG.info("Subscribed to topics: %s, %s, %s", self.imu_in, self.gps_in, self.batt_in)
            if self.retain_status:
                payload = json.dumps({"status": "online", "ts": now_iso()})
                client.publish(self.status_topic, payload=payload, qos=1, retain=True)
        else:
            LOG.error("MQTT connect failed with rc=%s", rc)


    def _on_disconnect(self, client, userdata, rc):
        LOG.warning("Disconnected from broker (rc=%s)", rc)


    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_bytes = msg.payload

        try:
            text = payload_bytes.decode("utf-8")
        except Exception:
            LOG.warning("Received non-decodable payload on topic %s; discarding", topic)
            return

        LOG.debug("RECV <%s> %s", topic, text[:300])

        try:
            payload = json.loads(text)
            if not isinstance(payload, dict):
                LOG.warning("Received JSON that is not an object on %s; discarding", topic)
                return
        except Exception:
            LOG.warning("Received non-JSON payload on %s; discarding. Head: %.200s", topic, text[:200])
            return

        if self.log_messages:
            LOG.info("RECV_PAYLOAD %s %s", topic, json.dumps(payload, separators=(",", ":"), ensure_ascii=False))

        if self.validate_schema:
            schema = self._find_schema_for_topic(topic)
            if schema is not None:
                try:
                    validate(instance=payload, schema=schema)
                except ValidationError as ve:
                    LOG.warning("Schema validation failed for topic %s: %s", topic, ve.message)
                    return

        now_epoch  = time.time()
        now_iso_ts = now_iso()
        if topic == self.imu_in:
            self._last_recv["imu"] = now_epoch
        elif topic == self.gps_in:
            self._last_recv["gps"] = now_epoch
        elif topic == self.batt_in:
            self._last_recv["battery"] = now_epoch

        if "ts" in payload and isinstance(payload["ts"], str) and payload["ts"].endswith("Z"):
            pass
        else:
            payload["ts"] = now_iso_ts
            payload["ts_source"] = "bridge"

        payload["_recv_ts"] = now_iso_ts

        if "seq" in payload:
            try:
                payload["sim_seq"] = int(payload["seq"])
            except Exception:
                payload["sim_seq"] = payload["seq"]

        payload["seq"] = int(self._pub_seq)
        self._pub_seq += 1

        payload["_forward_ts"] = now_iso()

        if topic == self.imu_in:
            qos = self.qos_imu
            out_topic = self.imu_out
        elif topic == self.gps_in:
            qos = self.qos_gps
            out_topic = self.gps_out
        elif topic == self.batt_in:
            qos = self.qos_batt
            out_topic = self.batt_out
        else:
            LOG.debug("Received message on unknown topic %s; ignoring", topic)
            return

        out_payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        if self.log_messages:
            LOG.info("SEND %s %s", out_topic, out_payload)

        info = self.client.publish(out_topic, payload=out_payload, qos=qos, retain=False)
        rc = getattr(info, "rc", None)
        mid = getattr(info, "mid", None)
        if self.log_messages:
            LOG.info(
                "Forwarded %s -> %s (qos=%d) rc=%s mid=%s seq=%s sim_seq=%s",
                topic, out_topic, qos, rc, mid, payload.get("seq"), payload.get("sim_seq"),
            )


    def start(self):
        if self.client is None:
            raise RuntimeError("MQTT client not initialized. Call read_config() first.")
        
        LOG.info("Starting esp32 client, connecting to %s:%d", self.broker_host, self.broker_port)
        
        self.running = True
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_start()
        try:
            while self.running:
                time.sleep(0.2)
        except KeyboardInterrupt:
            LOG.info("Keyboard interrupt received; stopping")
        finally:
            self.stop()


    def stop(self):
        LOG.info("Stopping esp32: publishing offline status and disconnecting")
        if self.client is None:
            self.running = False
            return
        if self.retain_status:
            payload = json.dumps({"status": "offline", "ts": now_iso()})
            try:
                self.client.publish(self.status_topic, payload=payload, qos=1, retain=True)
            except Exception:
                LOG.debug("Failed to publish offline status")
        self.running = False
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            LOG.debug("Exception while disconnecting: %s", e)
