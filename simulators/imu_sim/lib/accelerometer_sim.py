from dataclasses import dataclass
import math
import numpy as np


LSB_PER_G = {2: 16384.0, 4: 8192.0, 8: 4096.0, 16: 2048.0}


@dataclass
class AccelSimConfig:
    range_g: int
    odr_hz: float
    bias_g: np.ndarray
    noise_density_g_sqrtHz: float
    use_lpf: bool
    lpf_cut_hz: float


class AccelSim:
    def __init__(self, cfg: AccelSimConfig, seed: int | None = None) -> None:
        self.cfg   = cfg
        self.state = np.zeros(3, dtype=float)
        self._rng  = np.random.default_rng(seed)

        # LPF coefficient (1st-order). If cutoff <= 0, LPF is disabled.
        if self.cfg.use_lpf and self.cfg.lpf_cut_hz > 0.0:
            dt = 1.0 / self.cfg.odr_hz
            self._alpha = math.exp(-2.0 * math.pi * self.cfg.lpf_cut_hz * dt)
        else:
            self._alpha = None

        # Warm-start flag: ensures the first output equals the first input
        self._primed = (self._alpha is None)

        # Standard deviation of discrete noise
        self._sigma = self._calc_sigma()


    def _calc_sigma(self) -> float:
        """
        Compute standard deviation of discrete-time noise based on noise density
        and equivalent noise bandwidth of either LPF or Nyquist.
        """
        if self._alpha is not None:
            bw_eq = (math.pi / 2.0) * self.cfg.lpf_cut_hz    # eq. bandwidth of 1st-order LPF
        else:
            bw_eq = 0.5 * self.cfg.odr_hz                    # Nyquist bandwidth
        bw_eq = max(bw_eq, 1e-9)
        return self.cfg.noise_density_g_sqrtHz * math.sqrt(bw_eq)


    def ready(self, dt: float) -> bool:
        return True


    def step(self, a_lin_world_ms2: np.ndarray, R_world_to_sensor: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute one accelerometer sample.

        Args:
            a_lin_world_ms2: linear acceleration (m/s², excluding gravity) in world frame.
            R_world_to_sensor: 3x3 rotation matrix (world → sensor).

        Returns:
            counts_int16[3]: quantized sensor counts.
            a_meas_g[3]: simulated measurement in g.
        """
        g = 9.80665
        # Transform acceleration into sensor frame
        a_lin_s = R_world_to_sensor @ a_lin_world_ms2
        g_s = R_world_to_sensor @ np.array([0.0, 0.0, +g])    # Earth gravity (ENU Z up)
        a_true_g = (a_lin_s + g_s) / g

        # Apply static bias
        a_biased = a_true_g + self.cfg.bias_g

        # Apply optional LPF
        if self._alpha is not None:
            self.state = self._alpha * self.state + (1.0 - self._alpha) * a_biased
            a_f = self.state
        else:
            a_f = a_biased
        
        if self._alpha is not None:
            if not self._primed:
                # Prime the filter so the first output equals the first input
                self.state[:] = a_biased
                self._primed = True
            else:
                # Standard 1st-order low-pass: y[n] = α*y[n-1] + (1-α)*x[n]
                self.state = self._alpha * self.state + (1.0 - self._alpha) * a_biased
            a_f = self.state
        else:
            a_f = a_biased
        
        # Add white Gaussian noise
        noise = self._rng.normal(0.0, self._sigma, size=3)
        a_noisy = a_f + noise

        # Clip to sensor range
        rng = self.cfg.range_g
        a_clip = np.clip(a_noisy, -rng, +rng)

        # Quantize to 16-bit integer counts
        lsb = LSB_PER_G[rng]
        counts = np.rint(a_clip * lsb).astype(np.int32)
        counts = np.clip(counts, -32768, 32767).astype(np.int16)
        return counts, a_clip.astype(float)


    @classmethod
    def from_config(cls, 
                    range_g: int, 
                    odr_hz: float, 
                    bias_g: list[float],
                    noise_density_g_sqrtHz: float, 
                    use_lpf: bool, 
                    lpf_cut_hz: float,
                    seed: int | None = None) -> "AccelSim":
        """Factory method to build an AccelSim from configuration parameters."""
        cfg = AccelSimConfig(
                range_g=range_g,
                odr_hz=odr_hz,
                bias_g=np.array(bias_g, dtype=float),
                noise_density_g_sqrtHz=float(noise_density_g_sqrtHz),
                use_lpf=use_lpf,
                lpf_cut_hz=float(lpf_cut_hz),
            )
        return cls(cfg, seed=seed)
