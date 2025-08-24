from typing import Callable, Dict, Any, List, Optional, Tuple
from pathlib import Path
import math
import time
import numpy as np
from datetime import datetime, timezone

from simulators.gps_sim.lib.configparser import GPSConfigParser


# MotionProvider signature for GPS:
# Given time t (seconds), return tuple:
# (lat_deg, lon_deg, alt_m, speed_knots, course_deg, climb_m_s)
MotionProvider = Callable[[float], Tuple[float, float, float, float, float, float]]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _nmea_checksum(s: str) -> str:
    """
    Compute NMEA checksum for the string between '$' and '*' (exclusive).
    Return two hex uppercase characters.
    """
    cs = 0
    for ch in s:
        cs ^= ord(ch)
    return f"{cs:02X}"


def _format_lat(lat: float) -> Tuple[str, str]:
    """
    Convert decimal degrees latitude into NMEA ddmm.mmmm and hemisphere.
    """
    hemi = "N" if lat >= 0 else "S"
    lat = abs(lat)
    deg = int(lat)
    minutes = (lat - deg) * 60.0
    ddmm = f"{deg:02d}{minutes:07.4f}"
    return ddmm, hemi


def _format_lon(lon: float) -> Tuple[str, str]:
    """
    Convert decimal degrees longitude into NMEA dddmm.mmmm and hemisphere.
    """
    hemi = "E" if lon >= 0 else "W"
    lon = abs(lon)
    deg = int(lon)
    minutes = (lon - deg) * 60.0
    dddmm = f"{deg:03d}{minutes:07.4f}"
    return dddmm, hemi


