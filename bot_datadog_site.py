import requests
import json
import os
import schedule
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

BOT_TOKEN       = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID         = os.environ["TELEGRAM_CHAT_ID"]
CHAT_ID2        = os.environ["TELEGRAM_CHAT_ID2"]
UPSTASH_URL     = os.environ["UPSTASH_REDIS_REST_URL"]
UPSTASH_TOKEN   = os.environ["UPSTASH_REDIS_REST_TOKEN"]
REDIS_KEY       = "datadog:seen_jobs"

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/datadog/jobs"

# ── Minimal health check server (keeps Koyeb happy) ──────────────────────────
 
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
 
    def log_message(self, format, *args):
        pass  # silence request logs
 
def start_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health check server running on port {port}")
 
 
# ── Upstash Redis ─────────────────────────────────────────────────────────────

def load_seen_jobs():
    """Load seen jobs list from Upstash Redis (replaces reading seen_jobs2.json)."""
    try:
        resp = requests.get(
            f"{UPSTASH_URL}/GET/{REDIS_KEY}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            timeout=10,
        )
        resp.raise_for_status()
        result = resp.json().get("result")
        if result:
            return json.loads(result)
    except Exception as e:
        print(f"Error loading seen jobs from Redis: {e}")
    return []


def save_seen_jobs(jobs):
    """Save seen jobs list to Upstash Redis. Uses POST with body to avoid URL length limits."""
    try:
        # Convert tuples to lists for JSON, ensure all items are serializable
        serializable = [list(j) for j in jobs]
        payload = json.dumps(serializable)
        resp = requests.post(
            f"{UPSTASH_URL}/SET/{REDIS_KEY}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            data=payload,
            timeout=30,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"Error saving seen jobs to Redis: {e}")


def fetch_jobs():
    resp = requests.get(GREENHOUSE_API, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    jobs = {}
    for job in data.get("jobs", []):
        jobs[(job["title"], job["location"]["name"])] = {
            "url": job["absolute_url"]
        }
    return jobs


def send_telegram(text, max_retries=3):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    payload2 = {
        "chat_id": CHAT_ID2,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            resp2 = requests.post(url, json=payload2, timeout=30)
            resp2.raise_for_status()
            return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
            else:
                print(f"  Failed to send Telegram after {max_retries} attempts: {e}")
                return False


def check_jobs():
    print("Checking Datadog jobs...")
    try:
        current_jobs = fetch_jobs()
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        return

    seen = load_seen_jobs()
    new_jobs = [(title, location) for title, location in current_jobs.keys() if [title, location] not in seen]

    for title, location in new_jobs:
        url = current_jobs[(title, location)]["url"]
        message = f"<b>{title}</b>\n\n{location}\n\n<a href='{url}'>View listing</a>"
        if send_telegram(message):
            print(f"Notified: {title} {location}")
        time.sleep(1)  # Avoid Telegram rate limiting

    if new_jobs:
        save_seen_jobs(seen + new_jobs)
    else:
        print("No new jobs found.")


# Run immediately, then every 30 minutes
check_jobs()
schedule.every(30).minutes.do(check_jobs)

while True:
    schedule.run_pending()
    time.sleep(60)