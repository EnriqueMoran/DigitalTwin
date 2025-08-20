import pytest
from pathlib import Path
from simulators.esp32_sim.lib.configparser import ESP32Parser

VALID_CONFIG = """
[broker]
host = mosquitto
port = 1883

[esp32]
client_id = esp32_sim
retain_status = true
publish_qos_imu = 0
publish_qos_gps = 1
publish_qos_batt = 1
validate_schema = true
schema_path = ../../shared/mqtt_topics.json

[topics]
imu_in = sim/imu
gps_in = sim/gps
battery_in = sim/battery

imu_out = sensor/imu
gps_out = sensor/gps
battery_out = sensor/battery

status_topic = sensor/status
"""

ALTERNATE_BATT_CONFIG = """
[broker]
host = example-broker
port = 1884

[esp32]
client_id = esp32_sim_alt
retain_status = false
publish_qos_imu = 0
publish_qos_gps = 1
publish_qos_battery = 2
validate_schema = false

[topics]
imu_in = sim/imu
gps_in = sim/gps
batt_in = sim/battery_alt

imu_out = sensor/imu
gps_out = sensor/gps
batt_out = sensor/battery_alt

status_topic = sensor/status
"""

MINIMAL_CONFIG = """
[broker]

[esp32]

[topics]
"""


def write_cfg(tmp_path: Path, content: str) -> str:
    p = tmp_path / "esp32_config.ini"
    p.write_text(content.strip() + "\n", encoding="utf-8")
    return str(p)


def test_full_config_parsed_correctly(tmp_path):
    """Full example config: all parse_* helpers should return expected values."""
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    parser = ESP32Parser(cfg_path)

    # broker
    assert parser.parse_broker_host() == "mosquitto"
    assert parser.parse_broker_port() == 1883

    # esp32 fields
    assert parser.parse_client_id() == "esp32_sim"
    assert parser.parse_retain_status() is True

    # qos
    assert parser.parse_publish_qos_imu()  == 0
    assert parser.parse_publish_qos_gps()  == 1
    assert parser.parse_publish_qos_batt() == 1

    # validation flags
    assert parser.parse_validate_schema() is True
    assert parser.parse_schema_path() == "../../shared/mqtt_topics.json"

    # topics
    assert parser.parse_imu_in() == "sim/imu"
    assert parser.parse_gps_in() == "sim/gps"
    assert parser.parse_battery_in() == "sim/battery"
    assert parser.parse_imu_out() == "sensor/imu"
    assert parser.parse_gps_out() == "sensor/gps"
    assert parser.parse_battery_out()  == "sensor/battery"
    assert parser.parse_status_topic() == "sensor/status"

    # aggregators
    broker_cfg = parser.get_broker_cfg()
    assert broker_cfg["host"] == "mosquitto"
    assert broker_cfg["port"] == 1883

    qos_map = parser.get_qos_map()
    assert qos_map == {"imu": 0, "gps": 1, "battery": 1}

    topics_map = parser.get_topics_map()
    assert topics_map["imu_in"] == "sim/imu"
    assert topics_map["battery_out"]  == "sensor/battery"
    assert topics_map["status_topic"] == "sensor/status"


def test_alternate_battery_keys_and_publish_qos(tmp_path):
    """Support alternate keys 'batt_in' / 'batt_out' and 'publish_qos_battery' fallback."""
    cfg_path = write_cfg(tmp_path, ALTERNATE_BATT_CONFIG)
    parser = ESP32Parser(cfg_path)

    # broker
    assert parser.parse_broker_host() == "example-broker"
    assert parser.parse_broker_port() == 1884

    # esp32 fields
    assert parser.parse_client_id() == "esp32_sim_alt"
    assert parser.parse_retain_status() is False

    # publish qos: when publish_qos_batt is absent but publish_qos_battery present,
    # parser.parse_publish_qos_batt should return the publish_qos_battery value (2)
    assert parser.parse_publish_qos_batt() == 2

    # topics: batt_in / batt_out fallbacks should be picked up
    assert parser.parse_battery_in()  == "sim/battery_alt"
    assert parser.parse_battery_out() == "sensor/battery_alt"

    # convenience maps should reflect the alternate names
    topics_map = parser.get_topics_map()
    assert topics_map["battery_in"]  == "sim/battery_alt"
    assert topics_map["battery_out"] == "sensor/battery_alt"


def test_minimal_config_uses_defaults(tmp_path):
    """When keys are missing, parser should return sensible defaults (no exceptions)."""
    cfg_path = write_cfg(tmp_path, MINIMAL_CONFIG)
    parser = ESP32Parser(cfg_path)

    # defaults
    assert parser.parse_broker_host() == "localhost"
    assert parser.parse_broker_port() == 1883

    assert parser.parse_client_id() == "esp32_sim"
    # retain_status defaults to True per parser implementation
    assert parser.parse_retain_status() is True

    # QoS defaults
    assert parser.parse_publish_qos_imu() == 0
    assert parser.parse_publish_qos_gps() == 1
    # battery default
    assert parser.parse_publish_qos_batt() == 1

    # topics defaults
    assert parser.parse_imu_in() == "sim/imu"
    assert parser.parse_gps_in() == "sim/gps"
    assert parser.parse_battery_in() == "sim/battery"
    assert parser.parse_imu_out() == "sensor/imu"
    assert parser.parse_gps_out() == "sensor/gps"
    assert parser.parse_battery_out()  == "sensor/battery"
    assert parser.parse_status_topic() == "sensor/status"


def test_get_qos_map_and_broker_cfg(tmp_path):
    """Aggregated helper methods should return consistent dicts."""
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    parser = ESP32Parser(cfg_path)

    qos_map = parser.get_qos_map()
    assert isinstance(qos_map, dict)
    assert qos_map["imu"] == 0
    assert qos_map["gps"] == 1
    assert qos_map["battery"] == 1

    broker = parser.get_broker_cfg()
    assert broker["host"] == "mosquitto"
    assert broker["port"] == 1883
