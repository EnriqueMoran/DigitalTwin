from enum import Enum


class AccelerationRange(Enum):
    """Selectable range for the accelerometer."""

    ACCEL_RANGE_2G = 1
    ACCEL_RANGE_4G = 2
    ACCEL_RANGE_8G = 3
    ACCEL_RANGE_16G = 4


class GyroscopeRange(Enum):
    """Selectable range for the gyroscope."""

    GYRO_RANGE_250DPS = 1
    GYRO_RANGE_500DPS = 2
    GYRO_RANGE_1000DPS = 3
    GYRO_RANGE_2000DPS = 4


class MagnetometerRange(Enum):
    """Selectable range for the magnetometer."""

    MAG_RANGE_14BITS = 1
    MAG_RANGE_16BITS = 2


class DLPF(Enum):
    """Digital Low Pass Filter configuration."""

    ACTIVE = 1
    BYPASS = 2
