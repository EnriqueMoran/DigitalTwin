import numpy as np

from typing import Callable, Dict, Any, List, Tuple

from simulators.imu_sim.lib.configparsers import IMUParser
from simulators.imu_sim.lib.accelerometer_sim import AccelSim
from simulators.imu_sim.lib.gyroscope_sim import GyroSim
from simulators.imu_sim.lib.magnetometer_sim import MagSim
from simulators.imu_sim.lib.enums import (AccelerometerRange, GyroscopeRange, MagnetometerRange, 
                                          MagnetometerMode, DLPF)


MotionProvider = Callable[[float], Tuple[np.ndarray, np.ndarray, np.ndarray]]
# returns: (a_lin_world_ms2[3], omega_world_dps[3], R_world_to_sensor 3x3)


class MPU9250:

    def __init__(self, config_file="config.ini"):
        self.config_file  = config_file
        self._accel_range = None
        self._accel_dlpf  = None
        self._accel_bias  = None
        self._accel_odr   = None
        self._accel_noise_density = None
        self._accel_smplrt_div    = None

        self._gyro_range = None
        self._gyro_dlpf  = None
        self._gyro_bias  = None
        self._gyro_odr   = None
        self._gyro_noise_density = None
        self._gyro_smplrt_div    = None

        self._mag_range = None
        self._mag_mode  = None
        self._mag_bias  = None 
        self._mag_odr   = None
        self._mag_noise_density = None
        self._mag_world = None 


    @property
    def accel_range(self) -> AccelerometerRange:
        return self._accel_range

    @accel_range.setter
    def accel_range(self, val: int | AccelerometerRange) -> None:
        if isinstance(val, int):
            try:
                self._accel_range = AccelerometerRange(val)
            except ValueError:
                raise ValueError(f"Invalid accelerometer range {val}. "
                                 f"Valid values are {[e.value for e in AccelerometerRange]}.")
        elif isinstance(val, AccelerometerRange):
            self._accel_range = val
        else:
            raise TypeError(f"Invalid type {type(val)}. "
                            f"Valid types are int, AccelerometerRange")

    @property
    def accel_dlpf(self) -> DLPF:
        return self._accel_dlpf

    @accel_dlpf.setter
    def accel_dlpf(self, val: int | DLPF) -> None:
        if isinstance(val, int):
            try:
                self._accel_dlpf = DLPF(val)
            except ValueError:
                raise ValueError(f"Invalid accelerometer DLPF value {val}. "
                                 f"Valid values are {[e.value for e in DLPF]}.")
        elif isinstance(val, DLPF):
            self._accel_dlpf = val
        else:
            raise TypeError(f"Invalid type {type(val)}. "
                            f"Valid types are int, DLPF")

    @property
    def accel_bias(self) -> list[float]:
        return self._accel_bias

    @accel_bias.setter
    def accel_bias(self, val: list[float]) -> None:
        if (isinstance(val, list) and len(val) == 3
                and all(isinstance(x, (int, float)) for x in val)):
            self._accel_bias = [float(x) for x in val]
        else:
            raise TypeError("accel_bias must be a list of 3 numbers [bx, by, bz]")

    @property
    def accel_noise_density(self) -> float:
        return self._accel_noise_density

    @accel_noise_density.setter
    def accel_noise_density(self, val: float) -> None:
        if isinstance(val, (int, float)):
            self._accel_noise_density = float(val)
        else:
            raise TypeError("accel_noise_density must be a number")

    @property
    def accel_smplrt_div(self) -> int:
        return self._accel_smplrt_div

    @accel_smplrt_div.setter
    def accel_smplrt_div(self, val: int) -> None:
        if not isinstance(val, int) or val < 0:
            raise TypeError("accel_smplrt_div must be a non-negative integer")

        if self._accel_dlpf is None:
            raise ValueError("Set accel_dlpf before accel_smplrt_div")

        if self._accel_dlpf == DLPF.BYPASS and (val % 4) != 0:
            raise ValueError("When DLPF is BYPASS, accel_smplrt_div must be a multiple of 4")

        base = 1000 if self._accel_dlpf == DLPF.ACTIVE else 4000
        self._accel_smplrt_div = val
        self._accel_odr = base / (1 + val)
    
    @property
    def accel_odr_hz(self) -> float | None:
        return getattr(self, "_accel_odr", None)
    
    @property
    def gyro_range(self) -> GyroscopeRange:
        return self._gyro_range

    @gyro_range.setter
    def gyro_range(self, val: int | GyroscopeRange) -> None:
        if isinstance(val, int):
            try:
                self._gyro_range = GyroscopeRange(val)
            except ValueError:
                raise ValueError(f"Invalid gyroscope range {val}. "
                                 f"Valid values are {[e.value for e in GyroscopeRange]}.")
        elif isinstance(val, GyroscopeRange):
            self._gyro_range = val
        else:
            raise TypeError(f"Invalid type {type(val)}. "
                            f"Valid types are int, GyroscopeRange")
    
    @property
    def gyro_dlpf(self) -> DLPF:
        return self._gyro_dlpf

    @gyro_dlpf.setter
    def gyro_dlpf(self, val: int | DLPF) -> None:
        if isinstance(val, int):
            try:
                self._gyro_dlpf = DLPF(val)
            except ValueError:
                raise ValueError(f"Invalid gyroscope DLPF value {val}. "
                                 f"Valid values are {[e.value for e in DLPF]}.")
        elif isinstance(val, DLPF):
            self._gyro_dlpf = val
        else:
            raise TypeError(f"Invalid type {type(val)}. "
                            f"Valid types are int, DLPF")
    
    @property
    def gyro_bias(self) -> list[float]:
        return self._gyro_bias

    @gyro_bias.setter
    def gyro_bias(self, val: list[float]) -> None:
        if (isinstance(val, list) and len(val) == 3
                and all(isinstance(x, (int, float)) for x in val)):
            self._gyro_bias = [float(x) for x in val]
        else:
            raise TypeError("gyro_bias must be a list of 3 numbers [bx, by, bz]")
    
    @property
    def gyro_noise_density(self) -> float:
        return self._gyro_noise_density

    @gyro_noise_density.setter
    def gyro_noise_density(self, val: float) -> None:
        if isinstance(val, (int, float)):
            self._gyro_noise_density = float(val)
        else:
            raise TypeError("gyro_noise_density must be a number")
    
    @property
    def gyro_smplrt_div(self) -> int:
        return self._gyro_smplrt_div

    @gyro_smplrt_div.setter
    def gyro_smplrt_div(self, val: int) -> None:
        if not isinstance(val, int) or val < 0:
            raise TypeError("gyro_smplrt_div must be a non-negative integer")

        if self._gyro_dlpf is None:
            raise ValueError("Set gyro_dlpf before gyro_smplrt_div")

        base = 1000 if self._gyro_dlpf == DLPF.ACTIVE else 32000
        self._gyro_smplrt_div = val
        self._gyro_odr = base / (1 + val)

    @property
    def gyro_odr_hz(self) -> float | None:
        return getattr(self, "_gyro_odr", None)

    @property
    def mag_range(self) -> MagnetometerRange:
        return self._mag_range

    @mag_range.setter
    def mag_range(self, val: int | MagnetometerRange) -> None:
        if isinstance(val, int):
            try:
                self._mag_range = MagnetometerRange(val)
            except ValueError:
                raise ValueError(f"Invalid magnetometer range {val}. "
                                 f"Valid values are {[e.value for e in MagnetometerRange]}.")
        elif isinstance(val, MagnetometerRange):
            self._mag_range = val
        else:
            raise TypeError(f"Invalid type {type(val)}. "
                            f"Valid types are int, MagnetometerRange")
    
    @property
    def mag_mode(self) -> MagnetometerMode:
        return self._mag_mode

    @mag_mode.setter
    def mag_mode(self, val: int | MagnetometerMode) -> None:
        if isinstance(val, int):
            try:
                self._mag_mode = MagnetometerMode(val)
            except ValueError:
                raise ValueError(f"Invalid magnetometer mode {val}. "
                                f"Valid values are {[e.value for e in MagnetometerMode]}.")
        elif isinstance(val, MagnetometerMode):
            self._mag_mode = val
        else:
            raise TypeError("mag_mode must be int or MagnetometerMode")

        self._mag_odr = self.mag_mode.to_hz()
    
    @property
    def mag_bias(self) -> list[float]:
        return self._mag_bias

    @mag_bias.setter
    def mag_bias(self, val: list[float]) -> None:
        if isinstance(val, list) and len(val) == 3 and all(isinstance(x, (int, float)) for x in val):
            self._mag_bias = [float(x) for x in val]
        else:
            raise TypeError("mag_bias must be a list of 3 numbers [bx, by, bz]")
    
    @property
    def mag_noise_density(self) -> float:
        return self._mag_noise_density

    @mag_noise_density.setter
    def mag_noise_density(self, val: float) -> None:
        if isinstance(val, (int, float)) and val >= 0:
            self._mag_noise_density = float(val)
        else:
            raise TypeError("mag_noise_density must be a non-negative number")
    
    @property
    def mag_world(self) -> list[float]:
        return self._mag_world

    @mag_world.setter
    def mag_world(self, val: list[float]) -> None:
        if isinstance(val, list) and len(val) == 3 and all(isinstance(x, (int, float)) for x in val):
            self._mag_world = [float(x) for x in val]
        else:
            raise TypeError("mag_world must be a list of 3 numbers [Bx, By, Bz]")

    @property
    def mag_odr_hz(self) -> float | None:
        return self._mag_odr
            

    def read_config(self):
        parser = IMUParser(self.config_file)
        self.accel_range = parser.parse_accel_range()
        self.accel_dlpf  = parser.parse_accel_dlpf()
        self.accel_bias  = parser.parse_accel_bias()
        self.accel_noise_density = parser.parse_accel_noise_density()
        self.accel_smplrt_div = parser.parse_accel_smplrt_div()

        self.gyro_range = parser.parse_gyro_range()
        self.gyro_dlpf  = parser.parse_gyro_dlpf()
        self.gyro_bias  = parser.parse_gyro_bias()
        self.gyro_noise_density = parser.parse_gyro_noise_density()
        self.gyro_smplrt_div = parser.parse_gyro_smplrt_div()

        self.mag_range = parser.parse_mag_range()
        self.mag_mode  = parser.parse_mag_mode()
        self.mag_bias  = parser.parse_mag_bias()
        self.mag_noise_density = parser.parse_mag_noise_density()
        self.mag_world = parser.parse_mag_world()
    

    def init_accel_sim(self, seed: int | None = None, lpf_cut_hz: float = 100.0):
        range_g = self.accel_range.to_g()
        odr = float(self._accel_odr)

        self._accel_sim = AccelSim.from_config(
            range_g=range_g,
            odr_hz=odr,
            bias_g=self._accel_bias,
            noise_density_g_sqrtHz=float(self._accel_noise_density),
            use_lpf=(self._accel_dlpf == DLPF.ACTIVE),
            lpf_cut_hz=float(lpf_cut_hz),
            seed=seed,
        )


    def sample_accel(self, a_lin_world_ms2: np.ndarray, R_world_to_sensor: np.ndarray):
        """
        Returns (counts_int16[3], a_g_float[3]) for X,Y,Z axes.
        - a_lin_world_ms2: linear acceleration (WITHOUT gravity) in m/s² in world frame.
        - R_world_to_sensor: 3x3 rotation matrix that transforms world -> sensor coordinates.
        """
        if not hasattr(self, "_accel_sim"):
            raise RuntimeError("Call init_accel_sim() before sample_accel()")
        return self._accel_sim.step(a_lin_world_ms2, R_world_to_sensor)


    def init_gyro_sim(self, seed: int | None = None, lpf_cut_hz: float = 98.0):
        if self._gyro_odr is None:
            raise RuntimeError("Gyro ODR not set. Configure gyro_dlpf and gyro_smplrt_div first.")

        range_dps = self.gyro_range.to_dps()
        odr = float(self._gyro_odr)

        self._gyro_sim = GyroSim.from_config(
            range_dps=range_dps,
            odr_hz=odr,
            bias_dps=self._gyro_bias,
            noise_density_dps_sqrtHz=float(self._gyro_noise_density),
            use_lpf=(self._gyro_dlpf == DLPF.ACTIVE),
            lpf_cut_hz=float(lpf_cut_hz),
            seed=seed,
        )


    def sample_gyro(self, omega_world_dps: np.ndarray, R_world_to_sensor: np.ndarray):
        """
        Return one gyroscope sample as (counts_int16[3], omega_dps_float[3]).
        Args:
        - omega_world_dps: angular velocity in world frame (°/s), shape (3,)
        - R_world_to_sensor: rotation matrix world -> sensor, shape (3,3)
        """
        if not hasattr(self, "_gyro_sim"):
            raise RuntimeError("Call init_gyro_sim() before sample_gyro()")
        return self._gyro_sim.step(omega_world_dps, R_world_to_sensor)


    def init_mag_sim(self, seed: int | None = None, lpf_cut_hz: float = 10.0):
        """
        Initialize magnetometer simulator (MagSim) from current configuration.

        Preconditions:
            - mag_mode must be continuous (CONT_8HZ or CONT_100HZ). POWER_DOWN and SINGLE are not 
              supported by this streaming simulator.
            - read_config() must have been called so that mag_* fields are populated.

        Args:
            seed: RNG seed for reproducible noise.
            lpf_cut_hz: first-order LPF cutoff in Hz. Use 0.0 to disable.

        Raises:
            RuntimeError: if mode is not continuous or ODR is not available.
        """
        if self._mag_mode not in (MagnetometerMode.CONT_8HZ, MagnetometerMode.CONT_100HZ):
            raise RuntimeError(
                "Magnetometer mode must be continuous (CONT_8HZ or CONT_100HZ) to run the simulator."
            )
        if self._mag_odr is None or float(self._mag_odr) <= 0.0:
            raise RuntimeError("Magnetometer ODR not set. Configure mag_mode first.")

        range_bits = self._mag_range.to_bits()
        odr = float(self._mag_odr)

        self._mag_sim = MagSim.from_config(
            range_bits=range_bits,
            odr_hz=odr,
            bias_uT=self._mag_bias,
            noise_density_uT_sqrtHz=float(self._mag_noise_density),
            world_field_uT=self._mag_world,
            use_lpf=(float(lpf_cut_hz) > 0.0),
            lpf_cut_hz=float(lpf_cut_hz),
            seed=seed,
        )


    def sample_mag(self, R_world_to_sensor: np.ndarray):
        """
        Return one magnetometer sample as (counts_int16[3], B_uT_float[3]).

        Args:
            R_world_to_sensor: rotation matrix world -> sensor, shape (3,3).

        Returns:
            counts_int16[3]: quantized magnetometer counts (int16).
            B_uT_float[3]: simulated magnetic field in µT, after rotation, bias, LPF and noise.

        Raises:
            RuntimeError: if init_mag_sim() has not been called.
        """
        if not hasattr(self, "_mag_sim"):
            raise RuntimeError("Call init_mag_sim() before sample_mag()")
        return self._mag_sim.step(R_world_to_sensor)


    def init_all_sims(self, accel_seed: int | None = None, gyro_seed:  int | None = None, 
                      mag_seed: int | None = None, accel_lpf_cut_hz: float = 100.0, 
                      gyro_lpf_cut_hz:  float = 98.0) -> None:
        """
        Initialize all enabled sensor simulators from current configuration.
        Must call read_config() before this.
        """
        self.init_accel_sim(seed=accel_seed, lpf_cut_hz=accel_lpf_cut_hz)
        self.init_gyro_sim(seed=gyro_seed, lpf_cut_hz=gyro_lpf_cut_hz)
        # Mag ODR is driven by self.mag_mode; no LPF here for simplicity.
        self.init_mag_sim(seed=mag_seed)

        # Internal time and next-sample scheduling
        self._t = 0.0
        self._dt_acc  = 1.0 / float(self.accel_odr_hz)
        self._dt_gyro = 1.0 / float(self.gyro_odr_hz)
        # If mag in power-down/single, protect against div-by-zero; treat as no stream.
        self._dt_mag = (1.0 / float(self.mag_odr_hz)) if (self.mag_odr_hz and self.mag_odr_hz > 0.0) else None

        self._t_next_acc  = 0.0
        self._t_next_gyro = 0.0
        self._t_next_mag  = 0.0 if self._dt_mag is not None else None
    

    def simulate(self, duration_s: float, motion_provider: MotionProvider) -> Dict[str, Dict[str, Any]]:
        """
        Run a multi-sensor simulation for 'duration_s', driven by 'motion_provider'.

        Returns a dict with per-sensor arrays:
        {
            "accel": {"t": [...], "counts": Nx3 int16, "meas": Nx3 float},
            "gyro":  {"t": [...], "counts": Nx3 int16, "meas": Nx3 float},
            "mag":   {"t": [...], "counts": Nx3 int16, "meas": Nx3 float},
        }
        """
        t_end = self._t + float(duration_s)

        acc_t:  List[float] = []; acc_c: List[np.ndarray] = []; acc_f: List[np.ndarray] = []
        gyr_t:  List[float] = []; gyr_c: List[np.ndarray] = []; gyr_f: List[np.ndarray] = []
        mag_t:  List[float] = []; mag_c: List[np.ndarray] = []; mag_f: List[np.ndarray] = []

        # Event-driven loop: always jump to the next sensor timestamp
        while True:
            candidates = [self._t_next_acc, self._t_next_gyro]
            if self._t_next_mag is not None:
                candidates.append(self._t_next_mag)
            t_next = min(candidates)

            if t_next > t_end:
                break

            self._t = t_next

            # Query motion at current time
            a_lin_world_ms2, omega_world_dps, R_world_to_sensor = motion_provider(self._t)

            # Sample sensors whose time has arrived (allow tiny epsilon)
            EPS = 1e-12

            if abs(self._t - self._t_next_acc) <= EPS:
                cnt, meas = self.sample_accel(a_lin_world_ms2, R_world_to_sensor)
                acc_t.append(self._t); acc_c.append(cnt); acc_f.append(meas)
                self._t_next_acc += self._dt_acc

            if abs(self._t - self._t_next_gyro) <= EPS:
                cnt, meas = self.sample_gyro(omega_world_dps, R_world_to_sensor)
                gyr_t.append(self._t); gyr_c.append(cnt); gyr_f.append(meas)
                self._t_next_gyro += self._dt_gyro

            if (self._t_next_mag is not None) and (abs(self._t - self._t_next_mag) <= EPS):
                cnt, meas = self.sample_mag(R_world_to_sensor)
                mag_t.append(self._t); mag_c.append(cnt); mag_f.append(meas)
                self._t_next_mag += self._dt_mag

        # Pack outputs as numpy arrays
        def _pack(ts, cs, fs):
            if len(ts) == 0:
                return {"t": np.zeros(0), "counts": np.zeros((0,3), dtype=np.int16), 
                        "meas": np.zeros((0,3), float)}
            return {"t": np.array(ts, float),
                    "counts": np.vstack(cs).astype(np.int16),
                    "meas": np.vstack(fs).astype(float)}

        return {
            "accel": _pack(acc_t, acc_c, acc_f),
            "gyro":  _pack(gyr_t, gyr_c, gyr_f),
            "mag":   _pack(mag_t, mag_c, mag_f),
        }