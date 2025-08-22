from pathlib import Path
import configparser
from typing import Optional, List


class GPSConfigParser:
    def __init__(self, filename: str = "config.ini"):
        self.config = configparser.ConfigParser(inline_comment_prefixes=(";",))
        self.config.read(Path(filename))

    def _sec(self) -> Optional[configparser.SectionProxy]:
        if self.config.has_section("gps"):
            return self.config["gps"]
        return None

    def parse_baudrate(self) -> int:
        sec = self._sec()
        if sec is None:
            return 9600
        return sec.getint("baudrate", fallback=9600)

    def parse_protocol(self) -> str:
        sec = self._sec()
        if sec is None:
            return "nmea"
        return sec.get("protocol", fallback="nmea")

    def parse_use_ublox_binary(self) -> bool:
        sec = self._sec()
        if sec is None:
            return False
        return sec.getboolean("use_ublox_binary", fallback=False)

    def parse_update_rate_hz(self) -> float:
        sec = self._sec()
        if sec is None:
            return 1.0
        val = sec.get("update_rate_hz", None)
        if val is None:
            return 1.0
        try:
            return float(val)
        except Exception:
            # return raw so upper layer raises appropriate TypeError/ValueError
            return val

    def parse_nav_rate_ms(self) -> int:
        sec = self._sec()
        if sec is None:
            return 200
        return sec.getint("nav_rate_ms", fallback=200)

    def parse_fix_type(self) -> int:
        sec = self._sec()
        if sec is None:
            return 3
        return sec.getint("fix_type", fallback=3)

    def parse_num_svs(self) -> int:
        sec = self._sec()
        if sec is None:
            return 8
        return sec.getint("num_svs", fallback=8)

    def parse_initial_position(self):
        """
        Return (lat, lon, alt) — floats when possible, otherwise raw strings to let
        caller's setters raise consistent errors.
        """
        sec = self._sec()
        if sec is None:
            return (0.0, 0.0, 0.0)
        lat = sec.get("initial_lat", None)
        lon = sec.get("initial_lon", None)
        alt = sec.get("initial_alt", None)
        try:
            latf = float(lat) if lat is not None else None
            lonf = float(lon) if lon is not None else None
            altf = float(alt) if alt is not None else None
        except Exception:
            return (lat, lon, alt)
        return (latf, lonf, altf)

    def parse_pos_noise_m(self) -> float:
        sec = self._sec()
        if sec is None:
            return 0.0
        return sec.getfloat("pos_noise_m", fallback=0.0)

    def parse_alt_noise_m(self) -> float:
        sec = self._sec()
        if sec is None:
            return 0.0
        return sec.getfloat("alt_noise_m", fallback=0.0)

    def parse_vel_noise_m_s(self) -> float:
        sec = self._sec()
        if sec is None:
            return 0.0
        return sec.getfloat("vel_noise_m_s", fallback=0.0)

    def parse_hdop(self) -> float:
        sec = self._sec()
        if sec is None:
            return 1.0
        return sec.getfloat("hdop", fallback=1.0)

    def parse_nmea_sentences(self) -> Optional[List[str]]:
        sec = self._sec()
        if sec is None:
            return None
        raw = sec.get("nmea_sentences", fallback=None)
        if raw is None:
            return None
        # split by comma, strip, uppercase
        parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
        return parts if parts else None

    def parse_nmea_term(self) -> str:
        sec = self._sec()
        if sec is None:
            return "\\r\\n"
        return sec.get("nmea_term", fallback="\\r\\n")

    def parse_publish_rate_hz(self) -> float:
        sec = self._sec()
        if sec is None:
            return 1.0
        val = sec.get("publish_rate_hz", None)
        if val is None:
            return 1.0
        try:
            return float(val)
        except Exception:
            return val

    def parse_retain_messages(self) -> bool:
        sec = self._sec()
        if sec is None:
            return False
        return sec.getboolean("retain_messages", fallback=False)
