"""Enumerations used by the simplified IMU simulator."""

from __future__ import annotations

from enum import Enum


class AccelerometerRange(Enum):
    ACCEL_RANGE_2G = 1
    ACCEL_RANGE_4G = 2
    ACCEL_RANGE_8G = 4
    ACCEL_RANGE_16G = 8


class GyroscopeRange(Enum):
    GYRO_RANGE_250DPS = 1
    GYRO_RANGE_500DPS = 2
    GYRO_RANGE_1000DPS = 4
    GYRO_RANGE_2000DPS = 8


class MagnetometerRange(Enum):
    MAG_RANGE_14BITS = 1
    MAG_RANGE_16BITS = 2


class MagnetometerMode(Enum):
    POWER_DOWN = 1
    SINGLE = 2
    CONT_8HZ = 3
    CONT_100HZ = 4


class DLPF(Enum):
    BYPASS = 0
    ACTIVE = 1

