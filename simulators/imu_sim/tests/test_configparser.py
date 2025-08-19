import pytest
import re

from simulators.imu_sim.lib.imu_sim import MPU9250
from simulators.imu_sim.lib.enums import (AccelerometerRange, GyroscopeRange, MagnetometerRange, 
                                          MagnetometerMode, DLPF)


VALID_CONFIG = """
[accelerometer]
range = 1
dlpf = 1
bias_x = 0.01
bias_y = -0.02
bias_z = 0.03
noise_density = 0.0003
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
noise_density = 0.4
world_x = 20.0
world_y = 0.0
world_z = 40.0
"""

def replace_kv_in_section(ini_text: str, section: str, key: str, new_value: str) -> str:
    import re
    pattern_section = rf"(?ms)^\[{re.escape(section)}\]\s*(.*?)(?=^\[|\Z)"
    m = re.search(pattern_section, ini_text)
    if not m:
        return ini_text
    body = m.group(1)

    pattern_kv = rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$"

    def _repl(match: re.Match) -> str:
        return f"{match.group(1)}{new_value}"

    new_body, n = re.subn(pattern_kv, _repl, body, count=1)
    if n == 0:
        if not body.endswith("\n"):
            body += "\n"
        new_body = body + f"{key} = {new_value}\n"

    start, end = m.span(1)
    return ini_text[:start] + new_body + ini_text[end:]


def write_cfg(tmp_path, content: str) -> str:
    p = tmp_path / "imu_config.ini"
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_valid_config_loads_correctly(tmp_path):
    """Parser should populate all accelerometer fields with expected values from a valid INI."""
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert imu.accel_range == AccelerometerRange.ACCEL_RANGE_2G
    assert imu.accel_dlpf == DLPF.ACTIVE
    assert imu.accel_bias == [0.01, -0.02, 0.03]
    assert abs(imu.accel_noise_density - 0.0003) < 1e-12
    assert imu.accel_smplrt_div == 4


def test_invalid_accel_range_raises_value_error(tmp_path):
    """An out-of-range accelerometer 'range' code must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "accelerometer", "range", "99")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_accel_dlpf_raises_value_error(tmp_path):
    """An invalid DLPF code must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "accelerometer", "dlpf", "5")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_bias_type_raises_value_error(tmp_path):
    """Non-numeric bias values in the config must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "accelerometer", "bias_x", "text")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_negative_sample_rate_div_raises_type_error(tmp_path):
    """A negative sample_rate_div must raise TypeError (expects non-negative integer)."""
    bad = replace_kv_in_section(VALID_CONFIG, "accelerometer", "sample_rate_div", "-3")
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


def test_accel_odr_computation_active_dlpf():
    """With DLPF active: ODR = 1000 / (1 + div). For div=4 => 200 Hz."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.ACTIVE
    imu.accel_smplrt_div = 4
    assert abs(imu.accel_odr_hz - 200.0) < 1e-9


