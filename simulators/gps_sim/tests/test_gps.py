import math
import time
from pathlib import Path
from typing import Tuple

import numpy as np
import pytest

from simulators.gps_sim.lib.gps_sim import NEOM8N


VALID_CONFIG_NO_NOISE = """
[broker]
host = mosquitto
port = 1883

[gps]
baudrate = 9600
protocol = nmea
use_ublox_binary = false
update_rate_hz = 5
nav_rate_ms = 200
fix_type = 3
num_svs = 8
initial_lat = 31.000000
initial_lon = 118.000000
initial_alt = 5.0
pos_noise_m = 0.0
alt_noise_m = 0.0
vel_noise_m_s = 0.0
hdop = 0.9
nmea_sentences = GGA,RMC,VTG
nmea_term = \\r\\n
publish_rate_hz = 5
retain_messages = false
"""

VALID_CONFIG_WITH_NOISE = VALID_CONFIG_NO_NOISE.replace("pos_noise_m = 0.0", "pos_noise_m = 2.5") \
                                              .replace("alt_noise_m = 0.0", "alt_noise_m = 1.5") \
                                              .replace("vel_noise_m_s = 0.0", "vel_noise_m_s = 0.3")


def write_cfg(tmp_path: Path, content: str, name: str = "gps_config.ini") -> str:
    p = tmp_path / name
    p.write_text(content.strip() + "\n", encoding="utf-8")
    return str(p)


def static_motion_provider(t: float) -> Tuple[float, float, float, float, float, float]:
    """
    Returns a constant 'truth' position and kinematics. Signature:
    (lat_deg, lon_deg, alt_m, speed_knots, course_deg, climb_m_s)
    """
    return (31.0, 118.0, 5.0, 0.0, 0.0, 0.0)


def moving_motion_provider(t: float) -> Tuple[float, float, float, float, float, float]:
    """
    Simple linear motion: move north 1 m/s, keep lon same, climb 0.1 m/s.
    Convert small north displacement into lat offset approximately.
    """
    # approx 1 meter in latitude is ~1/111111 deg ≈ 9e-06 deg
    north_m = 1.0 * t
    lat = 31.0 + (north_m / 111111.0)
    lon = 118.0
    alt = 5.0 + 0.1 * t
    speed_knots = 1.94384  # 1 m/s ~ 1.94384 knots (approx)
    course_deg = 0.0
    climb_m_s = 0.1
    return (lat, lon, alt, speed_knots, course_deg, climb_m_s)


def _compute_nmea_checksum(sentence: str) -> str:
    """Compute XOR checksum for NMEA sentence body (between $ and *)."""
    assert sentence.startswith("$") and "*" in sentence
    body = sentence[1:sentence.index("*")]
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return f"{cs:02X}"


def test_read_config_and_init_and_sample_no_noise(tmp_path):
    cfg = write_cfg(tmp_path, VALID_CONFIG_NO_NOISE)
    gps = NEOM8N(cfg)
    # calling sample() before read_config/init should raise
    with pytest.raises(RuntimeError):
        gps.sample(0.0, static_motion_provider)

    gps.read_config()
    gps.init_sim(seed=123)

    # sample at t=0 using motion_provider -> measured should equal truth exactly (no noise)
    s = gps.sample(0.0, static_motion_provider)
    assert "meas" in s and "truth" in s

    meas = s["meas"]
    truth = s["truth"]

    # Because the config had zero noise, meas and truth positions should match (within tiny tol)
    assert abs(meas["lat"] - truth["lat"]) < 1e-12
    assert abs(meas["lon"] - truth["lon"]) < 1e-12
    assert abs(meas["alt"] - truth["alt"]) < 1e-12
    assert abs(meas["speed"] - truth["speed"]) < 1e-12
    # nmea present since protocol=nmea
    assert isinstance(s["nmea"], list)
    assert any("$GPGGA" in ns for ns in s["nmea"])
    assert any("$GPRMC" in ns for ns in s["nmea"])
    assert any("$GPVTG" in ns for ns in s["nmea"])


def test_simulate_counts_and_spacing(tmp_path):
    cfg = write_cfg(tmp_path, VALID_CONFIG_NO_NOISE)
    gps = NEOM8N(cfg)
    gps.read_config()
    gps.init_sim(seed=42)

    duration = 1.0
    out = gps.simulate(duration, motion_provider=static_motion_provider)

    fs = gps._update_rate_hz
    n_expected = math.floor(fs * duration) + 1

    assert "t" in out
    assert out["t"].shape[0] == n_expected

    # timestamps should be non-decreasing and evenly spaced
    t = out["t"]
    assert np.all(np.diff(t) >= -1e-15)
    if len(t) >= 2:
        assert np.allclose(np.diff(t), np.full(len(t)-1, 1.0 / fs), atol=1e-12)


