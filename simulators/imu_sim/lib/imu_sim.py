import configparser
import math
from pathlib import Path
from typing import Callable, Dict, Tuple

import numpy as np

from simulators.scenarios.route import Scenario
from .enums import DLPF, MagnetometerMode

MotionProvider = Callable[[float], Tuple[np.ndarray, np.ndarray, np.ndarray]]


# ---------------------------------------------------------------------------
# Utility

def _rotation_matrix(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    r = math.radians(roll_deg)
    p = math.radians(pitch_deg)
    y = math.radians(yaw_deg)
    sr, cr = math.sin(r), math.cos(r)
    sp, cp = math.sin(p), math.cos(p)
    sy, cy = math.sin(y), math.cos(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rx @ Ry @ Rz


class MPU9250:
    """Simplified IMU simulator for accelerometer, gyroscope and magnetometer."""

    def __init__(self, cfg_path: str,
                 scenario_path: str = "simulators/scenarios/main_scenario.json"):
        self._cfg_path = Path(cfg_path)
        self._scenario = Scenario(scenario_path)

    # ------------------------------------------------------------------
    def read_config(self) -> None:
        cfg = configparser.ConfigParser()
        cfg.read(self._cfg_path)

        a = cfg["accelerometer"]
        self.accel_dlpf = DLPF(a.getint("dlpf", 1))
        self.accel_bias = np.array([a.getfloat("bias_x", 0.0),
                                    a.getfloat("bias_y", 0.0),
                                    a.getfloat("bias_z", 0.0)])
        self.accel_noise = a.getfloat("noise_density", 0.0003)
        self.accel_smplrt_div = a.getint("sample_rate_div", 0)
        base = 1000.0
        self.accel_odr_hz = base / (self.accel_smplrt_div + 1)

        g = cfg["gyroscope"]
        self.gyro_dlpf = DLPF(g.getint("dlpf", 1))
        self.gyro_bias = np.array([g.getfloat("bias_x", 0.0),
                                   g.getfloat("bias_y", 0.0),
                                   g.getfloat("bias_z", 0.0)])
        self.gyro_noise = g.getfloat("noise_density", 0.01)
        self.gyro_smplrt_div = g.getint("sample_rate_div", 0)
        self.gyro_odr_hz = base / (self.gyro_smplrt_div + 1)

        m = cfg["magnetometer"]
        self.mag_range = m.getint("range", 2)
        self.mag_mode = MagnetometerMode(m.getint("mode", 1))
        self.mag_bias = np.array([m.getfloat("bias_x", 0.0),
                                  m.getfloat("bias_y", 0.0),
                                  m.getfloat("bias_z", 0.0)])
        self.mag_noise = m.getfloat("noise_density", 0.4)
        self.mag_world = np.array([m.getfloat("world_x", 20.0),
                                   m.getfloat("world_y", 0.0),
                                   m.getfloat("world_z", 40.0)])
        self.mag_odr_hz = 100.0 if self.mag_mode == MagnetometerMode.CONT_100HZ else (
            8.0 if self.mag_mode == MagnetometerMode.CONT_8HZ else 0.0)

    # ------------------------------------------------------------------
    def init_all_sims(self, accel_seed: int | None = None, gyro_seed: int | None = None,
                      mag_seed: int | None = None, accel_lpf_cut_hz: float | None = None,
                      gyro_lpf_cut_hz: float | None = None) -> None:
        if self.mag_mode == MagnetometerMode.POWER_DOWN:
            raise RuntimeError("Magnetometer not in continuous mode")
        self._rng_accel = np.random.default_rng(accel_seed)
        self._rng_gyro = np.random.default_rng(gyro_seed)
        self._rng_mag = np.random.default_rng(mag_seed)

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
        amp = self._rng_accel.uniform(lo, hi)
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
            a_lin, omega, R = motion_provider(ti) if motion_provider else self._scenario_motion(ti)
            accel_meas[i] = self._sample_accel(a_lin, R)
        for i, ti in enumerate(t_gyro):
            a_lin, omega, R = motion_provider(ti) if motion_provider else self._scenario_motion(ti)
            gyro_meas[i] = self._sample_gyro(omega, R)
        for i, ti in enumerate(t_mag):
            a_lin, omega, R = motion_provider(ti) if motion_provider else self._scenario_motion(ti)
            mag_meas[i] = self._sample_mag(R)

        return {
            "accel": {"t": t_acc, "meas": accel_meas},
            "gyro": {"t": t_gyro, "meas": gyro_meas},
            "mag": {"t": t_mag, "meas": mag_meas},
        }

    # ------------------------------------------------------------------
    def _sample_accel(self, a_lin_world_ms2: np.ndarray, R: np.ndarray) -> np.ndarray:
        g_world = np.array([0.0, 0.0, 9.80665])
        a_world = a_lin_world_ms2 + g_world
        a_sensor = R @ a_world
        a_g = a_sensor / 9.80665
        noise = self._rng_accel.normal(0.0, self.accel_noise, 3)
        return a_g + self.accel_bias + noise

    def _sample_gyro(self, omega_world_dps: np.ndarray, R: np.ndarray) -> np.ndarray:
        omega_sensor = R @ omega_world_dps
        noise = self._rng_gyro.normal(0.0, self.gyro_noise, 3)
        return omega_sensor + self.gyro_bias + noise

    def _sample_mag(self, R: np.ndarray) -> np.ndarray:
        B_sensor = R @ self.mag_world
        noise = self._rng_mag.normal(0.0, self.mag_noise, 3)
        return B_sensor + self.mag_bias + noise
