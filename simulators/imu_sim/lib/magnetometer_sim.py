from dataclasses import dataclass
import math
import numpy as np

# AK8963 typical sensitivities (µT per LSB):
#  - 14-bit: ≈ 0.6 µT/LSB  -> counts per µT ≈ 1.6666667
#  - 16-bit: ≈ 0.15 µT/LSB -> counts per µT ≈ 6.6666667
COUNTS_PER_UT = {
    14: 1.0 / 0.6,
    16: 1.0 / 0.15,
}

@dataclass
class MagSimConfig:
    range_bits: int
    odr_hz: float
    bias_uT: np.ndarray
    noise_density_uT_sqrtHz: float
    world_field_uT: np.ndarray
    use_lpf: bool
    lpf_cut_hz: float


class MagSim:
    def __init__(self, cfg: MagSimConfig, seed: int | None = None) -> None:
        self.cfg   = cfg
        self.state = np.zeros(3, dtype=float)
        self._rng  = np.random.default_rng(seed)

        # LPF coefficient (1st-order). If cutoff <= 0, LPF is disabled.
        if self.cfg.use_lpf and self.cfg.lpf_cut_hz > 0.0:
            dt = 1.0 / max(self.cfg.odr_hz, 1e-9)
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
            bw_eq = (math.pi / 2.0) * self.cfg.lpf_cut_hz   # eq. bandwidth of 1st-order LPF
        else:
            bw_eq = 0.5 * self.cfg.odr_hz                   # Nyquist bandwidth
        bw_eq = max(bw_eq, 1e-9)
        return self.cfg.noise_density_uT_sqrtHz * math.sqrt(bw_eq)


    def ready(self, dt: float) -> bool:
        return True


    def step(self, R_world_to_sensor: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Compute one magnetometer sample.

        Args:
            R_world_to_sensor: 3x3 rotation matrix (world → sensor).

        Returns:
            counts_int16[3]: quantized sensor counts.
            B_meas_uT[3]: simulated measurement in µT (sensor frame).
        """
        # Rotate world magnetic field into sensor frame
        B_true_s = R_world_to_sensor @ self.cfg.world_field_uT

        # Apply static hard-iron bias
        B_biased = B_true_s + self.cfg.bias_uT

        # Optional LPF
        if self._alpha is not None:
            if not self._primed:
                self.state[:] = B_biased
                self._primed = True
            else:
                self.state = self._alpha * self.state + (1.0 - self._alpha) * B_biased
            B_f = self.state
        else:
            B_f = B_biased

        # Add white Gaussian noise
        noise = self._rng.normal(0.0, self._sigma, size=3)
        B_noisy = B_f + noise

        # Quantize to counts (int16), using bit-dependent sensitivity
        cps = COUNTS_PER_UT[int(self.cfg.range_bits)]
        counts = np.rint(B_noisy * cps).astype(np.int32)
        counts = np.clip(counts, -32768, 32767).astype(np.int16)

        return counts, B_noisy.astype(float)


    @classmethod
    def from_config(cls,
                    range_bits: int,
                    odr_hz: float,
                    bias_uT: list[float],
                    noise_density_uT_sqrtHz: float,
                    world_field_uT: list[float],
                    use_lpf: bool,
                    lpf_cut_hz: float,
                    seed: int | None = None) -> "MagSim":
        """Factory method to build a MagSim from configuration parameters."""
        cfg = MagSimConfig(
            range_bits=int(range_bits),
            odr_hz=float(odr_hz),
            bias_uT=np.array(bias_uT, dtype=float),
            noise_density_uT_sqrtHz=float(noise_density_uT_sqrtHz),
            world_field_uT=np.array(world_field_uT, dtype=float),
            use_lpf=bool(use_lpf),
            lpf_cut_hz=float(lpf_cut_hz),
        )
        return cls(cfg, seed=seed)