def test_nmea_checksum_and_filtering(tmp_path):
    # use config with all sentences but assert checksum and filtering behavior
    cfg = write_cfg(tmp_path, VALID_CONFIG_NO_NOISE)
    gps = NEOM8N(cfg)
    gps.read_config()
    gps.init_sim(seed=1)

    s = gps.sample(0.0, static_motion_provider)
    nmea_list = s["nmea"]
    # compute and verify checksum for each sentence present
    for sentence in nmea_list:
        if "*" not in sentence:
            pytest.fail("NMEA sentence without checksum separator '*'")
        sent_cs = sentence.split("*")[1][:2]  # two hex digits after *
        calc_cs = _compute_nmea_checksum(sentence)
        assert sent_cs == calc_cs

    # Now restrict configured sentences to only GGA and ensure simulate respects it
    # mutate internal configured list to mimic config with single sentence
    gps._nmea_sentences = ["GGA"]
    s2 = gps.sample(0.0, static_motion_provider)
    nmea2 = s2["nmea"]
    # only GGA should be present
    assert all(sen[1:4] == "GPG" or sen[1:4] == "GGA" or sen[1:4] == "GPG" for sen in nmea2)
    # More robust: check that any RMC/VTG absent
    assert not any(sen.startswith("$GPRMC") for sen in nmea2)
    assert not any(sen.startswith("$GPVTG") for sen in nmea2)


def test_motion_provider_overrides_internal_truth(tmp_path):
    cfg = write_cfg(tmp_path, VALID_CONFIG_NO_NOISE)
    gps = NEOM8N(cfg)
    gps.read_config()
    gps.init_sim(seed=7)

    # sample with moving provider and zero noise -> meas should equal provider's truth
    ts = 0.5
    s = gps.sample(ts, moving_motion_provider)
    meas = s["meas"]
    truth = s["truth"]
    prov = moving_motion_provider(ts)
    # prov returns lat, lon, alt, speed_knots, course_deg, climb_m_s
    assert abs(meas["lat"] - prov[0]) < 1e-12
    assert abs(meas["lon"] - prov[1]) < 1e-12
    assert abs(meas["alt"] - prov[2]) < 1e-12


def test_noise_and_rng_determinism(tmp_path):
    # two instances with same seed and same config should produce identical noisy outputs
    cfg = write_cfg(tmp_path, VALID_CONFIG_WITH_NOISE)
    g1 = NEOM8N(cfg); g1.read_config(); g1.init_sim(seed=999)
    g2 = NEOM8N(cfg); g2.read_config(); g2.init_sim(seed=999)

    s1 = g1.sample(0.0, static_motion_provider)
    s2 = g2.sample(0.0, static_motion_provider)

    # with same seed, noise draws should be identical
    assert abs(s1["meas"]["lat"] - s2["meas"]["lat"]) < 1e-12
    assert abs(s1["meas"]["lon"] - s2["meas"]["lon"]) < 1e-12
    assert abs(s1["meas"]["alt"] - s2["meas"]["alt"]) < 1e-12

    # different seed -> values should differ in at least one field most of the time
    g3 = NEOM8N(cfg); g3.read_config(); g3.init_sim(seed=1000)
    s3 = g3.sample(0.0, static_motion_provider)
    # it's possible (very unlikely) noise draws match; use inequality check but allow rare flake
    assert not (abs(s1["meas"]["lat"] - s3["meas"]["lat"]) < 1e-12 and
                abs(s1["meas"]["lon"] - s3["meas"]["lon"]) < 1e-12 and
                abs(s1["meas"]["alt"] - s3["meas"]["alt"]) < 1e-12)


def test_sample_time_backward_error(tmp_path):
    cfg = write_cfg(tmp_path, VALID_CONFIG_NO_NOISE)
    gps = NEOM8N(cfg)
    gps.read_config()
    gps.init_sim(seed=1)

    # first sample at t=1.0, then call sample at t=0.5 -> should raise ValueError (time went backwards)
    gps.sample(1.0, static_motion_provider)
    with pytest.raises(ValueError):
        gps.sample(0.5, static_motion_provider)
