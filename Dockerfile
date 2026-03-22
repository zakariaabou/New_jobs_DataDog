FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_datadog_site.py .
COPY seen_jobs2.json .

CMD ["python", "bot_datadog_site.py"]
