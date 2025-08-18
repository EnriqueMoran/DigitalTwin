"""GPS simulator placeholder."""

import os


def main() -> None:
    host = os.getenv("HOST", "esp32_sim")
    port = int(os.getenv("PORT", "9000"))
    print(f"IMU simulator sending to {host}:{port} (not implemented)")


if __name__ == "__main__":
    main()