def test_accel_odr_computation_bypass_dlpf():
    """With DLPF bypass: ODR = 4000 / (1 + div). For div=4 => 800 Hz."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.BYPASS
    imu.accel_smplrt_div = 4
    assert abs(imu.accel_odr_hz - 800.0) < 1e-9


def test_accel_smplrt_div_multiple_of_4_required_in_bypass():
    """In bypass mode, sample_rate_div must be a multiple of 4."""
    imu = MPU9250()
    imu.accel_dlpf = DLPF.BYPASS
    with pytest.raises(ValueError):
        imu.accel_smplrt_div = 3
    imu.accel_smplrt_div = 8
    assert imu.accel_smplrt_div == 8


def test_valid_gyro_config_loads_correctly(tmp_path):
    """Parser should populate all gyroscope fields with expected values from a valid INI."""
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert imu.gyro_range == GyroscopeRange.GYRO_RANGE_250DPS
    assert imu.gyro_dlpf == DLPF.ACTIVE
    assert imu.gyro_bias == [0.1, -0.2, 0.3]
    assert abs(imu.gyro_noise_density - 0.01) < 1e-12
    assert imu.gyro_smplrt_div == 4


def test_invalid_gyro_range_raises_value_error(tmp_path):
    """An out-of-range gyroscope 'range' code must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "gyroscope", "range", "99")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_gyro_dlpf_raises_value_error(tmp_path):
    """An invalid gyroscope DLPF code must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "gyroscope", "dlpf", "5")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_gyro_bias_type_raises_value_error(tmp_path):
    """Non-numeric gyroscope bias values in the config must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "gyroscope", "bias_x", "text")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_negative_gyro_sample_rate_div_raises_type_error(tmp_path):
    """A negative gyroscope sample_rate_div must raise TypeError (expects non-negative integer)."""
    bad = replace_kv_in_section(VALID_CONFIG, "gyroscope", "sample_rate_div", "-3")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(TypeError):
        imu.read_config()


def test_gyro_range_rejects_invalid_type():
    """Setter must reject non-int / non-enum types for gyro_range."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.gyro_range = "250dps"
    with pytest.raises(TypeError):
        imu.gyro_range = [1]


def test_gyro_dlpf_rejects_invalid_type():
    """Setter must reject non-int / non-enum types for gyro_dlpf."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.gyro_dlpf = 3.14
    with pytest.raises(TypeError):
        imu.gyro_dlpf = {"dlpf": 1}


def test_gyro_bias_rejects_invalid_type_and_shape():
    """Setter must accept only a list of three numeric values for gyro_bias."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.gyro_bias = "0.0,0.0,0.0"
    with pytest.raises(TypeError):
        imu.gyro_bias = [0.0, 1.0]
    with pytest.raises(TypeError):
        imu.gyro_bias = [0.0, "x", 1.0]


def test_gyro_noise_density_rejects_invalid_type():
    """Setter must reject non-numeric types for gyro_noise_density."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.gyro_noise_density = "0.01"


def test_gyro_smplrt_div_rejects_invalid_type_and_negative():
    """Setter must reject non-int and negative values for gyro_smplrt_div."""
    imu = MPU9250()
    imu.gyro_dlpf = DLPF.ACTIVE
    with pytest.raises(TypeError):
        imu.gyro_smplrt_div = "10"
    with pytest.raises(TypeError):
        imu.gyro_smplrt_div = -5


def test_gyro_smplrt_div_requires_dlpf_first():
    """Setting gyro_smplrt_div before gyro_dlpf must raise ValueError."""
    imu = MPU9250()
    with pytest.raises(ValueError):
        imu.gyro_smplrt_div = 4


def test_gyro_odr_computation_active_dlpf():
    """With DLPF active: ODR = 1000 / (1 + div). For div=4 => 200 Hz."""
    imu = MPU9250()
    imu.gyro_dlpf = DLPF.ACTIVE
    imu.gyro_smplrt_div = 4
    assert abs(imu.gyro_odr_hz - 200.0) < 1e-9


def test_gyro_odr_computation_bypass_dlpf():
    """With DLPF bypass: ODR = 32000 / (1 + div). For div=4 => 6400 Hz."""
    imu = MPU9250()
    imu.gyro_dlpf = DLPF.BYPASS
    imu.gyro_smplrt_div = 4
    assert abs(imu.gyro_odr_hz - 6400.0) < 1e-9


def test_valid_mag_config_loads_correctly(tmp_path):
    """Parser should populate all magnetometer fields with expected values from a valid INI."""
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    imu = MPU9250(cfg_path)
    imu.read_config()
    assert imu.mag_range == MagnetometerRange.MAG_RANGE_16BITS
    assert imu.mag_mode == MagnetometerMode.CONT_100HZ
    assert imu.mag_bias == [3.0, -1.5, 0.5]
    assert abs(imu.mag_noise_density - 0.4) < 1e-12
    assert imu.mag_world == [20.0, 0.0, 40.0]
    assert abs(imu.mag_odr_hz - 100.0) < 1e-12


