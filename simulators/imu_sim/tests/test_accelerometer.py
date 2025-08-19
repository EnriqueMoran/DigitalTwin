import math
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
"""

CONFIG_LPF = """
[accelerometer]
range = 1
dlpf = 1
bias_x = 0.0
bias_y = 0.0
bias_z = 0.0
noise_density = 0.0
sample_rate_div = 0

[gyroscope]
range = 1
dlpf = 1
bias_x = 0.1
bias_y = -0.2
bias_z = 0.3
noise_density = 0.01
sample_rate_div = 4
"""


def write_cfg(tmp_path, content: str) -> str:
    p = tmp_path / "imu_config.ini"
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_sample_requires_init(tmp_path):
    """
    sample_accel() must not be callable before init_accel_sim().
    """
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    R = np.eye(3)
    a_lin = np.zeros(3)
    with pytest.raises(RuntimeError):
        imu.sample_accel(a_lin, R)


def test_static_rest_1g_no_noise(tmp_path):
    """
    With zero linear acceleration, identity rotation, zero bias and no noise,
    we expect ~[0, 0, +1.0] g and the corresponding int16 counts for ±2 g.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_accel_sim(seed=123, lpf_cut_hz=100.0)

    R = np.eye(3)
    a_lin = np.zeros(3)
    counts, a_g = imu.sample_accel(a_lin, R)

    assert np.allclose(a_g[:2], [0.0, 0.0], atol=1e-9)
    assert abs(a_g[2] - 1.0) < 1e-9

    # In ±2 g, 1 g -> 16384 LSB
    assert counts[0] == 0 and counts[1] == 0
    assert counts[2] == 16384


def test_bias_effect_is_applied(tmp_path):
    """
    Non-zero bias should shift the output in g units before quantization.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_WITH_BIAS)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_accel_sim(seed=0, lpf_cut_hz=100.0)

    R = np.eye(3)
    a_lin = np.zeros(3)
    counts, a_g = imu.sample_accel(a_lin, R)

    # Expected in g with gravity included:
    # X: +0.01 g, Y: -0.02 g, Z: 1.0 + 0.03 = 1.03 g
    assert abs(a_g[0] - 0.01) < 1e-9
    assert abs(a_g[1] + 0.02) < 1e-9
    assert abs(a_g[2] - 1.03) < 1e-9

    # Check quantization for ±2 g (16384 LSB/g)
    exp_counts = np.rint(np.array([0.01, -0.02, 1.03]) * 16384).astype(int)
    assert counts[0] == exp_counts[0]
    assert counts[1] == exp_counts[1]
    assert counts[2] == exp_counts[2]


def test_saturation_clip_at_range_edges(tmp_path):
    """
    A large positive Z linear acceleration should saturate at +range,
    and counts should clip at int16 max.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_NO_NOISE)
    imu = MPU9250(cfg_path)
    imu.read_config()
    imu.init_accel_sim(seed=0, lpf_cut_hz=0.0)

    R = np.eye(3)
    # +30 m/s^2 along +Z (world) -> in sensor with R=I
    # a_true_g ≈ 30/9.80665 + 1.0 ≈ 4.06 g -> should clip to +2.0 g in ±2 g range
    a_lin = np.array([0.0, 0.0, 30.0], dtype=float)
    counts, a_g = imu.sample_accel(a_lin, R)

    assert a_g[2] == 2.0
    # 2 g -> 32768 LSB, but clipped to int16 max 32767 after rounding
    assert counts[2] >= 32760
    assert counts[0] == 0 and counts[1] == 0


def test_lpf_roughly_attenuates_high_frequency(tmp_path):
    """
    With a low LPF cutoff, a high-frequency sinusoidal linear acceleration on X
    should be significantly attenuated compared to a high cutoff.
    """
    cfg_path = write_cfg(tmp_path, CONFIG_LPF)
    imu = MPU9250(cfg_path)
    imu.read_config()

    # Two simulators: low cutoff (20 Hz) vs high cutoff (500 Hz approx passthrough)
    imu_low = MPU9250(cfg_path); imu_low.read_config();  imu_low.init_accel_sim(seed=0, lpf_cut_hz=20.0)
    imu_high = MPU9250(cfg_path); imu_high.read_config(); imu_high.init_accel_sim(seed=0, lpf_cut_hz=500.0)

    R = np.eye(3)

    # ODR: dlpf=ACTIVE and smplrt_div=0 -> base 1000 Hz, so ODR=1000 Hz
    fs = imu_low.accel_odr_hz
    assert abs(fs - 1000.0) < 1e-6

    # 200 Hz sinusoid on X axis (well above 20 Hz cutoff; below Nyquist)
    N = 1000
    t = np.arange(N) / fs
    amp_g = 0.2  # 0.2 g amplitude
    a_x_ms2 = amp_g * 9.80665 * np.sin(2 * math.pi * 200.0 * t)

    x_low = []
    x_high = []
    for i in range(N):
        a_lin = np.array([a_x_ms2[i], 0.0, 0.0], dtype=float)
        _, a_g_low = imu_low.sample_accel(a_lin, R)
        _, a_g_high = imu_high.sample_accel(a_lin, R)
        x_low.append(a_g_low[0])
        x_high.append(a_g_high[0])

    x_low = np.array(x_low)
    x_high = np.array(x_high)

    # Remove any DC (should be ~0 anyway) and compare RMS
    rms_low = np.sqrt(np.mean((x_low - np.mean(x_low))**2))
    rms_high = np.sqrt(np.mean((x_high - np.mean(x_high))**2))

    # Expect strong attenuation at 200 Hz for 20 Hz cutoff
    assert rms_low < 0.5 * rms_high
