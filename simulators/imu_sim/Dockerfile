FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# By default run the application. Set RUN_TESTS=1 to execute unit tests instead.
ENV RUN_TESTS=0
CMD ["sh", "-c", "if [ \"$RUN_TESTS\" = \"1\" ]; then pytest; else python app.py; fi"]
