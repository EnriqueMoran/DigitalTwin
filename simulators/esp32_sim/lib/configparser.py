from pathlib import Path
import configparser
from typing import Dict


class ESP32Parser:
    def __init__(self, filename: str = "config.ini"):
        self.config = configparser.ConfigParser(inline_comment_prefixes=(";",))
        self.config.read(Path(filename))

    #  Broker
    def parse_broker_host(self) -> str:
        return self.config["broker"].get("host", "localhost")

    def parse_broker_port(self) -> int:
        return self.config["broker"].getint("port", fallback=1883)

    #  ESP32 / client settings
    def parse_client_id(self) -> str:
        return self.config["esp32"].get("client_id", fallback="esp32_sim")

    def parse_retain_status(self) -> bool:
        return self.config["esp32"].getboolean("retain_status", fallback=True)

    def parse_publish_qos_imu(self) -> int:
        return self.config["esp32"].getint("publish_qos_imu", fallback=0)

    def parse_publish_qos_gps(self) -> int:
        return self.config["esp32"].getint("publish_qos_gps", fallback=1)

    def parse_publish_qos_batt(self) -> int:
        return self.config["esp32"].getint("publish_qos_battery", fallback=1)

    def parse_validate_schema(self) -> bool:
        return self.config["esp32"].getboolean("validate_schema", fallback=False)

    def parse_schema_path(self) -> str:
        return self.config["esp32"].get("schema_path", fallback="mqtt_topics_v1.json")

    def parse_log_messages(self) -> bool:
        return self.config["esp32"].getboolean("log_messages", fallback=False)

    #  Topics
    def parse_imu_in(self) -> str:
        return self.config["topics"].get("imu_in", fallback="sim/imu")

    def parse_gps_in(self) -> str:
        return self.config["topics"].get("gps_in", fallback="sim/gps")

    def parse_battery_in(self) -> str:
        return self.config["topics"].get("battery_in", fallback="sim/battery")

    def parse_imu_out(self) -> str:
        return self.config["topics"].get("imu_out", fallback="sensor/imu")

    def parse_gps_out(self) -> str:
        return self.config["topics"].get("gps_out", fallback="sensor/gps")

    def parse_battery_out(self) -> str:
        return self.config["topics"].get("battery_out", fallback="sensor/battery")

    def parse_status_topic(self) -> str:
        return self.config["topics"].get("status_topic", fallback="sensor/status")

    def get_broker_cfg(self) -> Dict[str, object]:
        return {
            "host": self.parse_broker_host(),
            "port": self.parse_broker_port(),
        }

    def get_qos_map(self) -> Dict[str, int]:
        return {
            "imu": self.parse_publish_qos_imu(),
            "gps": self.parse_publish_qos_gps(),
            "battery": self.parse_publish_qos_batt(),
        }

    def get_topics_map(self) -> Dict[str, str]:
        return {
            "imu_in": self.parse_imu_in(),
            "gps_in": self.parse_gps_in(),
            "battery_in": self.parse_battery_in(),
            "imu_out": self.parse_imu_out(),
            "gps_out": self.parse_gps_out(),
            "battery_out": self.parse_battery_out(),
            "status_topic": self.parse_status_topic(),
        }