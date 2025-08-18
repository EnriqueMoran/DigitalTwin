FROM python:3.11-slim

WORKDIR /app

COPY simulators/imu_sim/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY simulators ./simulators
RUN pip install --no-cache-dir -e .

ENV RUN_TESTS=0

RUN apt-get update && apt-get install -y python3-tk && rm -rf /var/lib/apt/lists/*
ENV MPLBACKEND=TkAgg

CMD ["sh", "-c", "if [ \"$RUN_TESTS\" = \"1\" ]; then pytest -q simulators/imu_sim/tests -o cache_dir=/tmp/pytest_cache; else python -m simulators.imu_sim.app; fi"]