import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Scenario file to run
SCENARIO_FILE = Path(__file__).resolve().parent.parent / "simulators" / "scenarios" / "sample.json"


def main() -> None:
    env = os.environ.copy()
    env["SCENARIO_FILE"] = str(SCENARIO_FILE.resolve())

    procs = [
        subprocess.Popen([sys.executable, "-m", "simulators.esp32_sim.app"], env=env),
        subprocess.Popen([sys.executable, "-m", "simulators.gps_sim.app"], env=env),
        subprocess.Popen([sys.executable, "-m", "simulators.imu_sim.app"], env=env),
    ]

    try:
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
        for p in procs:
            try:
                p.wait()
            except Exception:
                pass


if __name__ == "__main__":
    main()
