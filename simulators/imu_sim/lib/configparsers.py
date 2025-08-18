import configparser

from pathlib import Path


class IMUParser:
    def __init__(self, filename="config.ini"):
        self.config = configparser.ConfigParser(inline_comment_prefixes=(';'))
        self.config.read(Path(filename))

    # Accelerometer
    def parse_accel_range(self):
        idx = self.config["accelerometer"].getint("range", fallback=1)
        return idx

    def parse_accel_dlpf(self):
        idx = self.config["accelerometer"].getint("dlpf", fallback=1)
        return idx

    def parse_accel_bias(self):
        bx = self.config["accelerometer"].getfloat("bias_x", fallback=0.0)
        by = self.config["accelerometer"].getfloat("bias_y", fallback=0.0)
        bz = self.config["accelerometer"].getfloat("bias_z", fallback=0.0)
        return [bx, by, bz]

    def parse_accel_noise_density(self):
        return self.config["accelerometer"].getfloat("noise_density", fallback=0.0003)

    def parse_accel_smplrt_div(self):
        return self.config["accelerometer"].getint("sample_rate_div", fallback=0)