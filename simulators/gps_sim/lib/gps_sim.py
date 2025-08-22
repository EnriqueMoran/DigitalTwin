"""Simple GPS simulator following a predefined scenario route.

This module intentionally mirrors a small subset of the behaviour of the
original project so that the existing unit tests continue to exercise the
configuration parser and the sampling functions.  The simulator exposes a
number of properties with validation logic and is able to produce noisy
NMEA sentences while following a route described by
``simulators/scenarios/main_scenario.json``.

Only the pieces of functionality required by the tests are implemented
here; the class is *not* a full featured GPS emulator.
"""

from __future__ import annotations

import configparser
import math
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import numpy as np

from simulators.scenarios.route import Scenario

# Signature of optional motion provider used by tests.  It should return
# (lat, lon, alt, speed_knots, course_deg, climb_m_s).
MotionProvider = Callable[[float], Tuple[float, float, float, float, float, float]]


class NEOM8N:
    """Very small GPS simulator that produces NMEA sentences."""

    # ------------------------------------------------------------------
    def __init__(
        self,
        cfg_path: str | None = None,
        scenario_path: str = "simulators/scenarios/main_scenario.json",
    ) -> None:
        self._cfg_path = Path(cfg_path) if cfg_path else None
        self._scenario = Scenario(scenario_path)
        self._rng: np.random.Generator | None = None
        self._last_t: float | None = None

        # sensible defaults so that property tests can instantiate without
        # providing a configuration file
        self._baudrate = 9600
        self._protocol = "nmea"
        self._use_ublox_binary = False
        self._update_rate_hz = 1.0
        self._nav_rate_ms = 1000
        self._fix_type = 3
        self._num_svs = 8
        self._initial_lat = 0.0
        self._initial_lon = 0.0
        self._initial_alt = 0.0
        self._pos_noise_m = 0.0
        self._alt_noise_m = 0.0
        self._vel_noise_m_s = 0.0
        self._hdop = 1.0
        self._nmea_sentences: List[str] = ["GGA"]
        self._nmea_term = "\r\n"
        self._publish_rate_hz = 1.0
        self._retain_messages = False

    # ------------------------------------------------------------------
    # Property helpers with validation

    @property
    def baudrate(self) -> int:
        return self._baudrate

    @baudrate.setter
    def baudrate(self, val: int) -> None:
        if not isinstance(val, int) or val <= 0:
            raise TypeError("baudrate must be positive int")
        self._baudrate = val

    @property
    def protocol(self) -> str:
        return self._protocol

    @protocol.setter
    def protocol(self, val: str) -> None:
        if val not in ("nmea", "ubx"):
            raise ValueError("protocol must be 'nmea' or 'ubx'")
        self._protocol = val

    @property
    def use_ublox_binary(self) -> bool:
        return self._use_ublox_binary

    @use_ublox_binary.setter
    def use_ublox_binary(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("use_ublox_binary must be bool")
        self._use_ublox_binary = val

    @property
    def update_rate_hz(self) -> float:
        return self._update_rate_hz

    @update_rate_hz.setter
    def update_rate_hz(self, val: float) -> None:
        if not isinstance(val, (int, float)) or val <= 0:
            raise TypeError("update_rate_hz must be positive number")
        self._update_rate_hz = float(val)

    @property
    def nav_rate_ms(self) -> int:
        return self._nav_rate_ms

    @nav_rate_ms.setter
    def nav_rate_ms(self, val: int) -> None:
        if not isinstance(val, int) or val <= 0:
            raise TypeError("nav_rate_ms must be positive int")
        self._nav_rate_ms = val

    @property
    def fix_type(self) -> int:
        return self._fix_type

    @fix_type.setter
    def fix_type(self, val: int) -> None:
        if val not in (0, 1, 2, 3):
            raise ValueError("fix_type must be 0..3")
        self._fix_type = int(val)

    @property
    def num_svs(self) -> int:
        return self._num_svs

    @num_svs.setter
    def num_svs(self, val: int) -> None:
        if not isinstance(val, int) or not (0 < val < 100):
            raise ValueError("num_svs must be int between 1 and 99")
        self._num_svs = val

    @property
    def initial_lat(self) -> float:
        return self._initial_lat

    @initial_lat.setter
    def initial_lat(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("initial_lat must be float")
        if not (-90.0 <= float(val) <= 90.0):
            raise ValueError("latitude out of range")
        self._initial_lat = float(val)

    @property
    def initial_lon(self) -> float:
        return self._initial_lon

    @initial_lon.setter
    def initial_lon(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("initial_lon must be float")
        if not (-180.0 <= float(val) <= 180.0):
            raise ValueError("longitude out of range")
        self._initial_lon = float(val)

    @property
    def initial_alt(self) -> float:
        return self._initial_alt

    @initial_alt.setter
    def initial_alt(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("initial_alt must be float")
        self._initial_alt = float(val)

    @property
    def initial_position(self) -> Tuple[float, float, float]:
        return self._initial_lat, self._initial_lon, self._initial_alt

    @initial_position.setter
    def initial_position(self, val: Iterable[float]) -> None:
        if not isinstance(val, Iterable):
            raise TypeError("initial_position must be iterable")
        vals = list(val)
        if len(vals) != 3 or not all(isinstance(v, (int, float)) for v in vals):
            raise TypeError("initial_position must be three floats")
        self.initial_lat, self.initial_lon, self.initial_alt = vals

    @property
    def pos_noise_m(self) -> float:
        return self._pos_noise_m

    @pos_noise_m.setter
    def pos_noise_m(self, val: float) -> None:
        if not isinstance(val, (int, float)) or val < 0:
            raise TypeError("pos_noise_m must be >=0 float")
        self._pos_noise_m = float(val)

    @property
    def alt_noise_m(self) -> float:
        return self._alt_noise_m

    @alt_noise_m.setter
    def alt_noise_m(self, val: float) -> None:
        if not isinstance(val, (int, float)) or val < 0:
            raise TypeError("alt_noise_m must be >=0 float")
        self._alt_noise_m = float(val)

    @property
    def vel_noise_m_s(self) -> float:
        return self._vel_noise_m_s

    @vel_noise_m_s.setter
    def vel_noise_m_s(self, val: float) -> None:
        if not isinstance(val, (int, float)) or val < 0:
            raise TypeError("vel_noise_m_s must be >=0 float")
        self._vel_noise_m_s = float(val)

    @property
    def hdop(self) -> float:
        return self._hdop

    @hdop.setter
    def hdop(self, val: float) -> None:
        if not isinstance(val, (int, float)) or val <= 0:
            raise TypeError("hdop must be positive float")
        self._hdop = float(val)

    @property
    def nmea_sentences(self) -> List[str]:
        return self._nmea_sentences

    @nmea_sentences.setter
    def nmea_sentences(self, val: Iterable[str]) -> None:
        if (not isinstance(val, Iterable)) or isinstance(val, (str, bytes)):
            raise TypeError("nmea_sentences must be iterable of strings")
        vals = [str(v).strip().upper() for v in val if str(v).strip()]
        if not vals:
            raise ValueError("nmea_sentences must contain at least one sentence")
        self._nmea_sentences = vals

    @property
    def nmea_term(self) -> str:
        return self._nmea_term

    @nmea_term.setter
    def nmea_term(self, val: str) -> None:
        if not isinstance(val, str):
            raise TypeError("nmea_term must be str")
        # Allow escaped sequences like "\r\n"
        self._nmea_term = val.encode().decode("unicode_escape")

    @property
    def publish_rate_hz(self) -> float:
        return self._publish_rate_hz

    @publish_rate_hz.setter
    def publish_rate_hz(self, val: float) -> None:
        if not isinstance(val, (int, float)) or val <= 0:
            raise TypeError("publish_rate_hz must be positive float")
        self._publish_rate_hz = float(val)

    @property
    def retain_messages(self) -> bool:
        return self._retain_messages

    @retain_messages.setter
    def retain_messages(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("retain_messages must be bool")
        self._retain_messages = val

    # ------------------------------------------------------------------
    def read_config(self) -> None:
        """Populate properties from an INI file."""

        if self._cfg_path is None:
            return

        cfg = configparser.ConfigParser()
        cfg.read(self._cfg_path)
        if not cfg.has_section("gps"):
            return  # keep defaults if GPS section missing
        g = cfg["gps"]

        # Parse using setters for validation
        self.baudrate = g.getint("baudrate", self._baudrate)
        self.protocol = g.get("protocol", self._protocol)
        self.use_ublox_binary = g.getboolean("use_ublox_binary", self._use_ublox_binary)
        self.update_rate_hz = g.getfloat("update_rate_hz", self._update_rate_hz)
        self.nav_rate_ms = g.getint("nav_rate_ms", int(1000 / self._update_rate_hz))
        self.fix_type = g.getint("fix_type", self._fix_type)
        self.num_svs = g.getint("num_svs", self._num_svs)
        self.initial_lat = g.getfloat("initial_lat", self._initial_lat)
        self.initial_lon = g.getfloat("initial_lon", self._initial_lon)
        self.initial_alt = g.getfloat("initial_alt", self._initial_alt)
        self.pos_noise_m = g.getfloat("pos_noise_m", self._pos_noise_m)
        self.alt_noise_m = g.getfloat("alt_noise_m", self._alt_noise_m)
        self.vel_noise_m_s = g.getfloat("vel_noise_m_s", self._vel_noise_m_s)
        self.hdop = g.getfloat("hdop", self._hdop)
        sentences = g.get("nmea_sentences", ",".join(self._nmea_sentences))
        self.nmea_sentences = [s.strip() for s in sentences.split(",") if s.strip()]
        self.nmea_term = g.get("nmea_term", "\r\n")
        self.publish_rate_hz = g.getfloat("publish_rate_hz", self._publish_rate_hz)
        self.retain_messages = g.getboolean("retain_messages", self._retain_messages)

    # ------------------------------------------------------------------
    def init_sim(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)
        self._last_t = None

    # ------------------------------------------------------------------
    def sample(self, t: float, motion_provider: MotionProvider | None = None) -> Dict:
        if self._rng is None:
            raise RuntimeError("GPS not initialized")
        if self._last_t is not None and t < self._last_t:
            raise ValueError("time must be monotonic")
        self._last_t = t

        if motion_provider is None:
            lat, lon, speed_m_s, heading = self._scenario.state_at(t)
            alt = self._initial_alt
            speed_knots = speed_m_s * 1.94384
            course_deg = heading
            climb = 0.0
        else:
            lat, lon, alt, speed_knots, course_deg, climb = motion_provider(t)

        truth = {
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "speed_knots": speed_knots,
            "course_deg": course_deg,
            "climb_m_s": climb,
        }

        lat_n = self._rng.normal(0.0, self._pos_noise_m / 111_111.0)
        lon_n = self._rng.normal(
            0.0,
            self._pos_noise_m
            / (111_111.0 * max(math.cos(math.radians(lat)), 1e-6)),
        )
        alt_n = self._rng.normal(0.0, self._alt_noise_m)
        spd_n = self._rng.normal(0.0, self._vel_noise_m_s * 1.94384)

        meas = {
            "lat": lat + lat_n,
            "lon": lon + lon_n,
            "alt": alt + alt_n,
            "speed_knots": speed_knots + spd_n,
            "course_deg": course_deg,
            "climb_m_s": climb,
        }

        nmea: List[str] = []
        for st in self._nmea_sentences:
            st = st.upper()
            if st == "GGA":
                body = (
                    f"GPGGA,{lat:.6f},{lon:.6f},1,{self._num_svs:02d},{self._hdop:.1f},"
                    f"{alt:.1f},M,0.0,M,,"
                )
            elif st == "RMC":
                body = (
                    f"GPRMC,{t:06.1f},A,{lat:.6f},N,{lon:.6f},E,"
                    f"{speed_knots:.1f},{course_deg:.1f},000000,,"
                )
            elif st == "VTG":
                body = (
                    f"GPVTG,{course_deg:.1f},T,,M,{speed_knots:.1f},N,{speed_knots*1.852:.1f},K"
                )
            else:
                continue
            nmea.append(self._with_checksum(body))

        return {"meas": meas, "truth": truth, "nmea": nmea}

    # ------------------------------------------------------------------
    def _with_checksum(self, body: str) -> str:
        cs = 0
        for ch in body:
            cs ^= ord(ch)
        return f"${body}*{cs:02X}{self._nmea_term}"

    # ------------------------------------------------------------------
    def simulate(self, duration: float, motion_provider: MotionProvider | None = None) -> Dict:
        n = math.floor(self._update_rate_hz * duration) + 1
        t = np.linspace(0.0, (n - 1) / self._update_rate_hz, n)
        meas_list: List[Dict] = []
        truth_list: List[Dict] = []
        nmea_list: List[List[str]] = []
        for ti in t:
            s = self.sample(ti, motion_provider)
            meas_list.append(s["meas"])
            truth_list.append(s["truth"])
            nmea_list.append(s["nmea"])
        return {"t": t, "meas": meas_list, "truth": truth_list, "nmea": nmea_list}

