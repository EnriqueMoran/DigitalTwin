import pytest
import re
from pathlib import Path

from simulators.gps_sim.lib.gps_sim import NEOM8N


VALID_CONFIG = """
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
pos_noise_m = 2.5
alt_noise_m = 1.5
vel_noise_m_s = 0.3
hdop = 0.9
nmea_sentences = GGA,RMC,VTG
nmea_term = \\r\\n
publish_rate_hz = 5
retain_messages = false
"""

def write_cfg(tmp_path: Path, content: str, name: str = "gps_config.ini") -> str:
    p = tmp_path / name
    # ensure file ends with newline like your other tests
    p.write_text(content.strip() + "\n", encoding="utf-8")
    return str(p)


def replace_kv_in_section(ini_text: str, section: str, key: str, new_value: str) -> str:
    """
    Replace (or append) a key/value pair inside a named section in the INI text.
    Preserves formatting of the rest of the file.
    """
    pattern_section = rf"(?ms)^\[{re.escape(section)}\]\s*(.*?)(?=^\[|\Z)"
    m = re.search(pattern_section, ini_text)
    if not m:
        return ini_text
    body = m.group(1)

    pattern_kv = rf"(?m)^(\s*{re.escape(key)}\s*=\s*).*$"

    def _repl(match: re.Match) -> str:
        return f"{match.group(1)}{new_value}"

    new_body, n = re.subn(pattern_kv, _repl, body, count=1)
    if n == 0:
        # key not present -> append inside section body
        if not body.endswith("\n"):
            body += "\n"
        new_body = body + f"{key} = {new_value}\n"

    start, end = m.span(1)
    return ini_text[:start] + new_body + ini_text[end:]


def test_read_config_populates_properties(tmp_path):
    cfg_path = write_cfg(tmp_path, VALID_CONFIG)
    gps = NEOM8N(cfg_path)
    gps.read_config()

    # transport / formatting
    assert gps.baudrate == 9600
    assert gps.protocol == "nmea"
    assert gps.use_ublox_binary is False

    # timing / rates
    assert abs(gps.update_rate_hz - 5.0) < 1e-12
    assert gps.nav_rate_ms == 200

    # fix / sats
    assert gps.fix_type == 3
    assert gps.num_svs == 8

    # initial position — updated to check the individual fields that match the INI
    assert abs(gps.initial_lat - 31.0) < 1e-9
    assert abs(gps.initial_lon - 118.0) < 1e-9
    assert abs(gps.initial_alt - 5.0) < 1e-9

    # noise & publishing
    assert abs(gps.pos_noise_m - 2.5) < 1e-12
    assert abs(gps.alt_noise_m - 1.5) < 1e-12
    assert abs(gps.vel_noise_m_s - 0.3) < 1e-12
    assert abs(gps.hdop - 0.9) < 1e-12

    # nmea & publishing behaviour
    assert gps.nmea_sentences == ["GGA", "RMC", "VTG"]
    # nmea_term should have been decoded to actual CRLF characters
    assert gps.nmea_term == "\r\n"
    assert abs(gps.publish_rate_hz - 5.0) < 1e-12
    assert gps.retain_messages is False


def test_read_config_missing_gps_section_uses_defaults(tmp_path):
    minimal = """
[broker]
host = example
"""
    cfg_path = write_cfg(tmp_path, minimal, name="gps_min.ini")
    gps = NEOM8N(cfg_path)
    # read_config should not raise even if gps section is missing; defaults applied via parser
    gps.read_config()

    # defaults inferred from our parser/common sense (fallbacks)
    assert isinstance(gps.baudrate, int)
    assert gps.protocol in ("nmea", "ubx")  # parser fallback uses 'nmea' in our design
    assert gps.update_rate_hz > 0.0
    assert gps.publish_rate_hz > 0.0


def test_invalid_latitude_in_config_raises(tmp_path):
    bad = replace_kv_in_section(VALID_CONFIG, "gps", "initial_lat", "999.0")
    cfg_path = write_cfg(tmp_path, bad)
    gps = NEOM8N(cfg_path)
    # setting out-of-range latitude via read_config should raise ValueError from setter
    with pytest.raises(ValueError):
        gps.read_config()


def test_invalid_longitude_in_config_raises(tmp_path):
    bad = replace_kv_in_section(VALID_CONFIG, "gps", "initial_lon", "-999.0")
    cfg_path = write_cfg(tmp_path, bad)
    gps = NEOM8N(cfg_path)
    with pytest.raises(ValueError):
        gps.read_config()


def test_invalid_update_rate_in_config_raises(tmp_path):
    bad = replace_kv_in_section(VALID_CONFIG, "gps", "update_rate_hz", "0")
    cfg_path = write_cfg(tmp_path, bad)
    gps = NEOM8N(cfg_path)
    with pytest.raises(TypeError):
        gps.read_config()


def test_invalid_protocol_value_raises(tmp_path):
    bad = replace_kv_in_section(VALID_CONFIG, "gps", "protocol", "txt")
    cfg_path = write_cfg(tmp_path, bad)
    gps = NEOM8N(cfg_path)
    # protocol setter should reject unknown protocol values
    with pytest.raises(ValueError):
        gps.read_config()


def test_nmea_sentences_setter_rejects_invalid_type():
    gps = NEOM8N()
    with pytest.raises(TypeError):
        gps.nmea_sentences = "GGA,RMC"   # must be list/tuple of strings
    with pytest.raises(ValueError):
        gps.nmea_sentences = []          # must contain at least one sentence


def test_nmea_term_setter_allows_escaped_sequences():
    gps = NEOM8N()
    gps.nmea_term = "\\r\\n"
    assert gps.nmea_term == "\r\n"
    # also accept already-decoded string
    gps.nmea_term = "\r\n"
    assert gps.nmea_term == "\r\n"


def test_setters_type_and_value_checks():
    gps = NEOM8N()

    with pytest.raises(TypeError):
        gps.baudrate = "9600"
    with pytest.raises(TypeError):
        gps.baudrate = -1

    with pytest.raises(TypeError):
        gps.use_ublox_binary = "false"

    with pytest.raises(TypeError):
        gps.update_rate_hz = "5"
    with pytest.raises(TypeError):
        gps.update_rate_hz = 0

    with pytest.raises(TypeError):
        gps.nav_rate_ms = "200"
    with pytest.raises(TypeError):
        gps.nav_rate_ms = -10

    with pytest.raises(ValueError):
        gps.fix_type = 99

    with pytest.raises(ValueError):
        gps.num_svs = 1000

    with pytest.raises(TypeError):
        gps.initial_position = "31,118,5"
    with pytest.raises(TypeError):
        gps.initial_position = (31.0, 118.0)  # only two elements

    with pytest.raises(TypeError):
        gps.pos_noise_m = "2.5"
    with pytest.raises(TypeError):
        gps.alt_noise_m = -1.0

    with pytest.raises(TypeError):
        gps.hdop = "0.9"
    with pytest.raises(TypeError):
        gps.hdop = 0.0


def test_publish_rate_and_retain_setters():
    gps = NEOM8N()
    with pytest.raises(TypeError):
        gps.publish_rate_hz = "5"
    with pytest.raises(TypeError):
        gps.publish_rate_hz = 0
    gps.publish_rate_hz = 2.0
    assert abs(gps.publish_rate_hz - 2.0) < 1e-12

    with pytest.raises(TypeError):
        gps.retain_messages = "false"
    gps.retain_messages = True
    assert gps.retain_messages is True
