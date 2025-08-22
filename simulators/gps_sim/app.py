import json
import logging
import os
import signal
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

import paho.mqtt.client as mqtt

from simulators.scenarios.utils import WAVE_STATES, generate_states, load_scenario, iso_now

LOG = logging.getLogger("gps_sim.app")

# Scenario to load for simulation (overridable via SCENARIO_FILE env var)
SCENARIO_FILE = Path(
    os.getenv(
        "SCENARIO_FILE",
        Path(__file__).resolve().parent.parent / "scenarios" / "sample.json",
    )
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    scenario = load_scenario(SCENARIO_FILE)
    wave_cfg = WAVE_STATES.get(scenario.get("wave_state", "calm"), WAVE_STATES["calm"])

    client = mqtt.Client()
    client.connect("mosquitto", 1883, 60)

    stop = False

    def _sig(sig, frame):
        nonlocal stop
        LOG.info("Signal %s received, shutting down", sig)
        stop = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    for _t, lat, lon, _heading, _roll, _pitch in generate_states(scenario["points"], wave_cfg):
        if stop:
            break
        payload = {"lat": lat, "lon": lon, "ts": iso_now()}
        client.publish("sim/gps", json.dumps(payload))
        time.sleep(1.0)

    client.disconnect()


if __name__ == "__main__":
    main()
