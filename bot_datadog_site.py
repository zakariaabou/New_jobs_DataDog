import requests
import json
import os
import schedule
import time

BOT_TOKEN = "8630469178:AAFRKkXcYzfXDl9ADiglScXrDTShsPcd6So"
CHAT_ID   = "6391797266"
CHAT_ID2  = "7543871208"
JOBS_FILE = "seen_jobs2.json"
CAREERS_URL = "https://careers.datadoghq.com/all-jobs/"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/datadog/jobs"

def load_seen_jobs():
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE) as f:
                data = json.load(f)
                return data
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}

def save_seen_jobs(jobs):
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f)

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
            resp2 = requests.post(url, json=payload2, timeout=30)
            resp.raise_for_status()
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
        message = f"{title}\n\n{location}\n\n<a href='{url}'>View listing</a>"
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