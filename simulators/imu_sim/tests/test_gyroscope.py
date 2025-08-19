import math
import numpy as np
import pytest

from simulators.imu_sim.lib.imu_sim import MPU9250

CONFIG_GYRO_NO_NOISE = """
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
sample_rate_div = 0
"""

CONFIG_GYRO_WITH_BIAS = """
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
noise_density = 0.0
sample_rate_div = 0
"""

CONFIG_GYRO_LPF = """
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
sample_rate_div = 0
"""


def write_cfg(tmp_path, content: str) -> str:
    p = tmp_path / "imu_config.ini"
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_sample_gyro_requires_init(tmp_path):
    """
    sample_gyro() must not be callable before init_gyro_sim().
    """
    cfg_path = write_cfg(tmp_path, CONFIG_GYRO_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    R = np.eye(3)
    w_world = np.zeros(3)
    with pytest.raises(RuntimeError):
        imu.sample_gyro(w_world, R)


def test_gyro_rest_zero_with_no_noise(tmp_path):
    """
    With zero angular rate, identity rotation, zero bias and no noise,
    we expect [0, 0, 0] dps and corresponding int16 counts of [0, 0, 0].
    """
    cfg_path = write_cfg(tmp_path, CONFIG_GYRO_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_gyro_sim(seed=123, lpf_cut_hz=100.0)

    R = np.eye(3)
    w_world = np.zeros(3)
    counts, w_dps = imu.sample_gyro(w_world, R)

    assert np.allclose(w_dps, [0.0, 0.0, 0.0], atol=1e-12)
    assert counts[0] == 0 and counts[1] == 0 and counts[2] == 0


def test_gyro_bias_effect_is_applied(tmp_path):
    """
    Non-zero bias should shift the output in dps before quantization.
    In ±250 dps, scale is 131 LSB/(°/s).
    """
    cfg_path = write_cfg(tmp_path, CONFIG_GYRO_WITH_BIAS)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_gyro_sim(seed=0, lpf_cut_hz=100.0)

    R = np.eye(3)
    w_world = np.zeros(3)  # only bias present
    counts, w_dps = imu.sample_gyro(w_world, R)

    assert abs(w_dps[0] - 0.1) < 1e-12
    assert abs(w_dps[1] + 0.2) < 1e-12
    assert abs(w_dps[2] - 0.3) < 1e-12

    exp_counts = np.rint(np.array([0.1, -0.2, 0.3]) * 131.0).astype(int)
    assert counts[0] == exp_counts[0]
    assert counts[1] == exp_counts[1]
    assert counts[2] == exp_counts[2]


def test_gyro_saturation_clip_at_range_edges(tmp_path):
    """
    A large angular rate should saturate at ±range and clip counts at int16 limits.
    For ±250 dps, +250 dps → ~32750 LSB, clipped to 32767.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_GYRO_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_gyro_sim(seed=0, lpf_cut_hz=0.0)

    R = np.eye(3)
    w_world = np.array([1000.0, 0.0, 0.0], dtype=float)  # way above +250
    counts, w_dps = imu.sample_gyro(w_world, R)

    assert w_dps[0] == 250.0
    assert counts[0] >= 32750  # after rounding and saturation
    assert counts[1] == 0 and counts[2] == 0


def test_gyro_lpf_attenuates_high_frequency(tmp_path):
    """
    With a low LPF cutoff, a high-frequency sinusoidal angular rate on X
    should be significantly attenuated compared to a high cutoff.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_GYRO_LPF)
    imu_low = MPU9250(cfg_path);  imu_low.read_config();  imu_low.init_gyro_sim(seed=0, lpf_cut_hz=20.0)
    imu_high = MPU9250(cfg_path); imu_high.read_config(); imu_high.init_gyro_sim(seed=0, lpf_cut_hz=500.0)

    # ODR with ACTIVE and smplrt_div=0 should be 1000 Hz
    fs_low = imu_low.gyro_odr_hz
    fs_high = imu_high.gyro_odr_hz
    assert abs(fs_low - 1000.0) < 1e-6 and abs(fs_high - 1000.0) < 1e-6

    R = np.eye(3)
    N = 1000
    t = np.arange(N) / fs_low

    # 200 Hz sinusoid @ 50 dps amplitude (well below range)
    amp = 50.0
    w_x = amp * np.sin(2 * math.pi * 200.0 * t)

    x_low = []
    x_high = []
    for i in range(N):
        w_world = np.array([w_x[i], 0.0, 0.0], dtype=float)
        _, w_low = imu_low.sample_gyro(w_world, R)
        _, w_hig = imu_high.sample_gyro(w_world, R)
        x_low.append(w_low[0]); x_high.append(w_hig[0])

    x_low = np.array(x_low)
    x_high = np.array(x_high)

    # Compare RMS (remove any small DC offset)
    rms_low  = np.sqrt(np.mean((x_low  - np.mean(x_low ))**2))
    rms_high = np.sqrt(np.mean((x_high - np.mean(x_high))**2))

    # Expect strong attenuation at 200 Hz for 20 Hz cutoff
    assert rms_low < 0.5 * rms_high
