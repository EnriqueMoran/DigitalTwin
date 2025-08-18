"""Minimal MPU9250 configuration reader used by the tests."""

from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass

from .enums import AccelerationRange, DLPF


@dataclass
class MPU9250:
    """Tiny representation of an MPU9250 IMU.

    Only the configuration fields required by the tests are implemented.
    """

    config_path: str
    accel_range: AccelerationRange | None = None
    accel_dlpf: DLPF | None = None
    accel_bias: list[float] | None = None
    accel_noise_density: float | None = None
    accel_smplrt_div: int | None = None

    def read_config(self) -> None:
        """Parse the INI configuration file.

        Raises:
            ValueError: if enumerated values are out of range or bias values
                cannot be parsed.
            TypeError: if ``sample_rate_div`` is negative.
        """

        parser = ConfigParser()
        if not parser.read(self.config_path):
            raise FileNotFoundError(self.config_path)

        acc = parser["accelerometer"]

        range_val = acc.getint("range")
        try:
            self.accel_range = AccelerationRange(range_val)
        except ValueError as exc:
            raise ValueError("Invalid accelerometer range") from exc

        dlpf_val = acc.getint("dlpf")
        try:
            self.accel_dlpf = DLPF(dlpf_val)
        except ValueError as exc:
            raise ValueError("Invalid accelerometer DLPF value") from exc

        try:
            self.accel_bias = [
                acc.getfloat("bias_x"),
                acc.getfloat("bias_y"),
                acc.getfloat("bias_z"),
            ]
        except ValueError as exc:
            raise ValueError("Invalid accelerometer bias") from exc

        self.accel_noise_density = acc.getfloat("noise_density")

        srd = acc.getint("sample_rate_div")
        if srd < 0:
            raise TypeError("sample_rate_div must be non-negative")
        self.accel_smplrt_div = srd
