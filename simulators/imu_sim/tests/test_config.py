"""Tests for the IMU simulator configuration loader."""

import sys
from pathlib import Path
import tempfile
import textwrap

import pytest

try:
    ROOT = Path(__file__).resolve().parents[3]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
except IndexError:
    # Repository root not available (e.g., inside Docker image).
    pass

try:  # Import from repository package layout
    from simulators.imu_sim.lib.imu import MPU9250
    from simulators.imu_sim.lib.enums import AccelerationRange, DLPF
except ModuleNotFoundError:  # Fallback when running inside Docker image
    from lib.imu import MPU9250
    from lib.enums import AccelerationRange, DLPF


VALID_CONFIG = textwrap.dedent(
    """
    [accelerometer]
    range = 1
    dlpf = 1
    bias_x = 0.01
    bias_y = -0.02
    bias_z = 0.03
    noise_density = 0.0003
    sample_rate_div = 4
    """
)


def make_temp_config(content: str) -> str:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
    f.write(content.encode("utf-8"))
    f.flush()
    return f.name


def test_valid_config_loads_correctly() -> None:
    path = make_temp_config(VALID_CONFIG)
    imu = MPU9250(path)
    imu.read_config()

    assert imu.accel_range == AccelerationRange.ACCEL_RANGE_2G
    assert imu.accel_dlpf == DLPF.ACTIVE
    assert imu.accel_bias == [0.01, -0.02, 0.03]
    assert abs(imu.accel_noise_density - 0.0003) < 1e-12
    assert imu.accel_smplrt_div == 4


def test_invalid_accel_range_raises_value_error() -> None:
    bad = VALID_CONFIG.replace("range = 1", "range = 99", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_accel_dlpf_raises_value_error() -> None:
    bad = VALID_CONFIG.replace("dlpf = 1", "dlpf = 5", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_invalid_bias_type_raises_value_error() -> None:
    bad = VALID_CONFIG.replace("bias_x = 0.01", "bias_x = text", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    with pytest.raises(ValueError):
        imu.read_config()


def test_negative_sample_rate_div_raises_type_error() -> None:
    bad = VALID_CONFIG.replace("sample_rate_div = 4", "sample_rate_div = -3", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    with pytest.raises(TypeError):
        imu.read_config()
