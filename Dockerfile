FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot_datadog_site.py .

CMD ["python", "bot_datadog_site.py"]
