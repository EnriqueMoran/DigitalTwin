import numpy as np
import pytest

from simulators.imu_sim.lib.imu_sim import MPU9250


CONFIG_NO_NOISE = """
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
bias_x = 0.1
bias_y = -0.2
bias_z = 0.3
noise_density = 0.01
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

CONFIG_WITH_BIAS = """
[accelerometer]
range = 1
dlpf = 1
bias_x = 0.01
bias_y = -0.02
bias_z = 0.03
noise_density = 0.0
sample_rate_div = 4

[gyroscope]
range = 1
dlpf = 1
bias_x = 0.1
bias_y = -0.2
bias_z = 0.3
noise_density = 0.01
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

CONFIG_RANGE_14BIT = """
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
range = 1
mode = 4
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
world_x = 10.0
world_y = 0.0
world_z = 0.0
"""

CONFIG_MODE_8HZ = """
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
mode = 3
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


def Rz(deg: float) -> np.ndarray:
    th = np.deg2rad(deg)
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s, 0.0],
                     [s,  c, 0.0],
                     [0.0, 0.0, 1.0]])


def test_mag_sample_requires_init(tmp_path):
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    R = np.eye(3)
    with pytest.raises(RuntimeError):
        imu.sample_mag(R)


def test_mag_no_noise_identity_rotation(tmp_path):
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_mag_sim(seed=0, lpf_cut_hz=0.0)

    # 16-bit mode (range=2) -> ~0.15 µT/LSB -> counts/µT ≈ 6.6666667
    cps = 1.0 / 0.15

    R = np.eye(3)
    counts, B_uT = imu.sample_mag(R)

    # world=[20,0,40], bias=[3,-1.5,0.5] -> sensor=[23,-1.5,40.5]
    exp = np.array([23.0, -1.5, 40.5])
    assert np.allclose(B_uT, exp, atol=1e-12)

    exp_counts = np.rint(exp * cps).astype(int)
    assert counts.dtype == np.int16
    assert (counts == exp_counts).all()


def test_mag_bias_effect(tmp_path):
    cfg_path = write_cfg(tmp_path, CONFIG_WITH_BIAS)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_mag_sim(seed=0, lpf_cut_hz=0.0)

    R = np.eye(3)
    counts, B_uT = imu.sample_mag(R)

    # bias already non-zero in config
    assert abs(B_uT[0] - 23.0) < 1e-12
    assert abs(B_uT[1] + 1.5) < 1e-12
    assert abs(B_uT[2] - 40.5) < 1e-12
    assert counts.dtype == np.int16


def test_mag_rotation_yaw_90deg(tmp_path):
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_mag_sim(seed=0, lpf_cut_hz=0.0)

    # Rotate world->sensor by +90° yaw
    R = Rz(90.0)

    # world=[20,0,40] -> rotate -> [0,20,40]; then + bias=[3,-1.5,0.5] -> [3,18.5,40.5]
    counts, B_uT = imu.sample_mag(R)
    exp = np.array([3.0, 18.5, 40.5])
    assert np.allclose(B_uT, exp, atol=1e-12)


def test_mag_quantization_16bit_vs_14bit(tmp_path):
    # 16-bit case (0.15 µT/LSB -> 6.6667 counts/µT)
    cfg16 = CONFIG_NO_NOISE
    cfg_path = write_cfg(tmp_path, cfg16)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_mag_sim(seed=0, lpf_cut_hz=0.0)

    R = np.eye(3)
    counts16, B16 = imu.sample_mag(R)
    exp_counts16 = np.rint(B16 * (1.0 / 0.15)).astype(int)
    assert (counts16 == exp_counts16).all()

    # 14-bit case (0.6 µT/LSB -> 1.6667 counts/µT)
    cfg14 = CONFIG_RANGE_14BIT
    cfg_path = write_cfg(tmp_path, cfg14)
    imu2 = MPU9250(cfg_path)
    imu2.read_config()
    imu2.init_mag_sim(seed=0, lpf_cut_hz=0.0)

    counts14, B14 = imu2.sample_mag(np.eye(3))
    exp_counts14 = np.rint(B14 * (1.0 / 0.6)).astype(int)
    assert (counts14 == exp_counts14).all()


def test_mag_odr_from_mode(tmp_path):
    # mode=4 -> 100 Hz
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert abs(float(imu.mag_odr_hz) - 100.0) < 1e-12

    # mode=3 -> 8 Hz
    cfg_path = write_cfg(tmp_path, CONFIG_MODE_8HZ)
    imu2 = MPU9250(cfg_path)
    imu2.read_config()
    assert abs(float(imu2.mag_odr_hz) - 8.0) < 1e-12
