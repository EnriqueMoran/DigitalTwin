import logging
import os
import signal
import sys

from simulators.esp32_sim.lib.esp32_sim import ESP32, LOG as _LOG

LOG = logging.getLogger("esp32_sim.app")


def _get_log_level() -> int:
    """
    Decide logging level:
    - If LOGLEVEL env var is set, use it (DEBUG/INFO/WARNING/ERROR).
    - Else if DEBUG env var is truthy use DEBUG.
    - Otherwise INFO.
    """
    lvl = os.getenv("LOGLEVEL")
    if lvl:
        try:
            return getattr(logging, lvl.upper())
        except Exception:
            pass
    debug = os.getenv("DEBUG", "0").lower()
    if debug == "1":
        return logging.DEBUG
    return logging.INFO


def main():
    # logging: DEBUG if env var SET, else INFO
    logging.basicConfig(level=_get_log_level(), format="%(asctime)s %(levelname)s %(message)s")
    cfg = "./simulators/esp32_sim/config.ini"
    sim = ESP32(cfg)

    try:
        sim.read_config()
    except Exception as e:
        LOG.error("Failed to load config from %s: %s", cfg, e)
        sys.exit(2)


    def _sig(sig, frame):
        LOG.info("Signal %s received, shutting down", sig)
        try:
            sim.stop()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    sim.start()

if __name__ == "__main__":
    main()