def test_invalid_mag_range_raises_value_error(tmp_path):
    """An out-of-range magnetometer 'range' code must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "magnetometer", "range", "99")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_mag_mode_raises_value_error(tmp_path):
    """An invalid magnetometer mode code must raise ValueError during parsing."""
    bad = replace_kv_in_section(VALID_CONFIG, "magnetometer", "mode", "99")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_mag_bias_type_raises_value_error(tmp_path):
    """Non-numeric magnetometer bias values in the config must raise ValueError."""
    bad = replace_kv_in_section(VALID_CONFIG, "magnetometer", "bias_x", "text")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_mag_noise_density_type_raises_value_error(tmp_path):
    """Non-numeric magnetometer noise_density in the config must raise ValueError."""
    bad = replace_kv_in_section(VALID_CONFIG, "magnetometer", "noise_density", "text")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_negative_mag_noise_density_raises_type_error(tmp_path):
    """A negative magnetometer noise_density must raise TypeError."""
    bad = replace_kv_in_section(VALID_CONFIG, "magnetometer", "noise_density", "-0.1")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(TypeError):
        imu.read_config()


def test_invalid_mag_world_component_type_raises_value_error(tmp_path):
    """Non-numeric magnetometer world field components must raise ValueError."""
    bad = replace_kv_in_section(VALID_CONFIG, "magnetometer", "world_x", "east")
    cfg_path = write_cfg(tmp_path, bad)
    imu = MPU9250(cfg_path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_mag_range_rejects_invalid_type():
    """Setter must reject non-int / non-enum types for mag_range."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.mag_range = "16bits"
    with pytest.raises(TypeError):
        imu.mag_range = [2]


def test_mag_mode_rejects_invalid_type():
    """Setter must reject non-int / non-enum types for mag_mode."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.mag_mode = {"mode": 4}
    with pytest.raises(TypeError):
        imu.mag_mode = 3.14  # float not allowed


def test_mag_bias_rejects_invalid_type_and_shape():
    """Setter must accept only a list of three numeric values for mag_bias."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.mag_bias = "3.0,-1.5,0.5"
    with pytest.raises(TypeError):
        imu.mag_bias = [3.0, 0.0]
    with pytest.raises(TypeError):
        imu.mag_bias = [3.0, "x", 0.5]


def test_mag_noise_density_rejects_invalid_type_and_negative():
    """Setter must reject non-numeric types and negative values for mag_noise_density."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.mag_noise_density = "0.4"
    with pytest.raises(TypeError):
        imu.mag_noise_density = -0.01


def test_mag_world_rejects_invalid_type_and_shape():
    """Setter must accept only a list of three numeric values for mag_world."""
    imu = MPU9250()
    with pytest.raises(TypeError):
        imu.mag_world = "20,0,40"
    with pytest.raises(TypeError):
        imu.mag_world = [20.0, 0.0]
    with pytest.raises(TypeError):
        imu.mag_world = [20.0, None, 40.0]


def test_mag_mode_sets_expected_odr():
    """Setting mag_mode must update mag_odr_hz with the expected frequency."""
    imu = MPU9250()
    imu.mag_mode = MagnetometerMode.POWER_DOWN
    assert abs(imu.mag_odr_hz - 0.0) < 1e-12
    imu.mag_mode = MagnetometerMode.SINGLE
    assert abs(imu.mag_odr_hz - 0.0) < 1e-12
    imu.mag_mode = MagnetometerMode.CONT_8HZ
    assert abs(imu.mag_odr_hz - 8.0) < 1e-12
    imu.mag_mode = MagnetometerMode.CONT_100HZ
    assert abs(imu.mag_odr_hz - 100.0) < 1e-12