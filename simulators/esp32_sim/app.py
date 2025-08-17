"""ESP32 telemetry multiplexer simulator placeholder."""

import os


def main() -> None:
    ground_host = os.getenv("GROUND_HOST", "ground")
    ground_port = int(os.getenv("GROUND_PORT", "9001"))
    print(
        f"ESP32 simulator forwarding telemetry to {ground_host}:{ground_port} (not implemented)"
    )


if __name__ == "__main__":
    main()
