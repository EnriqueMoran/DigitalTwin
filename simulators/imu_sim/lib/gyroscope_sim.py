from dataclasses import dataclass
import math
import numpy as np


LSB_PER_DPS = {250: 131.0, 500: 65.5, 1000: 32.8, 2000: 16.4}


@dataclass
class GyroSimConfig:
    range_dps: int
    odr_hz: float
    bias_dps: np.ndarray
    noise_density_dps_sqrtHz: float
    use_lpf: bool
    lpf_cut_hz: float


class GyroSim:
    def __init__(self, cfg: GyroSimConfig, seed: int | None = None) -> None:
        self.cfg   = cfg
        self.state = np.zeros(3, dtype=float)
        self._rng  = np.random.default_rng(seed)

        # Compute LPF coefficient (1st-order). If cutoff <= 0, LPF is disabled.
        if self.cfg.use_lpf and self.cfg.lpf_cut_hz > 0.0:
            dt = 1.0 / self.cfg.odr_hz
            self._alpha = math.exp(-2.0 * math.pi * self.cfg.lpf_cut_hz * dt)
        else:
            self._alpha = None

        # Warm-start flag: first output equals the first input
        self._primed = (self._alpha is None)

        # Standard deviation of discrete noise
        self._sigma = self._calc_sigma()


    def _calc_sigma(self) -> float:
        """
        Compute standard deviation of discrete-time noise based on noise density
        and equivalent noise bandwidth of either LPF or Nyquist.
        """
        if self._alpha is not None:
            bw_eq = (math.pi / 2.0) * self.cfg.lpf_cut_hz   # eq. bandwidth of 1st-order LPF
        else:
            bw_eq = 0.5 * self.cfg.odr_hz                   # Nyquist bandwidth
        bw_eq = max(bw_eq, 1e-9)
        return self.cfg.noise_density_dps_sqrtHz * math.sqrt(bw_eq)


    def ready(self, dt: float) -> bool:
        return True


    def step(self, omega_world_dps: np.ndarray, R_world_to_sensor: np.ndarray
             ) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute one gyroscope sample.

        Args:
            omega_world_dps: angular velocity (°/s) in world frame.
            R_world_to_sensor: 3x3 rotation matrix (world → sensor).

        Returns:
            counts_int16[3]: quantized sensor counts.
            omega_meas_dps[3]: simulated measurement in °/s.
        """
        # Transform angular velocity into sensor frame
        omega_s = R_world_to_sensor @ omega_world_dps

        # Apply static bias
        omega_biased = omega_s + self.cfg.bias_dps

        # Apply optional LPF
        if self._alpha is not None:
            if not self._primed:
                self.state[:] = omega_biased
                self._primed = True
            else:
                self.state = self._alpha * self.state + (1.0 - self._alpha) * omega_biased
            w_f = self.state
        else:
            w_f = omega_biased

        # Add white Gaussian noise
        noise = self._rng.normal(0.0, self._sigma, size=3)
        w_noisy = w_f + noise

        # Clip to sensor range
        rng = int(self.cfg.range_dps)
        w_clip = np.clip(w_noisy, -rng, +rng)

        # Quantize to 16-bit integer counts
        lsb = LSB_PER_DPS[rng]
        counts = np.rint(w_clip * lsb).astype(np.int32)
        counts = np.clip(counts, -32768, 32767).astype(np.int16)

        return counts, w_clip.astype(float)


    @classmethod
    def from_config(cls, 
                    range_dps: int, 
                    odr_hz: float, 
                    bias_dps: list[float],
                    noise_density_dps_sqrtHz: float, 
                    use_lpf: bool, 
                    lpf_cut_hz: float,
                    seed: int | None = None) -> "GyroSim":
        """Factory method to build a GyroSim from configuration parameters."""
        cfg = GyroSimConfig(
            range_dps=int(range_dps),
            odr_hz=float(odr_hz),
            bias_dps=np.array(bias_dps, dtype=float),
            noise_density_dps_sqrtHz=float(noise_density_dps_sqrtHz),
            use_lpf=bool(use_lpf),
            lpf_cut_hz=float(lpf_cut_hz),
        )
        return cls(cfg, seed=seed)
