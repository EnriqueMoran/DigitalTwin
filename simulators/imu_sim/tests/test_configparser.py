import pytest

from simulators.imu_sim.lib.enums import AccelerationRange, DLPF
from simulators.imu_sim.lib.imu import MPU9250

VALID_CONFIG = """
[accelerometer]
range = 1
dlpf = 1
bias_x = 0.01
bias_y = -0.02
bias_z = 0.03
noise_density = 0.0003
sample_rate_div = 4
"""

def write_cfg(tmp_path, content: str) -> str:
    p = tmp_path / "imu_config.ini"
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_valid_config_loads_correctly(tmp_path):
    """Parser should populate all accelerometer fields with expected values from a valid INI."""
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert imu.accel_range == AccelerationRange.ACCEL_RANGE_2G
    assert imu.accel_dlpf == DLPF.ACTIVE
    assert imu.accel_bias == [0.01, -0.02, 0.03]
    assert abs(imu.accel_noise_density - 0.0003) < 1e-12
    assert imu.accel_smplrt_div == 4


def test_invalid_accel_range_raises_value_error(tmp_path):
    """An out-of-range accelerometer 'range' code must raise ValueError during parsing."""
    bad = VALID_CONFIG.replace("range = 1", "range = 99", 1)
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_accel_dlpf_raises_value_error(tmp_path):
    """An invalid DLPF code must raise ValueError during parsing."""
    bad = VALID_CONFIG.replace("dlpf = 1", "dlpf = 5", 1)
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_bias_type_raises_value_error(tmp_path):
    """Non-numeric bias values in the config must raise ValueError during parsing."""
    bad = VALID_CONFIG.replace("bias_x = 0.01", "bias_x = text", 1)
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_negative_sample_rate_div_raises_type_error(tmp_path):
    """A negative sample_rate_div must raise TypeError (expects non-negative integer)."""
    bad = VALID_CONFIG.replace("sample_rate_div = 4", "sample_rate_div = -3", 1)
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(TypeError):
        imu.read_config()


def test_accel_range_rejects_invalid_type():
    """Setter must reject non-int / non-enum types for accel_range."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.accel_range = "2g"
    with pytest.raises(TypeError):
        imu.accel_range = [1]


def test_accel_dlpf_rejects_invalid_type():
    """Setter must reject non-int / non-enum types for accel_dlpf."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.accel_dlpf = 3.14
    with pytest.raises(TypeError):
        imu.accel_dlpf = {"dlpf": 1}


def test_accel_bias_rejects_invalid_type_and_shape():
    """Setter must accept only a list of three numeric values for accel_bias."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.accel_bias = "0.0,0.0,0.0"
    with pytest.raises(TypeError):
        imu.accel_bias = [0.0, 1.0]
    with pytest.raises(TypeError):
        imu.accel_bias = [0.0, "x", 1.0]


def test_accel_noise_density_rejects_invalid_type():
    """Setter must reject non-numeric types for accel_noise_density."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.accel_noise_density = "0.0003"


def test_accel_smplrt_div_rejects_invalid_type_and_negative():
    """Setter must reject non-int and negative values for accel_smplrt_div."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.ACTIVE
    with pytest.raises(TypeError):
        imu.accel_smplrt_div = "10"
    with pytest.raises(TypeError):
        imu.accel_smplrt_div = -5


def test_accel_smplrt_div_requires_dlpf_first():
    """Setting accel_smplrt_div before accel_dlpf must raise ValueError."""
    imu = MPU9250()
    with pytest.raises(ValueError):
        imu.accel_smplrt_div = 4


def test_odr_computation_active_dlpf():
    """With DLPF active: ODR = 1000 / (1 + div). For div=4 => 200 Hz."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.ACTIVE
    imu.accel_smplrt_div = 4
    assert abs(imu.accel_odr_hz - 200.0) < 1e-9


def test_odr_computation_bypass_dlpf():
    """With DLPF bypass: ODR = 4000 / (1 + div). For div=4 => 800 Hz."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.BYPASS
    imu.accel_smplrt_div = 4
    assert abs(imu.accel_odr_hz - 800.0) < 1e-9


def test_smplrt_div_multiple_of_4_required_in_bypass():
    """In bypass mode, sample_rate_div must be a multiple of 4."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.BYPASS
    with pytest.raises(ValueError):
        imu.accel_smplrt_div = 3
    imu.accel_smplrt_div = 8
    assert imu.accel_smplrt_div == 8
