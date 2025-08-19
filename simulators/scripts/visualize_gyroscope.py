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
    """
    Build world->sensor rotation. Convention:
      R = Rx(roll) @ Ry(pitch) @ Rz(yaw)
    """
    return Rx(roll_deg) @ Ry(pitch_deg) @ Rz(yaw_deg)

def step_rate_profile(t: float, axis: int = 0, amp_dps: float = 50.0,
                      T_pos: float = 0.5, T_zero: float = 0.5, T_neg: float = 0.5) -> np.ndarray:
    """
    Piecewise angular rate profile in world frame (°/s):
      +amp_dps for T_pos -> 0 for T_zero -> -amp_dps for T_neg, repeating.
    Returns omega_world_dps (3,) in °/s.
    """
    w = np.zeros(3, dtype=float)
    T = T_pos + T_zero + T_neg
    tau = t % T
    if tau < T_pos:
        w[axis] = +amp_dps
    elif tau < T_pos + T_zero:
        w[axis] = 0.0
    else:
        w[axis] = -amp_dps
    return w

def sine_rate_profile(t: float, axis: int = 0, amp_dps: float = 50.0, freq_hz: float = 1.0) -> np.ndarray:
    """
    Sinusoidal angular rate in world frame (°/s):
      w_axis(t) = amp_dps * sin(2π f t)
    Returns omega_world_dps (3,) in °/s.
    """
    w = np.zeros(3, dtype=float)
    w[axis] = amp_dps * math.sin(2.0 * math.pi * freq_hz * t)
    return w

def _guess_range_dps(imu: MPU9250) -> int:
    """
    Utility to print human-friendly gyro range from your enum setting.
    """
    from simulators.imu_sim.lib.enums import GyroscopeRange
    m = {
        GyroscopeRange.GYRO_RANGE_250DPS: 250,
        GyroscopeRange.GYRO_RANGE_500DPS: 500,
        GyroscopeRange.GYRO_RANGE_1000DPS: 1000,
        GyroscopeRange.GYRO_RANGE_2000DPS: 2000,
    }
    return m.get(imu.gyro_range, -1)

def run_and_plot_gyro(config_path: str,
                      scenario: str = "step",     # "step" or "sine"
                      axis: int = 0,               # 0:X, 1:Y, 2:Z
                      amp_dps: float = 50.0,
                      freq_hz: float = 2.0,
                      duration_s: float = 3.0,
                      seed: int | None = 1,
                      lpf_cut_hz: float = 98.0,
                      roll_deg: float = 0.0,
                      pitch_deg: float = 0.0,
                      yaw_deg: float = 0.0):
    """
    Initializes MPU9250 + GyroSim from INI config, generates a time series using the chosen scenario,
    and plots omega_dps (°/s) and counts (int16) over time.
    """
    # 1) Init device + gyro sim
    imu = MPU9250(config_path)
    imu.read_config()
    imu.init_gyro_sim(seed=seed, lpf_cut_hz=lpf_cut_hz)

    fs = float(imu.gyro_odr_hz)
    Ts = 1.0 / fs
    N = int(duration_s * fs)

    # Rotation: world -> sensor (use Euler angles from parameters)
    R_world_to_sensor = euler_R_world_to_sensor(roll_deg, pitch_deg, yaw_deg)

    t_arr = np.arange(N) * Ts
    w_dps_arr = np.zeros((N, 3), dtype=float)
    cnt_arr = np.zeros((N, 3), dtype=np.int16)

    # 2) Generate samples
    for i, t in enumerate(t_arr):
        if scenario == "step":
            w_world = step_rate_profile(t, axis=axis, amp_dps=amp_dps)
        elif scenario == "sine":
            w_world = sine_rate_profile(t, axis=axis, amp_dps=amp_dps, freq_hz=freq_hz)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        counts, w_dps = imu.sample_gyro(w_world, R_world_to_sensor)
        w_dps_arr[i, :] = w_dps
        cnt_arr[i, :] = counts

    # 3) Plot °/s
    plt.figure(figsize=(10, 5))
    plt.plot(t_arr, w_dps_arr[:, 0], label="ω_x [°/s]")
    plt.plot(t_arr, w_dps_arr[:, 1], label="ω_y [°/s]")
    plt.plot(t_arr, w_dps_arr[:, 2], label="ω_z [°/s]")
    plt.title(
        f"Gyroscope (°/s) — scenario={scenario}, axis={'XYZ'[axis]}, "
        f"ODR={fs:.1f} Hz, RPY=({roll_deg:.1f},{pitch_deg:.1f},{yaw_deg:.1f})°"
    )
    plt.xlabel("Time [s]")
    plt.ylabel("Angular rate [°/s]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    # 4) Plot counts
    plt.figure(figsize=(10, 5))
    plt.plot(t_arr, cnt_arr[:, 0], label="counts_x")
    plt.plot(t_arr, cnt_arr[:, 1], label="counts_y")
    plt.plot(t_arr, cnt_arr[:, 2], label="counts_z")
    plt.title(
        f"Gyroscope (counts) — scenario={scenario}, axis={'XYZ'[axis]}, "
        f"range ±{_guess_range_dps(imu)} dps, RPY=({roll_deg:.1f},{pitch_deg:.1f},{yaw_deg:.1f})°"
    )
    plt.xlabel("Time [s]")
    plt.ylabel("Counts [int16]")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()

    plt.show()

if __name__ == "__main__":
    CONFIG_PATH = "./simulators/imu_sim/config.ini"
    SCENARIO    = "sine"       # "step" or "sine"
    AXIS        = 0            # 0:X, 1:Y, 2:Z
    AMP_DPS     = 80.0         # amplitude in °/s
    FREQ_HZ     = 3.0          # used only for "sine"
    DURATION_S  = 3.0
    SEED        = 1
    LPF_CUT_HZ  = 98.0         # 0.0 disables LPF

    ROLL_DEG   = 0.0
    PITCH_DEG  = 0.0
    YAW_DEG    = 0.0

    run_and_plot_gyro(
        CONFIG_PATH,
        SCENARIO,
        AXIS,
        AMP_DPS,
        FREQ_HZ,
        DURATION_S,
        SEED,
        LPF_CUT_HZ,
        roll_deg=ROLL_DEG,
        pitch_deg=PITCH_DEG,
        yaw_deg=YAW_DEG,
    )
