import json
import logging
import math
import os
import signal
import time
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

import paho.mqtt.client as mqtt

from simulators.scenarios.utils import WAVE_STATES, generate_states, load_scenario, iso_now

LOG = logging.getLogger("imu_sim.app")

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

    seq = 0
    prev_heading = None
    for t, _lat, _lon, heading, roll, pitch in generate_states(scenario["points"], wave_cfg):
        if stop:
            break
        amp = wave_cfg["amp"]
        freq = wave_cfg["freq"]
        roll_rate = 2 * math.pi * freq * amp * math.cos(2 * math.pi * freq * t)
        pitch_rate = -2 * math.pi * freq * amp * math.sin(2 * math.pi * freq * t)
        if prev_heading is None:
            yaw_rate = 0.0
        else:
            delta = ((heading - prev_heading + 180.0) % 360.0) - 180.0
            yaw_rate = delta
        prev_heading = heading
        payload = {
            "ax": 0.0,
            "ay": 0.0,
            "az": 1.0,
            "gx": roll_rate,
            "gy": pitch_rate,
            "gz": yaw_rate,
            "ts": iso_now(),
            "seq": seq,
        }
        client.publish("sim/imu", json.dumps(payload))
        seq += 1
        time.sleep(1.0)

    client.disconnect()


if __name__ == "__main__":
    main()
