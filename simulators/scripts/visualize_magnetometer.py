# Visualize magnetometer simulator outputs (B_uT and counts) over time.

import math
import numpy as np
import matplotlib.pyplot as plt

from simulators.imu_sim.lib.imu_sim import MPU9250


def Rx(deg: float) -> np.ndarray:
    """Rotation around X axis (roll), degrees."""
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[1, 0, 0],
                     [0, c,-s],
                     [0, s, c]])

def Ry(deg: float) -> np.ndarray:
    """Rotation around Y axis (pitch), degrees."""
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[ c, 0, s],
                     [ 0, 1, 0],
                     [-s, 0, c]])

def Rz(deg: float) -> np.ndarray:
    """Rotation around Z axis (yaw), degrees."""
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[c,-s, 0],
                     [s, c, 0],
                     [0, 0, 1]])

def euler_R_world_to_sensor(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """Build world->sensor rotation: R = Rx(roll) @ Ry(pitch) @ Rz(yaw)."""
    return Rx(roll_deg) @ Ry(pitch_deg) @ Rz(yaw_deg)


# --------- simple angle profiles to make the mag change over time ---------

def step_yaw_profile(t: float, yaw_deg_pos: float = 60.0,
                     T_pos: float = 0.5, T_zero: float = 0.5, T_neg: float = 0.5) -> float:
    """
    Piecewise yaw profile (deg): +yaw_deg_pos for T_pos -> 0 for T_zero -> -yaw_deg_pos for T_neg, repeating.
    Returns yaw angle in degrees.
    """
    T = T_pos + T_zero + T_neg
    tau = t % T
    if tau < T_pos:
        return +yaw_deg_pos
    elif tau < T_pos + T_zero:
        return 0.0
    else:
        return -yaw_deg_pos

def sine_yaw_profile(t: float, amp_deg: float = 60.0, freq_hz: float = 0.5) -> float:
    """Sinusoidal yaw angle (deg): yaw(t) = amp_deg * sin(2π f t)."""
    return amp_deg * math.sin(2.0 * math.pi * freq_hz * t)


def _guess_mag_bits(imu: MPU9250) -> int:
    """Utility to print human-friendly mag resolution from enum setting."""
    from simulators.imu_sim.lib.enums import MagnetometerRange
    m = {MagnetometerRange.MAG_RANGE_14BITS: 14,
         MagnetometerRange.MAG_RANGE_16BITS: 16}
    return m.get(imu.mag_range, -1)


def run_and_plot_mag(config_path: str,
                     scenario: str = "sine_yaw",  # "sine_yaw" or "step_yaw"
                     yaw_amp_deg: float = 60.0,
                     yaw_freq_hz: float = 0.5,
                     fixed_roll_deg: float = 0.0,
                     fixed_pitch_deg: float = 0.0,
                     duration_s: float = 5.0,
                     seed: int | None = 1,
                     lpf_cut_hz: float = 10.0):
    """
    Initializes MPU9250 + MagSim from INI config, generates a time series with a varying yaw
    (roll/pitch fixed), and plots B_uT (µT) and counts (int16) over time.
    """
    # 1) Init device + mag sim
    imu = MPU9250(config_path)
    imu.read_config()
    imu.init_mag_sim(seed=seed, lpf_cut_hz=lpf_cut_hz)

    # ODR comes from mode: 8 Hz or 100 Hz
    fs = float(imu.mag_odr_hz)
    if fs <= 0.0:
        raise RuntimeError("Magnetometer ODR is zero (mode must be CONT_8HZ or CONT_100HZ).")
    Ts = 1.0 / fs
    N = int(duration_s * fs)

    t_arr = np.arange(N) * Ts
    B_uT_arr = np.zeros((N, 3), dtype=float)
    cnt_arr  = np.zeros((N, 3), dtype=np.int16)

    # 2) Generate samples
    for i, t in enumerate(t_arr):
        if scenario == "sine_yaw":
            yaw_deg = sine_yaw_profile(t, amp_deg=yaw_amp_deg, freq_hz=yaw_freq_hz)
        elif scenario == "step_yaw":
            yaw_deg = step_yaw_profile(t, yaw_deg_pos=yaw_amp_deg)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        R_ws = euler_R_world_to_sensor(fixed_roll_deg, fixed_pitch_deg, yaw_deg)
        counts, B_uT = imu.sample_mag(R_ws)  # (counts_int16[3], B_uT_float[3])
        B_uT_arr[i, :] = B_uT
        cnt_arr[i, :]  = counts

    # 3) Plot B [µT]
    plt.figure(figsize=(10, 5))
    plt.plot(t_arr, B_uT_arr[:, 0], label="Bx [µT]")
    plt.plot(t_arr, B_uT_arr[:, 1], label="By [µT]")
    plt.plot(t_arr, B_uT_arr[:, 2], label="Bz [µT]")
    plt.title(
        f"Magnetometer (µT) — scenario={scenario}, ODR={fs:.1f} Hz, "
        f"roll={fixed_roll_deg:.1f}°, pitch={fixed_pitch_deg:.1f}°"
    )
    plt.xlabel("Time [s]")
    plt.ylabel("Magnetic field [µT]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # 4) Plot counts
    plt.figure(figsize=(10, 5))
    plt.plot(t_arr, cnt_arr[:, 0], label="counts_x")
    plt.plot(t_arr, cnt_arr[:, 1], label="counts_y")
    plt.plot(t_arr, cnt_arr[:, 2], label="counts_z")
    plt.title(
        f"Magnetometer (counts) — scenario={scenario}, res={_guess_mag_bits(imu)} bits"
    )
    plt.xlabel("Time [s]")
    plt.ylabel("Counts [int16]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    CONFIG_PATH = "./simulators/imu_sim/config.ini"
    SCENARIO    = "sine_yaw"   # "sine_yaw" or "step_yaw"
    YAW_AMP_DEG = 60.0         # amplitude of yaw motion
    YAW_FREQ_HZ = 0.5          # used for sine_yaw
    DURATION_S  = 6.0
    SEED        = 1
    LPF_CUT_HZ  = 10.0         # 0.0 disables LPF inside MagSim
    ROLL_DEG    = 0.0          # keep roll fixed
    PITCH_DEG   = 0.0          # keep pitch fixed

    run_and_plot_mag(
        CONFIG_PATH,
        SCENARIO,
        YAW_AMP_DEG,
        YAW_FREQ_HZ,
        fixed_roll_deg=ROLL_DEG,
        fixed_pitch_deg=PITCH_DEG,
        duration_s=DURATION_S,
        seed=SEED,
        lpf_cut_hz=LPF_CUT_HZ,
    )
