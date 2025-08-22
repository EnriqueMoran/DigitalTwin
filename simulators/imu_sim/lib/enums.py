from enum import Enum


class MagnetometerMode(Enum):
    POWER_DOWN = 1
    CONT_8HZ = 2
    CONT_100HZ = 4


class DLPF(Enum):
    BYPASS = 0
    ACTIVE = 1
