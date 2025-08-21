import logging
import os
import signal
import sys

from simulators.gps_sim.lib.mqtt_bridge import GPSPublisher

LOG = logging.getLogger("gps_sim.app")


def _get_log_level() -> int:
    lvl = os.getenv("LOGLEVEL", "")
    if lvl:
        try:
            return getattr(logging, lvl.upper())
        except Exception:
            pass
    debug = os.getenv("DEBUG", "0").lower()
    if debug in ("1", "true", "yes", "on"):
        return logging.DEBUG
    return logging.INFO


def main():
    logging.basicConfig(level=_get_log_level(), format="%(asctime)s %(levelname)s %(message)s")

    cfg = os.getenv("GPS_CONFIG", "./simulators/gps_sim/config.ini")
    bridge = GPSPublisher(cfg)

    try:
        bridge.read_and_init_gps()
    except Exception as e:
        LOG.error("Failed to init GPS from %s: %s", cfg, e)
        sys.exit(2)

    def _sig(sig, frame):
        LOG.info("Signal %s received, shutting down", sig)
        try:
            bridge.stop()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    bridge.start()


if __name__ == "__main__":
    main()