class NEOM8N:
    def __init__(self, config_file: str = "config.ini"):
        self.config_file = Path(config_file)

        # raw backing fields
        self._baudrate: Optional[int] = None
        self._protocol: Optional[str] = None
        self._use_ublox_binary: Optional[bool] = None

        self._update_rate_hz: Optional[float] = None
        self._nav_rate_ms: Optional[int] = None

        self._fix_type: Optional[int] = None
        self._num_svs: Optional[int] = None

        self._initial_lat: Optional[float] = None
        self._initial_lon: Optional[float] = None
        self._initial_alt: Optional[float] = None

        self._speed_knots_cfg: Optional[float] = None
        self._course_deg_cfg: Optional[float] = None
        self._climb_m_s_cfg: Optional[float] = None

        self._pos_noise_m: Optional[float] = None
        self._alt_noise_m: Optional[float] = None
        self._vel_noise_m_s: Optional[float] = None
        self._hdop: Optional[float] = None

        self._nmea_sentences: Optional[List[str]] = None
        self._nmea_term: Optional[str] = None

        self._publish_rate_hz: Optional[float] = None
        self._retain_messages: Optional[bool] = None

        self._rng: Optional[np.random.Generator] = None
        self._t: float = 0.0
        self._dt: Optional[float] = None
        self._t_next: Optional[float] = None

        # For monotonic-time checks on sample()
        self._last_sample_t: Optional[float] = None

        self._truth_lat = None
        self._truth_lon = None
        self._truth_alt = None
        self._truth_speed_knots = None
        self._truth_course_deg = None
        self._truth_climb_m_s = None

    # ---------------------
    # Properties (validated)
    # ---------------------
    @property
    def baudrate(self) -> Optional[int]:
        return self._baudrate

    @baudrate.setter
    def baudrate(self, val: int) -> None:
        if not isinstance(val, int) or val <= 0:
            raise TypeError("baudrate must be a positive integer")
        self._baudrate = val

    @property
    def protocol(self) -> Optional[str]:
        return self._protocol

    @protocol.setter
    def protocol(self, val: str) -> None:
        if not isinstance(val, str):
            raise TypeError("protocol must be a string ('nmea' or 'ubx')")
        v = val.strip().lower()
        if v not in ("nmea", "ubx"):
            raise ValueError("protocol must be 'nmea' or 'ubx'")
        self._protocol = v

    @property
    def use_ublox_binary(self) -> Optional[bool]:
        return self._use_ublox_binary

    @use_ublox_binary.setter
    def use_ublox_binary(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("use_ublox_binary must be a boolean")
        self._use_ublox_binary = val

    @property
    def update_rate_hz(self) -> Optional[float]:
        return self._update_rate_hz

    @update_rate_hz.setter
    def update_rate_hz(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("update_rate_hz must be a number")
        valf = float(val)
        if valf <= 0.0:
            raise TypeError("update_rate_hz must be > 0")
        self._update_rate_hz = valf
        self._dt = 1.0 / valf

    @property
    def nav_rate_ms(self) -> Optional[int]:
        return self._nav_rate_ms

    @nav_rate_ms.setter
    def nav_rate_ms(self, val: int) -> None:
        if not isinstance(val, int) or val <= 0:
            raise TypeError("nav_rate_ms must be a positive integer")
        self._nav_rate_ms = val

    @property
    def fix_type(self) -> Optional[int]:
        return self._fix_type

    @fix_type.setter
    def fix_type(self, val: int) -> None:
        if not isinstance(val, int):
            raise TypeError("fix_type must be an integer")
        if val < 0 or val > 3:
            raise ValueError("fix_type must be 0..3")
        self._fix_type = val

    @property
    def num_svs(self) -> Optional[int]:
        return self._num_svs

    @num_svs.setter
    def num_svs(self, val: int) -> None:
        if not isinstance(val, int):
            raise TypeError("num_svs must be an integer")
        if val < 0 or val > 64:
            raise ValueError("num_svs out of reasonable range")
        self._num_svs = val

    @property
    def initial_lat(self) -> Optional[float]:
        return self._initial_lat

    @initial_lat.setter
    def initial_lat(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("initial_lat must be a number")
        vf = float(val)
        if vf < -90.0 or vf > 90.0:
            raise ValueError("initial_lat must be between -90 and 90")
        self._initial_lat = vf

    @property
    def initial_lon(self) -> Optional[float]:
        return self._initial_lon

    @initial_lon.setter
    def initial_lon(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("initial_lon must be a number")
        vf = float(val)
        if vf < -180.0 or vf > 180.0:
            raise ValueError("initial_lon must be between -180 and 180")
        self._initial_lon = vf

    @property
    def initial_alt(self) -> Optional[float]:
        return self._initial_alt

    @initial_alt.setter
    def initial_alt(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("initial_alt must be a number")
        self._initial_alt = float(val)

    @property
    def initial_position(self):
        return (self._initial_lat, self._initial_lon, self._initial_alt)

    @initial_position.setter
    def initial_position(self, val) -> None:
        if not isinstance(val, (list, tuple)) or len(val) != 3:
            raise TypeError("initial_position must be a tuple/list of (lat, lon, alt)")
        # let individual setters validate types/ranges
        self.initial_lat = val[0]
        self.initial_lon = val[1]
        self.initial_alt = val[2]

    @property
    def pos_noise_m(self) -> Optional[float]:
        return self._pos_noise_m

    @pos_noise_m.setter
    def pos_noise_m(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("pos_noise_m must be a number")
        vf = float(val)
        if vf < 0.0:
            raise TypeError("pos_noise_m must be non-negative")
        self._pos_noise_m = vf

    @property
    def alt_noise_m(self) -> Optional[float]:
        return self._alt_noise_m

    @alt_noise_m.setter
    def alt_noise_m(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("alt_noise_m must be a number")
        vf = float(val)
        if vf < 0.0:
            raise TypeError("alt_noise_m must be non-negative")
        self._alt_noise_m = vf

    @property
    def vel_noise_m_s(self) -> Optional[float]:
        return self._vel_noise_m_s

    @vel_noise_m_s.setter
    def vel_noise_m_s(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("vel_noise_m_s must be a number")
        vf = float(val)
        if vf < 0.0:
            raise TypeError("vel_noise_m_s must be non-negative")
        self._vel_noise_m_s = vf

    @property
    def hdop(self) -> Optional[float]:
        return self._hdop

    @hdop.setter
    def hdop(self, val) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("hdop must be a number")
        vf = float(val)
        if vf <= 0.0:
            raise TypeError("hdop must be > 0")
        self._hdop = vf

    @property
    def nmea_sentences(self) -> Optional[List[str]]:
        return self._nmea_sentences

    @nmea_sentences.setter
    def nmea_sentences(self, val) -> None:
        if isinstance(val, str):
            raise TypeError("nmea_sentences must be a list/tuple of strings, not a plain string")
        if val is None:
            self._nmea_sentences = None
            return
        if not isinstance(val, (list, tuple)) or len(val) == 0:
            raise ValueError("nmea_sentences must be a non-empty list/tuple of sentence ids")
        if not all(isinstance(x, str) for x in val):
            raise TypeError("nmea_sentences must be list/tuple of strings")
        self._nmea_sentences = [x.strip().upper() for x in val]

    @property
    def nmea_term(self) -> Optional[str]:
        return self._nmea_term

    @nmea_term.setter
    def nmea_term(self, val: str) -> None:
        if not isinstance(val, str):
            raise TypeError("nmea_term must be a string (use \\r\\n or actual CRLF)")
        # Accept escaped sequences like "\\r\\n" and convert them to real characters
        if "\\r" in val or "\\n" in val or "\\t" in val:
            decoded = val.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")
            self._nmea_term = decoded
        else:
            self._nmea_term = val

    @property
    def publish_rate_hz(self) -> Optional[float]:
        return self._publish_rate_hz

    @publish_rate_hz.setter
    def publish_rate_hz(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("publish_rate_hz must be a number")
        vf = float(val)
        if vf <= 0.0:
            raise TypeError("publish_rate_hz must be > 0")
        self._publish_rate_hz = vf

    @property
    def retain_messages(self) -> Optional[bool]:
        return self._retain_messages

    @retain_messages.setter
    def retain_messages(self, val: bool) -> None:
        if not isinstance(val, bool):
            raise TypeError("retain_messages must be boolean")
        self._retain_messages = val

    # ---------------------
    # Config loading
    # ---------------------
    def read_config(self) -> None:
        parser = GPSConfigParser(str(self.config_file))

        # transport / formatting
        self.baudrate = parser.parse_baudrate()
        self.protocol = parser.parse_protocol()
        self.use_ublox_binary = parser.parse_use_ublox_binary()

        # timing / rates
        # parser returns float or raw -> setter will validate
        self.update_rate_hz = parser.parse_update_rate_hz()
        self.nav_rate_ms = parser.parse_nav_rate_ms()

        # fix / sats
        self.fix_type = parser.parse_fix_type()
        self.num_svs = parser.parse_num_svs()

        # initial position (parser returns floats when possible)
        lat, lon, alt = parser.parse_initial_position()
        # Use individual setters to enforce ranges
        self.initial_lat = lat
        self.initial_lon = lon
        self.initial_alt = alt

        # kinematics if present (parser may omit -> use defaults)
        try:
            self._speed_knots_cfg = parser.parse_publish_rate_hz()  # (not used here); keep compat
        except Exception:
            pass
        # noise & publishing
        self.pos_noise_m = parser.parse_pos_noise_m()
        self.alt_noise_m = parser.parse_alt_noise_m()
        self.vel_noise_m_s = parser.parse_vel_noise_m_s()
        self.hdop = parser.parse_hdop()

        # nmea formatting / publishing
        nmea_sent = parser.parse_nmea_sentences()
        self.nmea_sentences = nmea_sent if nmea_sent is not None else None
        self.nmea_term = parser.parse_nmea_term()
        self.publish_rate_hz = parser.parse_publish_rate_hz()
        self.retain_messages = parser.parse_retain_messages()

        # compute dt if update_rate_hz was set by setter
        if self._update_rate_hz is None:
            self._update_rate_hz = 1.0
            self._dt = 1.0

        # initialize internal truth from config
        self._truth_lat = float(self._initial_lat)
        self._truth_lon = float(self._initial_lon)
        self._truth_alt = float(self._initial_alt)
        self._truth_speed_knots = float(self._speed_knots_cfg or 0.0)
        self._truth_course_deg = float(self._course_deg_cfg or 0.0)
        self._truth_climb_m_s = float(self._climb_m_s_cfg or 0.0)

    # ---------------------
    # RNG / simulation init
    # ---------------------
    def init_sim(self, seed: Optional[int] = None) -> None:
        """
        Prepare RNG and scheduling. Must call read_config() first.
        """
        if self._dt is None:
            raise RuntimeError("Call read_config() before init_sim()")

        self._rng = np.random.default_rng(seed)
        self._t = 0.0
        self._t_next = 0.0
        self._last_sample_t = None

    @staticmethod
    def _knots_to_m_s(knots: float) -> float:
        return float(knots) * 0.514444

    @staticmethod
    def _m_s_to_knots(m_s: float) -> float:
        return float(m_s) / 0.514444

    @staticmethod
    def _move_lat_lon(lat_deg: float, lon_deg: float, north_m: float, east_m: float) -> Tuple[float, float]:
        """
        Move lat/lon by north_m (meters) and east_m (meters) using simple equirectangular approx
        good for small distances.
        """
        R = 6371000.0  # earth radius meters
        lat_rad = math.radians(lat_deg)
        dlat = north_m / R
        dlon = east_m / (R * math.cos(lat_rad))
        new_lat = lat_deg + math.degrees(dlat)
        new_lon = lon_deg + math.degrees(dlon)
        return new_lat, new_lon

    def _apply_motion_internal(self, dt: float) -> None:
        """
        Integrate the simple constant-velocity motion model for dt seconds updating
        internal truth: lat, lon, alt, using speed and course.
        """
        speed_m_s = self._knots_to_m_s(self._truth_speed_knots)
        distance = speed_m_s * dt
        # course_deg: 0 = North, 90 = East
        heading_rad = math.radians(self._truth_course_deg)
        north = distance * math.cos(heading_rad)
        east = distance * math.sin(heading_rad)
        self._truth_lat, self._truth_lon = self._move_lat_lon(self._truth_lat, self._truth_lon, north, east)
        self._truth_alt += self._truth_climb_m_s * dt

    def _add_noise(self, lat: float, lon: float, alt: float, speed_knots: float) -> Tuple[float, float, float, float]:
        """
        Add gaussian noise to position, altitude and speed according to config sigmas.
        Returns (lat_noisy, lon_noisy, alt_noisy, speed_knots_noisy)
        """
        if self._rng is None:
            rng = np.random.default_rng()
        else:
            rng = self._rng

        # Positional noise: sample in local east/north and convert to lat/lon offset
        sigma = float(self._pos_noise_m or 0.0)
        if sigma > 0.0:
            east = rng.normal(loc=0.0, scale=sigma)
            north = rng.normal(loc=0.0, scale=sigma)
            lat_n, lon_n = self._move_lat_lon(lat, lon, north, east)
        else:
            lat_n, lon_n = lat, lon

        alt_sigma = float(self._alt_noise_m or 0.0)
        alt_n = alt + (rng.normal(loc=0.0, scale=alt_sigma) if alt_sigma > 0.0 else 0.0)

        vel_sigma = float(self._vel_noise_m_s or 0.0)
        speed_m_s = self._knots_to_m_s(float(speed_knots))
        speed_m_s_n = speed_m_s + (rng.normal(loc=0.0, scale=vel_sigma) if vel_sigma > 0.0 else 0.0)
        speed_knots_n = self._m_s_to_knots(speed_m_s_n)
        return lat_n, lon_n, alt_n, speed_knots_n

    def sample(self, t: float, motion_provider: Optional[MotionProvider] = None) -> Dict[str, Any]:
        """
        Produce a single simulated measurement at time t (seconds).
        If motion_provider is provided, the 'truth' state is taken from it; otherwise
        internal constant-velocity integration is used.
        Returns a dict with fields:
            {
              "ts_epoch": float,
              "ts_iso": str,
              "fix_type": int,
              "num_svs": int,
              "hdop": float,
              "truth": {"lat":..., "lon":..., "alt":..., "speed":..., "course_deg":..., "climb_m_s":...},
              "meas": {"lat":..., "lon":..., "alt":..., "speed":..., "course_deg":...},
              "nmea": ["$GPGGA,...*CS<term>", ...]   # present only if protocol == 'nmea'
            }
        """
        if self._dt is None:
            raise RuntimeError("Simulator not configured. Call read_config() and init_sim() first.")

        # Monotonic-time check across calls (tests expect ValueError on decreasing time)
        if self._last_sample_t is not None and t < self._last_sample_t - 1e-9:
            raise ValueError("sample() called with decreasing time")

        # Determine truth
        if motion_provider is not None:
            lat_t, lon_t, alt_t, sp_knots_t, course_t, climb_t = motion_provider(t)
            truth_lat = float(lat_t)
            truth_lon = float(lon_t)
            truth_alt = float(alt_t)
            truth_speed_knots = float(sp_knots_t)
            truth_course_deg = float(course_t)
            truth_climb = float(climb_t)
            # update last sample time even if not using internal integration
            self._last_sample_t = float(t)
        else:
            # advance internal truth from previous internal time (self._t) to t
            dt = float(t - self._t)
            if dt < -1e-9:
                # time went backwards; not supported
                raise ValueError("sample() called with decreasing time")
            if dt > 0:
                # integrate by dt
                self._apply_motion_internal(dt)
                self._t = float(t)
            truth_lat = float(self._truth_lat)
            truth_lon = float(self._truth_lon)
            truth_alt = float(self._truth_alt)
            truth_speed_knots = float(self._truth_speed_knots)
            truth_course_deg = float(self._truth_course_deg)
            truth_climb = float(self._truth_climb_m_s)
            self._last_sample_t = float(t)

        # measured = truth + noise
        lat_m, lon_m, alt_m, speed_knots_m = self._add_noise(truth_lat, truth_lon, truth_alt, truth_speed_knots)

        # HDOP, fix and sats come from config
        hdop = float(self._hdop or 1.0)
        fix = int(self._fix_type or 3)
        svs = int(self._num_svs or 8)

        ts_epoch = time.time()
        ts_iso = now_iso()

        meas = {
            "lat": lat_m,
            "lon": lon_m,
            "alt": alt_m,
            "speed": speed_knots_m,
            "course_deg": float(truth_course_deg),
            "climb_m_s": float(truth_climb),
            "fix_type": fix,
            "num_svs": svs,
            "hdop": hdop,
            "ts": ts_iso,
            "ts_epoch": ts_epoch,
        }

        # Optionally build NMEA sentences
        nmea_list: List[str] = []
        if self._protocol == "nmea":
            # GGA
            # time in hhmmss format from current UTC time
            utc = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)
            timestr = utc.strftime("%H%M%S.%f")[:9]  # hhmmss.ss
            lat_s, lat_h = _format_lat(lat_m)
            lon_s, lon_h = _format_lon(lon_m)
            gga_parts = [
                "GPGGA",
                timestr,
                lat_s,
                lat_h,
                lon_s,
                lon_h,
                str(fix),
                f"{svs:d}",
                f"{hdop:.1f}",
                f"{alt_m:.1f}",
                "M",
                "0.0", "M",  # geoid separation placeholder
                ""  # age of differential data
            ]
            gga_body = ",".join(gga_parts)
            gga_cs = _nmea_checksum(gga_body)
            gga_sentence = f"${gga_body}*{gga_cs}{self._nmea_term}"
            nmea_list.append(gga_sentence)

            # RMC (position, speed, course, date)
            date_str = utc.strftime("%d%m%y")
            # speed in knots, course in degrees
            sog = f"{meas['speed']:.1f}"
            cog = f"{meas['course_deg']:.1f}"
            rmc_parts = [
                "GPRMC",
                timestr,
                "A" if fix != 0 else "V",
                lat_s,
                lat_h,
                lon_s,
                lon_h,
                sog,
                cog,
                date_str,
                "", ""  # magnetic variation placeholder
            ]
            rmc_body = ",".join(rmc_parts)
            rmc_cs = _nmea_checksum(rmc_body)
            rmc_sentence = f"${rmc_body}*{rmc_cs}{self._nmea_term}"
            nmea_list.append(rmc_sentence)

            # VTG (course and speed)
            vtg_parts = [
                "GPVTG",
                f"{meas['course_deg']:.1f}",
                "T",
                "",  # true course repeated placeholder
                "M",
                f"{meas['speed']:.1f}",
                "N",
                f"{(meas['speed'] * 1.852):.1f}",
                "K"
            ]
            vtg_body = ",".join(vtg_parts)
            vtg_cs = _nmea_checksum(vtg_body)
            vtg_sentence = f"${vtg_body}*{vtg_cs}{self._nmea_term}"
            nmea_list.append(vtg_sentence)

            # keep only configured sentences in order if user limited them
            configured = [s.upper() for s in (self._nmea_sentences or [])]
            # sentence id for "$GPxxx" is characters 3..5 inclusive (slice 3:6)
            nmea_list = [s for s in nmea_list if len(s) >= 6 and s[3:6] in configured] if configured else nmea_list

        result = {
            "ts_epoch": ts_epoch,
            "ts_iso": ts_iso,
            "truth": {
                "lat": truth_lat,
                "lon": truth_lon,
                "alt": truth_alt,
                "speed": truth_speed_knots,
                "course_deg": truth_course_deg,
                "climb_m_s": truth_climb,
            },
            "meas": meas,
            "nmea": nmea_list,
        }
        return result

    def simulate(self, duration_s: float, motion_provider: Optional[MotionProvider] = None) -> Dict[str, Any]:
        """
        Run a simulation for duration_s seconds. Returns a dictionary with:
         {
           "t": np.array([...]),
           "truth": {"lat": np.array([...]), "lon":..., "alt":..., "speed":..., "course_deg":...},
           "meas": list of measurement dicts,
           "nmea": list of lists per sample (each list contains nmea sentences)
         }
        """
        if self._dt is None:
            raise RuntimeError("Call read_config() before simulate()")
        if self._rng is None:
            self.init_sim(None)

        t0 = 0.0
        t_end = float(duration_s)
        samples_t: List[float] = []
        truths = {"lat": [], "lon": [], "alt": [], "speed": [], "course_deg": []}
        meas_list: List[Dict[str, Any]] = []
        nmea_all: List[List[str]] = []

        t = t0
        while t <= t_end + 1e-12:
            sample = self.sample(t, motion_provider=motion_provider)
            samples_t.append(t)
            truths["lat"].append(sample["truth"]["lat"])
            truths["lon"].append(sample["truth"]["lon"])
            truths["alt"].append(sample["truth"]["alt"])
            truths["speed"].append(sample["truth"]["speed"])
            truths["course_deg"].append(sample["truth"]["course_deg"])
            meas_list.append(sample["meas"])
            nmea_all.append(sample.get("nmea", []))
            t += float(self._dt)

        # pack into numpy arrays where convenient
        out = {
            "t": np.array(samples_t, dtype=float),
            "truth": {k: np.array(v, dtype=float) for k, v in truths.items()},
            "meas": meas_list,
            "nmea": nmea_all,
        }
        return out
