import configparser
import math
from pathlib import Path
from typing import Callable, Dict, List, Tuple

import numpy as np

from simulators.scenarios.route import Scenario

MotionProvider = Callable[[float], Tuple[float, float, float, float, float, float]]


class NEOM8N:
    """Very small GPS simulator that produces NMEA sentences."""

    def __init__(self, cfg_path: str,
                 scenario_path: str = "simulators/scenarios/main_scenario.json"):
        self._cfg_path = Path(cfg_path)
        self._scenario = Scenario(scenario_path)
        self._rng: np.random.Generator | None = None

    # ------------------------------------------------------------------
    def read_config(self) -> None:
        cfg = configparser.ConfigParser()
        cfg.read(self._cfg_path)
        g = cfg["gps"]
        self._update_rate_hz = g.getfloat("update_rate_hz", 1.0)
        self._pos_noise_m = g.getfloat("pos_noise_m", 0.0)
        self._alt_noise_m = g.getfloat("alt_noise_m", 0.0)
        self._vel_noise_m_s = g.getfloat("vel_noise_m_s", 0.0)
        self._num_svs = g.getint("num_svs", 8)
        self._hdop = g.getfloat("hdop", 0.9)
        self._nmea_sentences = [s.strip() for s in g.get("nmea_sentences", "GGA,RMC,VTG").split(",") if s.strip()]
        term_raw = g.get("nmea_term", "\\r\\n")
        self._nmea_term = term_raw.encode().decode("unicode_escape")
        self._initial_lat = g.getfloat("initial_lat", 0.0)
        self._initial_lon = g.getfloat("initial_lon", 0.0)
        self._initial_alt = g.getfloat("initial_alt", 0.0)

    # ------------------------------------------------------------------
    def init_sim(self, seed: int | None = None) -> None:
        self._rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    def sample(self, t: float, motion_provider: MotionProvider | None = None) -> Dict:
        if self._rng is None or not hasattr(self, "_update_rate_hz"):
            raise RuntimeError("GPS not initialized")

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

        # Gaussian noise conversions
        lat_n = self._rng.normal(0.0, self._pos_noise_m / 111_111.0)
        lon_n = self._rng.normal(0.0, self._pos_noise_m / (111_111.0 * max(math.cos(math.radians(lat)), 1e-6)))
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
