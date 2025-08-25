FROM python:3.11-slim

WORKDIR /app

COPY simulators/radar_sim/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY simulators ./simulators
RUN pip install --no-cache-dir -e .

ENV RUN_TESTS=0
ENV RADAR_SIM_CONFIG=/app/simulators/radar_sim/config.json

CMD ["sh", "-c", "if [ \"$RUN_TESTS\" = \"1\" ]; then pytest -q simulators/radar_sim/tests -o cache_dir=/tmp/pytest_cache; else python -m simulators.radar_sim.app; fi"]
