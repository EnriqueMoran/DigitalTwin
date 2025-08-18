import sys
import tempfile

from simulators.imu_sim.lib.imu import MPU9250
from simulators.imu_sim.lib.enums import (
    AccelerationRange, GyroscopeRange, MagnetometerRange, DLPF
)

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

def make_temp_config(content: str) -> str:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
    f.write(content.encode("utf-8"))
    f.flush()
    return f.name

def test_valid_config_loads_correctly():
    path = make_temp_config(VALID_CONFIG)
    imu = MPU9250(path)
    imu.read_config()

    assert imu.accel_range == AccelerationRange.ACCEL_RANGE_2G, "Invalid accel_range"
    assert imu.accel_dlpf == DLPF.ACTIVE, "Invalid accel_dlpf"
    assert imu.accel_bias == [0.01, -0.02, 0.03], "Invalid accel_bias"
    assert abs(imu.accel_noise_density - 0.0003) < 1e-12, "Invalid accel_noise_density"
    assert imu.accel_smplrt_div == 4, "Invalid accel_smplrt_div"


def test_invalid_accel_range_raises_value_error():
    bad = VALID_CONFIG.replace("range = 1", "range = 99", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    try:
        imu.read_config()
        raise AssertionError("Expected ValueError for invalid accelerometer range")
    except ValueError:
        pass

def test_invalid_accel_dlpf_raises_value_error():
    bad = VALID_CONFIG.replace("dlpf = 1", "dlpf = 5", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    try:
        imu.read_config()
        raise AssertionError("Expected ValueError for invalid DLPF value")
    except ValueError:
        pass

def test_invalid_bias_type_raises_value_error():
    bad = VALID_CONFIG.replace("bias_x = 0.01", "bias_x = text", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    try:
        imu.read_config()
        raise AssertionError("Expected ValueError while parsing bias_x as float")
    except ValueError:
        pass

def test_negative_sample_rate_div_raises_type_error():
    bad = VALID_CONFIG.replace("sample_rate_div = 4", "sample_rate_div = -3", 1)
    path = make_temp_config(bad)
    imu = MPU9250(path)
    try:
        imu.read_config()
        raise AssertionError("Expected TypeError for negative sample_rate_div")
    except TypeError:
        pass

def main():
    tests = [
        test_valid_config_loads_correctly,
        test_invalid_accel_range_raises_value_error,
        test_invalid_accel_dlpf_raises_value_error,
        test_invalid_bias_type_raises_value_error,
        test_negative_sample_rate_div_raises_type_error,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"[OK] {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"[FAIL] {t.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")

    if failures:
        print(f"\nCHECK: {failures} FAILURE(s).")
        sys.exit(1)
    else:
        print("\nCHECK: OK")
        sys.exit(0)

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
