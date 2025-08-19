# Visualize accelerometer simulator outputs (a_g and counts) over time.

import math
import numpy as np
import matplotlib.pyplot as plt

from simulators.imu_sim.lib.imu_sim import MPU9250

G = 9.80665

def Rx(deg: float) -> np.ndarray:
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[1, 0, 0],
                     [0, c,-s],
                     [0, s, c]])

def Ry(deg: float) -> np.ndarray:
    th = np.deg2rad(deg); c, s = np.cos(th), np.sin(th)
    return np.array([[ c, 0, s],
                     [ 0, 1, 0],
                     [-s, 0, c]])

def Rz(deg: float) -> np.ndarray:
    th = np.deg2rad(deg); c, s = np.sin(th), np.cos(th)
    # swap to keep standard convention
    s, c = np.sin(th), np.cos(th)
    return np.array([[c,-s, 0],
                     [s, c, 0],
                     [0, 0, 1]])

def euler_R_world_to_sensor(roll_deg: float, pitch_deg: float, yaw_deg: float) -> np.ndarray:
    """
    Build world->sensor rotation. Convention used here:
      R = Rx(roll) @ Ry(pitch) @ Rz(yaw)
    Notes:
      - Gravity is [0,0,+g] in world (ENU, Z up).
      - Roll (about X) mixes Y/Z; Pitch (about Y) mixes X/Z; Yaw (about Z) does not change gravity projection.
    """
    return Rx(roll_deg) @ Ry(pitch_deg) @ Rz(yaw_deg)


def step_profile(t: float, axis: int = 0, amp_g: float = 1.0,
                 T_on: float = 0.5, T_off: float = 0.5, T_neg: float = 0.5) -> np.ndarray:
    """
    Piecewise profile: +amp_g (g) -> 0 -> -amp_g (g) repeating.
    Returns linear acceleration WITHOUT gravity in m/s^2 in world frame.
    """
    a = np.zeros(3, dtype=float)
    T = T_on + T_off + T_neg
    tau = t % T
    if tau < T_on:
        a[axis] = +amp_g * G
    elif tau < T_on + T_off:
        a[axis] = 0.0
    else:
        a[axis] = -amp_g * G
    return a

def sine_profile(t: float, axis: int = 0, amp_g: float = 1.0, freq_hz: float = 1.0) -> np.ndarray:
    """
    Sinusoidal profile of amplitude amp_g (g) at freq_hz (Hz).
    Returns linear acceleration WITHOUT gravity in m/s^2 in world frame.
    """
    a = np.zeros(3, dtype=float)
    a[axis] = amp_g * G * math.sin(2.0 * math.pi * freq_hz * t)
    return a

def run_and_plot(config_path: str,
                 scenario: str = "step",       # "step" or "sine"
                 axis: int = 0,                 # 0:X, 1:Y, 2:Z (sensor/world aligned in this demo)
                 amp_g: float = 1.0,
                 freq_hz: float = 1.0,
                 duration_s: float = 3.0,
                 seed: int | None = 1,
                 lpf_cut_hz: float = 100.0,
                 roll_deg: float = 0.0,
                 pitch_deg: float = 0.0,
                 yaw_deg: float = 0.0):
    """
    Initializes MPU9250 + AccelSim from INI config, generates a time series using the chosen scenario,
    and plots a_g (g) and counts (int16) over time.
    """
    # 1) Init device + accel sim
    imu = MPU9250(config_path)
    imu.read_config()
    imu.init_accel_sim(seed=seed, lpf_cut_hz=lpf_cut_hz)

    fs = float(imu.accel_odr_hz)
    Ts = 1.0 / fs
    N = int(duration_s * fs)

    # Rotation: world -> sensor (use Euler angles from parameters)
    R_world_to_sensor = euler_R_world_to_sensor(roll_deg, pitch_deg, yaw_deg)

    t_arr = np.arange(N) * Ts
    a_g_arr = np.zeros((N, 3), dtype=float)
    cnt_arr = np.zeros((N, 3), dtype=np.int16)

    # 2) Generate samples
    for i, t in enumerate(t_arr):
        if scenario == "step":
            a_lin = step_profile(t, axis=axis, amp_g=amp_g)
        elif scenario == "sine":
            a_lin = sine_profile(t, axis=axis, amp_g=amp_g, freq_hz=freq_hz)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        counts, a_g = imu.sample_accel(a_lin, R_world_to_sensor)
        a_g_arr[i, :] = a_g
        cnt_arr[i, :] = counts

    # 3) Plot (single figure with a_g; counts optional second plot)
    plt.figure(figsize=(10, 5))
    plt.plot(t_arr, a_g_arr[:, 0], label="a_x [g]")
    plt.plot(t_arr, a_g_arr[:, 1], label="a_y [g]")
    plt.plot(t_arr, a_g_arr[:, 2], label="a_z [g]")
    plt.title(
        f"Accelerometer (a_g) — scenario={scenario}, axis={'XYZ'[axis]}, "
        f"ODR={fs:.1f} Hz, RPY=({roll_deg:.1f},{pitch_deg:.1f},{yaw_deg:.1f})°"
    )
    plt.xlabel("Time [s]")
    plt.ylabel("Acceleration [g]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # Optional: counts plot
    plt.figure(figsize=(10, 5))
    plt.plot(t_arr, cnt_arr[:, 0], label="counts_x")
    plt.plot(t_arr, cnt_arr[:, 1], label="counts_y")
    plt.plot(t_arr, cnt_arr[:, 2], label="counts_z")
    plt.title(
        f"Accelerometer (counts) — scenario={scenario}, axis={'XYZ'[axis]}, "
        f"range ±{_guess_range_g(imu)} g, RPY=({roll_deg:.1f},{pitch_deg:.1f},{yaw_deg:.1f})°"
    )
    plt.xlabel("Time [s]")
    plt.ylabel("Counts [int16]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.show()

def _guess_range_g(imu: MPU9250) -> int:
    """
    Utility to print human-friendly range from your enum setting.
    Adjust if your enum changes.
    """
    from simulators.imu_sim.lib.enums import AccelerometerRange
    m = {
        AccelerometerRange.ACCEL_RANGE_2G: 2,
        AccelerometerRange.ACCEL_RANGE_4G: 4,
        AccelerometerRange.ACCEL_RANGE_8G: 8,
        AccelerometerRange.ACCEL_RANGE_16G: 16,
    }
    return m.get(imu.accel_range, -1)


if __name__ == "__main__":
    CONFIG_PATH = "./simulators/imu_sim/config.ini"
    SCENARIO    = "step"        # "step" or "sine"
    AXIS        = 0             # 0:X, 1:Y, 2:Z
    AMP_G       = 1.0           # amplitude in g for step/sine
    FREQ_HZ     = 1.5           # used only for "sine"
    DURATION_S  = 3.0           # total time to simulate
    SEED        = 1             # for reproducibility of noise
    LPF_CUT_HZ  = 100.0         # 0.0 disables LPF

    ROLL_DEG   = 0.0            # rotation about sensor X
    PITCH_DEG  = 0.0            # rotation about sensor Y
    YAW_DEG    = 0.0            # rotation about sensor Z

    run_and_plot(
        CONFIG_PATH,
        SCENARIO,
        AXIS,
        AMP_G,
        FREQ_HZ,
        DURATION_S,
        SEED,
        LPF_CUT_HZ,
        roll_deg=ROLL_DEG,
        pitch_deg=PITCH_DEG,
        yaw_deg=YAW_DEG,
    )
