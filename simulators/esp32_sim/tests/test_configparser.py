import pytest
from pathlib import Path

from simulators.esp32_sim.lib.configparser import ESP32Parser
from simulators.esp32_sim.lib.esp32_sim import ESP32


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


def test_read_config_populates_properties(tmp_path):
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    esp = ESP32(cfg_path)
    esp.read_config()

    # broker
    assert esp.broker_host == "mosquitto"
    assert esp.broker_port == 1883

    # client
    assert esp.client_id == "esp32_sim"
    assert esp.retain_status is True

    # topics in/out
    assert esp.imu_in == "sim/imu"
    assert esp.gps_in == "sim/gps"
    assert esp.batt_in == "sim/battery"

    assert esp.imu_out == "sensor/imu"
    assert esp.gps_out == "sensor/gps"
    assert esp.batt_out == "sensor/battery"

    assert esp.status_topic == "sensor/status"

    # qos
    assert esp.qos_imu == 0
    assert esp.qos_gps == 1
    assert esp.qos_batt == 1

    # validation flags
    assert esp.validate_schema is True
    assert esp.schema_path == "../../shared/mqtt_topics.json"

    # mqtt client created
    assert esp.client is not None


def test_alternate_battery_keys_and_publish_qos(tmp_path):
    cfg_path = write_cfg(tmp_path, ALTERNATE_BATT_CONFIG)
    esp = ESP32(cfg_path)
    esp.read_config()

    assert esp.broker_host == "example-broker"
    assert esp.broker_port == 1884

    assert esp.client_id == "esp32_sim_alt"
    assert esp.retain_status is False

    # when publish_qos_batt is absent but publish_qos_battery present, it should be used
    assert esp.qos_batt == 2

    # batt_in / batt_out fallback
    assert esp.batt_in == "sim/battery_alt"
    assert esp.batt_out == "sensor/battery_alt"


def test_minimal_config_uses_defaults(tmp_path):
    cfg_path = write_cfg(tmp_path, MINIMAL_CONFIG)
    esp = ESP32(cfg_path)
    esp.read_config()

    # defaults from parser
    assert esp.broker_host == "localhost"
    assert esp.broker_port == 1883

    assert esp.client_id == "esp32_sim"
    assert esp.retain_status is True

    # default topics/qos
    assert esp.imu_in == "sim/imu"
    assert esp.gps_in == "sim/gps"
    assert esp.batt_in == "sim/battery"
    assert esp.imu_out == "sensor/imu"
    assert esp.gps_out == "sensor/gps"
    assert esp.batt_out == "sensor/battery"

    assert esp.qos_imu == 0
    assert esp.qos_gps == 1
    assert esp.qos_batt == 1


def test_broker_host_rejects_non_string():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.broker_host = 123
    with pytest.raises(TypeError):
        esp.broker_host = None


def test_broker_port_rejects_invalid_values():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.broker_port = "1883"
    with pytest.raises(TypeError):
        esp.broker_port = -1
    with pytest.raises(TypeError):
        esp.broker_port = 0


def test_client_id_rejects_non_string():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.client_id = 1234
    with pytest.raises(TypeError):
        esp.client_id = None


def test_retain_status_rejects_non_bool():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.retain_status = "true"
    with pytest.raises(TypeError):
        esp.retain_status = 1


def test_topic_setters_reject_invalid():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.imu_in = ""
    with pytest.raises(TypeError):
        esp.gps_in = None
    with pytest.raises(TypeError):
        esp.batt_in = 123


def test_qos_setters_reject_invalid():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.qos_imu = -1
    with pytest.raises(TypeError):
        esp.qos_gps = "1"


def test_validate_schema_and_schema_path_setters():
    esp = ESP32()
    with pytest.raises(TypeError):
        esp.validate_schema = "yes"
    with pytest.raises(TypeError):
        esp.schema_path = ""


def test_start_without_read_config_raises():
    esp = ESP32()  # no read_config called -> client is None
    with pytest.raises(RuntimeError):
        esp.start()
