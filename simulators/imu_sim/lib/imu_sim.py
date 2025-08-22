"""Simplified IMU simulator with basic configuration parsing.

The goal of this module is to provide just enough functionality for the
unit tests used in the kata.  It supports basic accelerometer, gyroscope
and magnetometer simulation including bias, noise and first‑order
low‑pass filtering.  When no external motion provider is supplied, the
simulator follows the waypoint scenario defined in
``simulators/scenarios/main_scenario.json`` and applies a crude wave model
to generate roll/pitch angles based on the sea state.
"""

from __future__ import annotations

import configparser
import math
from pathlib import Path
from typing import Callable, Dict, Iterable, Tuple

import numpy as np

from simulators.scenarios.route import Scenario
from .enums import (
    AccelerometerRange,
    DLPF,
    GyroscopeRange,
    MagnetometerMode,
    MagnetometerRange,
)

MotionProvider = Callable[[float], Tuple[np.ndarray, np.ndarray, np.ndarray]]


# ---------------------------------------------------------------------------
# Utility helpers

def _rotation_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    r, p, y = map(math.radians, (roll_deg, pitch_deg, yaw_deg))
    sr, cr = math.sin(r), math.cos(r)
    sp, cp = math.sin(p), math.cos(p)
    sy, cy = math.sin(y), math.cos(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rx @ Ry @ Rz


def _lpf_alpha(cut_hz: float, fs_hz: float) -> float | None:
    if cut_hz is None or cut_hz <= 0:
        return None
    dt = 1.0 / fs_hz
    rc = 1.0 / (2.0 * math.pi * cut_hz)
    return dt / (rc + dt)


# ---------------------------------------------------------------------------
class MPU9250:
    """Simplified IMU simulator for accelerometer, gyroscope and magnetometer."""

    def __init__(
        self,
        cfg_path: str | None = None,
        scenario_path: str = "simulators/scenarios/main_scenario.json",
    ) -> None:
        self._cfg_path = Path(cfg_path) if cfg_path else None
        self._scenario = Scenario(scenario_path)

        # Defaults
        self._accel_range = AccelerometerRange.ACCEL_RANGE_2G
        self._accel_dlpf: DLPF | None = None
        self._accel_bias = [0.0, 0.0, 0.0]
        self._accel_noise_density = 0.0
        self._accel_smplrt_div: int | None = None
        self._accel_odr_hz = 0.0

        self._gyro_range = GyroscopeRange.GYRO_RANGE_250DPS
        self._gyro_dlpf: DLPF | None = None
        self._gyro_bias = [0.0, 0.0, 0.0]
        self._gyro_noise_density = 0.0
        self._gyro_smplrt_div: int | None = None
        self._gyro_odr_hz = 0.0

        self._mag_range = MagnetometerRange.MAG_RANGE_16BITS
        self._mag_mode = MagnetometerMode.CONT_100HZ
        self._mag_bias = [0.0, 0.0, 0.0]
        self._mag_noise_density = 0.0
        self._mag_world = [20.0, 0.0, 40.0]
        self._mag_odr_hz = 100.0
        self._mag_cps = 1.0 / 0.15  # counts per µT (16-bit mode)

    # ------------------------------------------------------------------
    # Properties and validation helpers

    # Accelerometer ----------------------------------------------------
    @property
    def accel_range(self) -> AccelerometerRange:
        return self._accel_range

    @accel_range.setter
    def accel_range(self, val: int | AccelerometerRange) -> None:
        if isinstance(val, AccelerometerRange):
            self._accel_range = val
        elif isinstance(val, int):
            try:
                self._accel_range = AccelerometerRange(val)
            except ValueError:
                raise ValueError("invalid accelerometer range code") from None
        else:
            raise TypeError("accel_range must be AccelerometerRange or int")

    @property
    def accel_dlpf(self) -> DLPF | None:
        return self._accel_dlpf

    @accel_dlpf.setter
    def accel_dlpf(self, val: int | DLPF) -> None:
        if isinstance(val, DLPF):
            self._accel_dlpf = val
        elif isinstance(val, int):
            try:
                self._accel_dlpf = DLPF(val)
            except ValueError:
                raise ValueError("invalid accel dlpf code") from None
        else:
            raise TypeError("accel_dlpf must be DLPF or int")

    @property
    def accel_bias(self) -> list[float]:
        return self._accel_bias

    @accel_bias.setter
    def accel_bias(self, val: Iterable[float]) -> None:
        if not isinstance(val, (list, tuple)):
            raise TypeError("accel_bias must be list/tuple of three floats")
        if len(val) != 3 or not all(isinstance(v, (int, float)) for v in val):
            raise TypeError("accel_bias must contain three numeric values")
        self._accel_bias = [float(v) for v in val]

    @property
    def accel_noise_density(self) -> float:
        return self._accel_noise_density

    @accel_noise_density.setter
    def accel_noise_density(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("accel_noise_density must be numeric")
        self._accel_noise_density = float(val)

    @property
    def accel_smplrt_div(self) -> int | None:
        return self._accel_smplrt_div

    @accel_smplrt_div.setter
    def accel_smplrt_div(self, val: int) -> None:
        if self._accel_dlpf is None:
            raise ValueError("set accel_dlpf before accel_smplrt_div")
        if not isinstance(val, int) or val < 0:
            raise TypeError("accel sample_rate_div must be non-negative int")
        if self._accel_dlpf == DLPF.BYPASS and val % 4 != 0:
            raise ValueError("sample_rate_div must be multiple of 4 in BYPASS mode")
        self._accel_smplrt_div = val
        base = 1000.0 if self._accel_dlpf == DLPF.ACTIVE else 4000.0
        self._accel_odr_hz = base / (val + 1)

    @property
    def accel_odr_hz(self) -> float:
        return self._accel_odr_hz

    # Gyroscope -------------------------------------------------------
    @property
    def gyro_range(self) -> GyroscopeRange:
        return self._gyro_range

    @gyro_range.setter
    def gyro_range(self, val: int | GyroscopeRange) -> None:
        if isinstance(val, GyroscopeRange):
            self._gyro_range = val
        elif isinstance(val, int):
            try:
                self._gyro_range = GyroscopeRange(val)
            except ValueError:
                raise ValueError("invalid gyroscope range code") from None
        else:
            raise TypeError("gyro_range must be GyroscopeRange or int")

    @property
    def gyro_dlpf(self) -> DLPF | None:
        return self._gyro_dlpf

    @gyro_dlpf.setter
    def gyro_dlpf(self, val: int | DLPF) -> None:
        if isinstance(val, DLPF):
            self._gyro_dlpf = val
        elif isinstance(val, int):
            try:
                self._gyro_dlpf = DLPF(val)
            except ValueError:
                raise ValueError("invalid gyro dlpf code") from None
        else:
            raise TypeError("gyro_dlpf must be DLPF or int")

    @property
    def gyro_bias(self) -> list[float]:
        return self._gyro_bias

    @gyro_bias.setter
    def gyro_bias(self, val: Iterable[float]) -> None:
        if not isinstance(val, (list, tuple)):
            raise TypeError("gyro_bias must be list/tuple of three floats")
        if len(val) != 3 or not all(isinstance(v, (int, float)) for v in val):
            raise TypeError("gyro_bias must contain three numeric values")
        self._gyro_bias = [float(v) for v in val]

    @property
    def gyro_noise_density(self) -> float:
        return self._gyro_noise_density

    @gyro_noise_density.setter
    def gyro_noise_density(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("gyro_noise_density must be numeric")
        self._gyro_noise_density = float(val)

    @property
    def gyro_smplrt_div(self) -> int | None:
        return self._gyro_smplrt_div

    @gyro_smplrt_div.setter
    def gyro_smplrt_div(self, val: int) -> None:
        if self._gyro_dlpf is None:
            raise ValueError("set gyro_dlpf before gyro_smplrt_div")
        if not isinstance(val, int) or val < 0:
            raise TypeError("gyro sample_rate_div must be non-negative int")
        self._gyro_smplrt_div = val
        base = 1000.0 if self._gyro_dlpf == DLPF.ACTIVE else 32000.0
        self._gyro_odr_hz = base / (val + 1)

    @property
    def gyro_odr_hz(self) -> float:
        return self._gyro_odr_hz

    # Magnetometer ----------------------------------------------------
    @property
    def mag_range(self) -> MagnetometerRange:
        return self._mag_range

    @mag_range.setter
    def mag_range(self, val: int | MagnetometerRange) -> None:
        if isinstance(val, MagnetometerRange):
            self._mag_range = val
        elif isinstance(val, int):
            try:
                self._mag_range = MagnetometerRange(val)
            except ValueError:
                raise ValueError("invalid magnetometer range code") from None
        else:
            raise TypeError("mag_range must be MagnetometerRange or int")
        self._mag_cps = 1.0 / (0.6 if self._mag_range == MagnetometerRange.MAG_RANGE_14BITS else 0.15)

    @property
    def mag_mode(self) -> MagnetometerMode:
        return self._mag_mode

    @mag_mode.setter
    def mag_mode(self, val: int | MagnetometerMode) -> None:
        if isinstance(val, MagnetometerMode):
            self._mag_mode = val
        elif isinstance(val, int):
            try:
                self._mag_mode = MagnetometerMode(val)
            except ValueError:
                raise ValueError("invalid magnetometer mode") from None
        else:
            raise TypeError("mag_mode must be MagnetometerMode or int")
        self._mag_odr_hz = {
            MagnetometerMode.POWER_DOWN: 0.0,
            MagnetometerMode.SINGLE: 0.0,
            MagnetometerMode.CONT_8HZ: 8.0,
            MagnetometerMode.CONT_100HZ: 100.0,
        }[self._mag_mode]

    @property
    def mag_bias(self) -> list[float]:
        return self._mag_bias

    @mag_bias.setter
    def mag_bias(self, val: Iterable[float]) -> None:
        if not isinstance(val, (list, tuple)):
            raise TypeError("mag_bias must be list/tuple of three floats")
        if len(val) != 3 or not all(isinstance(v, (int, float)) for v in val):
            raise TypeError("mag_bias must contain three numeric values")
        self._mag_bias = [float(v) for v in val]

    @property
    def mag_noise_density(self) -> float:
        return self._mag_noise_density

    @mag_noise_density.setter
    def mag_noise_density(self, val: float) -> None:
        if not isinstance(val, (int, float)):
            raise TypeError("mag_noise_density must be numeric")
        if val < 0:
            raise TypeError("mag_noise_density must be non-negative")
        self._mag_noise_density = float(val)

    @property
    def mag_world(self) -> list[float]:
        return self._mag_world

    @mag_world.setter
    def mag_world(self, val: Iterable[float]) -> None:
        if not isinstance(val, (list, tuple)):
            raise TypeError("mag_world must be list/tuple of three floats")
        if len(val) != 3 or not all(isinstance(v, (int, float)) for v in val):
            raise TypeError("mag_world must contain three numeric values")
        self._mag_world = [float(v) for v in val]

    @property
    def mag_odr_hz(self) -> float:
        return self._mag_odr_hz

    # ------------------------------------------------------------------
    # Configuration ----------------------------------------------------

    def read_config(self) -> None:
        if self._cfg_path is None:
            return
        cfg = configparser.ConfigParser()
        cfg.read(self._cfg_path)

        a = cfg["accelerometer"]
        self.accel_range = a.getint("range")
        self.accel_dlpf = a.getint("dlpf")
        self.accel_bias = [a.getfloat("bias_x"), a.getfloat("bias_y"), a.getfloat("bias_z")]
        self.accel_noise_density = a.getfloat("noise_density")
        self.accel_smplrt_div = a.getint("sample_rate_div")

        g = cfg["gyroscope"]
        self.gyro_range = g.getint("range")
        self.gyro_dlpf = g.getint("dlpf")
        self.gyro_bias = [g.getfloat("bias_x"), g.getfloat("bias_y"), g.getfloat("bias_z")]
        self.gyro_noise_density = g.getfloat("noise_density")
        self.gyro_smplrt_div = g.getint("sample_rate_div")

        m = cfg["magnetometer"]
        self.mag_range = m.getint("range")
        self.mag_mode = m.getint("mode")
        self.mag_bias = [m.getfloat("bias_x"), m.getfloat("bias_y"), m.getfloat("bias_z")]
        self.mag_noise_density = m.getfloat("noise_density")
        self.mag_world = [m.getfloat("world_x"), m.getfloat("world_y"), m.getfloat("world_z")]

    # ------------------------------------------------------------------
    # Initialisation of sensor simulations ------------------------------

    def init_accel_sim(self, seed: int | None = None, lpf_cut_hz: float | None = None) -> None:
        self._rng_accel = np.random.default_rng(seed)
        self._accel_alpha = _lpf_alpha(lpf_cut_hz or 0.0, self.accel_odr_hz)
        self._accel_prev = np.zeros(3)
        self._accel_initialized = False

    def init_gyro_sim(self, seed: int | None = None, lpf_cut_hz: float | None = None) -> None:
        self._rng_gyro = np.random.default_rng(seed)
        self._gyro_alpha = _lpf_alpha(lpf_cut_hz or 0.0, self.gyro_odr_hz)
        self._gyro_prev = np.zeros(3)
        self._gyro_initialized = False

    def init_mag_sim(self, seed: int | None = None, lpf_cut_hz: float | None = None) -> None:
        self._rng_mag = np.random.default_rng(seed)
        self._mag_alpha = _lpf_alpha(lpf_cut_hz or 0.0, self.mag_odr_hz if self.mag_odr_hz else 1.0)
        self._mag_prev = np.zeros(3)
        self._mag_initialized = False

    def init_all_sims(
        self,
        accel_seed: int | None = None,
        gyro_seed: int | None = None,
        mag_seed: int | None = None,
        accel_lpf_cut_hz: float | None = None,
        gyro_lpf_cut_hz: float | None = None,
    ) -> None:
        if self.mag_mode in (MagnetometerMode.POWER_DOWN, MagnetometerMode.SINGLE):
            raise RuntimeError("Magnetometer not in continuous mode")
        self.init_accel_sim(accel_seed, accel_lpf_cut_hz)
        self.init_gyro_sim(gyro_seed, gyro_lpf_cut_hz)
        self.init_mag_sim(mag_seed, None)

    # ------------------------------------------------------------------
    # Sampling ---------------------------------------------------------

    def _range_g(self) -> float:
        return {
            AccelerometerRange.ACCEL_RANGE_2G: 2.0,
            AccelerometerRange.ACCEL_RANGE_4G: 4.0,
            AccelerometerRange.ACCEL_RANGE_8G: 8.0,
            AccelerometerRange.ACCEL_RANGE_16G: 16.0,
        }[self.accel_range]

    def _range_dps(self) -> float:
        return {
            GyroscopeRange.GYRO_RANGE_250DPS: 250.0,
            GyroscopeRange.GYRO_RANGE_500DPS: 500.0,
            GyroscopeRange.GYRO_RANGE_1000DPS: 1000.0,
            GyroscopeRange.GYRO_RANGE_2000DPS: 2000.0,
        }[self.gyro_range]

    def sample_accel(self, a_lin_world_ms2: np.ndarray, R: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if not hasattr(self, "_rng_accel"):
            raise RuntimeError("Accel sim not initialized")
        g_world = np.array([0.0, 0.0, 9.80665])
        a_world = a_lin_world_ms2 + g_world
        a_sensor = R @ a_world
        a_g = a_sensor / 9.80665
        a_g = a_g + self.accel_bias + self._rng_accel.normal(0.0, self.accel_noise_density, 3)
        if self._accel_alpha is not None:
            if self._accel_initialized:
                self._accel_prev += self._accel_alpha * (a_g - self._accel_prev)
            else:
                self._accel_prev = a_g
                self._accel_initialized = True
            a_g = self._accel_prev
        range_g = self._range_g()
        a_g = np.clip(a_g, -range_g, range_g)
        scale = 32768.0 / range_g
        counts = np.clip(np.rint(a_g * scale), -32768, 32767).astype(np.int16)
        return counts, a_g

    def sample_gyro(self, omega_world_dps: np.ndarray, R: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if not hasattr(self, "_rng_gyro"):
            raise RuntimeError("Gyro sim not initialized")
        w_sensor = R @ omega_world_dps
        w_dps = w_sensor + self.gyro_bias + self._rng_gyro.normal(0.0, self.gyro_noise_density, 3)
        if self._gyro_alpha is not None:
            if self._gyro_initialized:
                self._gyro_prev += self._gyro_alpha * (w_dps - self._gyro_prev)
            else:
                self._gyro_prev = w_dps
                self._gyro_initialized = True
            w_dps = self._gyro_prev
        range_dps = self._range_dps()
        w_dps = np.clip(w_dps, -range_dps, range_dps)
        scale = 32768.0 / range_dps
        counts = np.clip(np.rint(w_dps * scale), -32768, 32767).astype(np.int16)
        return counts, w_dps

    def sample_mag(self, R: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if not hasattr(self, "_rng_mag"):
            raise RuntimeError("Mag sim not initialized")
        B_sensor = R @ np.array(self.mag_world)
        B_uT = B_sensor + self.mag_bias + self._rng_mag.normal(0.0, self.mag_noise_density, 3)
        if self._mag_alpha is not None:
            if self._mag_initialized:
                self._mag_prev += self._mag_alpha * (B_uT - self._mag_prev)
            else:
                self._mag_prev = B_uT
                self._mag_initialized = True
            B_uT = self._mag_prev
        counts = np.clip(np.rint(B_uT * self._mag_cps), -32768, 32767).astype(np.int16)
        return counts, B_uT

    # ------------------------------------------------------------------
    def _wave_angles(self, t: float) -> Tuple[float, float]:
        amp_map = {
            "calm": (0.0, 1.0),
            "choppy": (5.0, 15.0),
            "moderate": (5.0, 20.0),
            "rough": (15.0, 40.0),
            "storm": (40.0, 50.0),
        }
        lo, hi = amp_map.get(self._scenario.wave_state, (0.0, 1.0))
        amp = lo if lo == hi else np.random.uniform(lo, hi)
        roll = amp * math.sin(0.5 * t)
        pitch = amp * math.sin(0.5 * t + math.pi / 2)
        return roll, pitch

    def _scenario_motion(self, t: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        lat, lon, speed, heading = self._scenario.state_at(t)
        roll, pitch = self._wave_angles(t)
        yaw = heading
        R = _rotation_matrix(roll, pitch, yaw)
        a_lin = np.zeros(3)
        omega = np.zeros(3)
        return a_lin, omega, R

    # ------------------------------------------------------------------
    def simulate(self, duration: float, motion_provider: MotionProvider | None = None) -> Dict:
        if not hasattr(self, "_rng_accel") or not hasattr(self, "_rng_gyro") or not hasattr(self, "_rng_mag"):
            raise RuntimeError("Simulators not initialised")

        n_acc = math.floor(self.accel_odr_hz * duration) + 1
        n_gyro = math.floor(self.gyro_odr_hz * duration) + 1
        n_mag = math.floor(self.mag_odr_hz * duration) + 1

        t_acc = np.linspace(0.0, (n_acc - 1) / self.accel_odr_hz, n_acc)
        t_gyro = np.linspace(0.0, (n_gyro - 1) / self.gyro_odr_hz, n_gyro)
        t_mag = np.linspace(0.0, (n_mag - 1) / self.mag_odr_hz, n_mag)

        accel_meas = np.empty((n_acc, 3))
        gyro_meas = np.empty((n_gyro, 3))
        mag_meas = np.empty((n_mag, 3))

        for i, ti in enumerate(t_acc):
            a_lin, omega, R = (motion_provider(ti) if motion_provider else self._scenario_motion(ti))
            _, a_g = self.sample_accel(a_lin, R)
            accel_meas[i] = a_g
        for i, ti in enumerate(t_gyro):
            a_lin, omega, R = (motion_provider(ti) if motion_provider else self._scenario_motion(ti))
            _, w_dps = self.sample_gyro(omega, R)
            gyro_meas[i] = w_dps
        for i, ti in enumerate(t_mag):
            a_lin, omega, R = (motion_provider(ti) if motion_provider else self._scenario_motion(ti))
            _, B_uT = self.sample_mag(R)
            mag_meas[i] = B_uT

        return {
            "accel": {"t": t_acc, "meas": accel_meas},
            "gyro": {"t": t_gyro, "meas": gyro_meas},
            "mag": {"t": t_mag, "meas": mag_meas},
        }

