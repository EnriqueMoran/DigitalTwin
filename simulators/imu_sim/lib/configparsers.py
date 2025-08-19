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
    

    # Gyroscope
    def parse_gyro_range(self):
        idx = self.config["gyroscope"].getint("range", fallback=1)
        return idx
    
    def parse_gyro_dlpf(self):
        idx = self.config["gyroscope"].getint("dlpf", fallback=1)
        return idx
    
    def parse_gyro_bias(self):
        bx = self.config["gyroscope"].getfloat("bias_x", fallback=0.0)
        by = self.config["gyroscope"].getfloat("bias_y", fallback=0.0)
        bz = self.config["gyroscope"].getfloat("bias_z", fallback=0.0)
        return [bx, by, bz]

    def parse_gyro_noise_density(self):
        return self.config["gyroscope"].getfloat("noise_density", fallback=0.01)

    def parse_gyro_smplrt_div(self):
        return self.config["gyroscope"].getint("sample_rate_div", fallback=0)
    

    # Magnetometer
    def parse_mag_range(self) -> int:
        return self.config["magnetometer"].getint("range", fallback=2)
    
    def parse_mag_mode(self) -> int:
        return self.config["magnetometer"].getint("mode", fallback=3)
    
    def parse_mag_bias(self) -> list[float]:
        m = self.config["magnetometer"]
        return [m.getfloat("bias_x", fallback=0.0),
                m.getfloat("bias_y", fallback=0.0),
                m.getfloat("bias_z", fallback=0.0)]

    def parse_mag_noise_density(self) -> float:
        return self.config["magnetometer"].getfloat("noise_density", fallback=0.4)

    def parse_mag_world(self) -> list[float]:
        m = self.config["magnetometer"]
        return [m.getfloat("world_x", fallback=20.0),
                m.getfloat("world_y", fallback=0.0),
                m.getfloat("world_z", fallback=40.0)]