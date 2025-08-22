FROM python:3.11-slim

WORKDIR /app

COPY simulators/battery_sim/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml . 
COPY simulators ./simulators
RUN pip install --no-cache-dir -e .

ENV RUN_TESTS=0

CMD ["sh", "-c", "if [ \"$RUN_TESTS\" = \"1\" ]; then pytest -q simulators/battery_sim/tests -o cache_dir=/tmp/pytest_cache; else python -m simulators.battery_sim.app; fi"]
