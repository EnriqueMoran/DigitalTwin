FROM python:3.11-slim

WORKDIR /app

COPY simulators/gps_sim/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY simulators ./simulators
RUN pip install --no-cache-dir -e .

ENV RUN_TESTS=0

CMD ["sh", "-c", "if [ \"$RUN_TESTS\" = \"1\" ]; then pytest -q simulators/gps_sim/tests -o cache_dir=/tmp/pytest_cache; else python -m simulators.gps_sim.app; fi"]