from enum import Enum


class AccelerometerRange(Enum):
    ACCEL_RANGE_2G  = 1
    ACCEL_RANGE_4G  = 2
    ACCEL_RANGE_8G  = 3
    ACCEL_RANGE_16G = 4

    def to_g(self) -> int:
        return {1: 2, 2: 4, 3: 8, 4: 16}[self.value]
    

class GyroscopeRange(Enum):
    GYRO_RANGE_250DPS  = 1
    GYRO_RANGE_500DPS  = 2
    GYRO_RANGE_1000DPS = 3
    GYRO_RANGE_2000DPS = 4

    def to_dps(self) -> int:
        return {1: 250, 2: 500, 3: 1000, 4: 2000}[self.value]


class MagnetometerRange(Enum):
    MAG_RANGE_14BITS = 1
    MAG_RANGE_16BITS = 2

    def to_bits(self) -> int:
        return {1: 14, 2: 16}[self.value]


class MagnetometerMode(Enum):
    POWER_DOWN = 1
    SINGLE     = 2
    CONT_8HZ   = 3
    CONT_100HZ = 4

    def to_hz(self) -> int:
        return {1:0.0, 2:0.0, 3:8.0, 4:100.0}[self.value]


class DLPF(Enum):
    ACTIVE = 1
    BYPASS = 2