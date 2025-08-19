import math
import numpy as np
import pytest

from simulators.imu_sim.lib.imu_sim import MPU9250
from simulators.imu_sim.lib.enums import MagnetometerMode, DLPF


CONFIG_ALL_NO_NOISE = """
[accelerometer]
range = 1
dlpf = 1
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
sample_rate_div = 4

[gyroscope]
range = 1
dlpf = 1
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
sample_rate_div = 4

[magnetometer]
range = 2
mode = 4
bias_x = 3.0
bias_y = -1.5
bias_z = 0.5
noise_density = 0.0
world_x = 20.0
world_y = 0.0
world_z = 40.0
"""

CONFIG_MAG_POWERDOWN = """
[accelerometer]
range = 1
dlpf = 1
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
sample_rate_div = 4

[gyroscope]
range = 1
dlpf = 1
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
sample_rate_div = 4

[magnetometer]
range = 2
mode = 1
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
world_x = 20.0
world_y = 0.0
world_z = 40.0
"""


def write_cfg(tmp_path, content: str) -> str:
    p = tmp_path / "imu_config.ini"
    p.write_text(content, encoding="utf-8")
    return str(p)

def static_motion_provider(t: float):
    """
    World->sensor rotation = I, no linear accel (gravity handled in AccelSim),
    no angular rate.
    """
    R = np.eye(3)
    a_lin_world_ms2 = np.zeros(3, dtype=float)
    omega_world_dps = np.zeros(3, dtype=float)
    return a_lin_world_ms2, omega_world_dps, R


def test_simulate_counts_and_values_static(tmp_path):
    """
    With accel/gyro DLPF=ACTIVE and div=4 → fs=200 Hz; mag CONT_100HZ → 100 Hz.
    For duration=0.1 s with sampling at t=0 included, N = floor(fs*duration)+1.
    Values: accel ~ [0,0,1] g; gyro ~ [0,0,0] dps; mag = world + bias (R=I).
    """
    cfg_path = write_cfg(tmp_path, CONFIG_ALL_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    # Defensive: ensure parsed as expected
    assert imu.accel_dlpf == DLPF.ACTIVE and imu.accel_odr_hz == pytest.approx(200.0)
    assert imu.gyro_odr_hz  == pytest.approx(200.0)
    assert imu.mag_odr_hz   == pytest.approx(100.0)

    imu.init_all_sims(accel_seed=1, gyro_seed=1, mag_seed=1,
                      accel_lpf_cut_hz=100.0, gyro_lpf_cut_hz=98.0)

    duration = 0.1
    out = imu.simulate(duration, static_motion_provider)

    # Expected sample counts
    n_acc  = math.floor(imu.accel_odr_hz * duration) + 1
    n_gyro = math.floor(imu.gyro_odr_hz  * duration) + 1
    n_mag  = math.floor(imu.mag_odr_hz   * duration) + 1

    assert out["accel"]["t"].shape[0] == n_acc
    assert out["gyro"]["t"].shape[0]  == n_gyro
    assert out["mag"]["t"].shape[0]   == n_mag

    # Accel expected last sample ~ [0,0,1] g (no noise, R=I, gravity inside sim)
    a_last = out["accel"]["meas"][-1]
    assert np.allclose(a_last[:2], [0.0, 0.0], atol=1e-12)
    assert a_last[2] == pytest.approx(1.0, abs=1e-12)

    # Gyro expected last sample ~ zeros
    w_last = out["gyro"]["meas"][-1]
    assert np.allclose(w_last, np.zeros(3), atol=1e-12)

    # Mag expected last sample = world + bias (R=I), noise=0
    B_last = out["mag"]["meas"][-1]
    expect_B = np.array([23.0, -1.5, 40.5])  # (20,0,40) + (3,-1.5,0.5)
    assert np.allclose(B_last, expect_B, atol=1e-12)


def test_timestamps_are_monotonic_and_evenly_spaced(tmp_path):
    """
    Timestamps must be strictly non-decreasing and approximately uniform with step 1/fs.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_ALL_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_all_sims(accel_seed=0, gyro_seed=0, mag_seed=0)

    out = imu.simulate(0.05, static_motion_provider)

    for key, fs in (("accel", imu.accel_odr_hz),
                    ("gyro",  imu.gyro_odr_hz),
                    ("mag",   imu.mag_odr_hz)):
        t = out[key]["t"]
        assert np.all(np.diff(t) >= -1e-15)
        if t.size >= 3:
            dt = np.diff(t)
            # Allow tiny floating error tolerance
            assert np.allclose(dt, 1.0/float(fs), atol=1e-12)


def test_init_all_sims_raises_if_mag_not_continuous(tmp_path):
    """
    init_all_sims() must raise if magnetometer mode is not continuous (e.g. POWER_DOWN).
    """
    cfg_path = write_cfg(tmp_path, CONFIG_MAG_POWERDOWN)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert imu.mag_mode == MagnetometerMode.POWER_DOWN
    with pytest.raises(RuntimeError):
        imu.init_all_sims()


def test_event_alignment_when_changing_odr(tmp_path):
    """
    Changing accel smplrt_div to 0 (DLPF=ACTIVE) → fs_acc=1000 Hz.
    With duration=0.003 s: N_acc = floor(3 * 1000e-3) + 1 = 4 samples.
    Gyro stays 200 Hz (= floor(0.003*200)+1 = 1) and mag 100 Hz (=1).
    """
    # Start from base config and tweak accel sample_rate_div
    cfg = CONFIG_ALL_NO_NOISE.replace("sample_rate_div = 4", "sample_rate_div = 0", 1)
    cfg_path = write_cfg(tmp_path, cfg)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert imu.accel_odr_hz == pytest.approx(1000.0)
    assert imu.gyro_odr_hz  == pytest.approx(200.0)
    assert imu.mag_odr_hz   == pytest.approx(100.0)

    imu.init_all_sims()
    out = imu.simulate(0.003, static_motion_provider)

    n_acc  = math.floor(0.003 * 1000.0) + 1  # 4
    n_gyro = math.floor(0.003 * 200.0)  + 1  # 1
    n_mag  = math.floor(0.003 * 100.0)  + 1  # 1

    assert out["accel"]["t"].shape[0] == n_acc
    assert out["gyro"]["t"].shape[0]  == n_gyro
    assert out["mag"]["t"].shape[0]   == n_mag
