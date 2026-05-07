import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

MANGA_NAME = "One Piece"
MANGA_SLUG = "one-piece"

PAGE_URL = "https://3asq.org/manga/one-piece/"
AJAX_URL = "https://3asq.org/manga/one-piece/ajax/chapters/?t=1"

# The file will save in your current working directory
STATE_FILE = Path("seen_chapters.json")

# Ensure you set these in your environment variables or paste them directly here if running locally/privately
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") 
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,ar;q=0.8",
    "origin": "https://3asq.org",
    "referer": PAGE_URL,
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
    "x-requested-with": "XMLHttpRequest",
}


def clean_text(text):
    return re.sub(r"\s+", " ", text).strip()


def load_seen():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data)
    except Exception:
        return set()


def save_seen(chapter_ids):
    STATE_FILE.write_text(
        json.dumps(sorted(chapter_ids), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ WARNING: Telegram credentials missing. Skipping notification.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }

    response = requests.post(url, data=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def fetch_chapters():
    response = requests.post(
        AJAX_URL,
        headers=HEADERS,
        timeout=20
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    chapters = []

    for li in soup.select("li.wp-manga-chapter"):
        link = li.find("a", href=True)
        if not link:
            continue

        chapter_url = urljoin(PAGE_URL, link["href"])
        title = clean_text(link.get_text(" ", strip=True))

        chapter_id_match = re.search(
            rf"/manga/{re.escape(MANGA_SLUG)}/([^/]+)/?",
            chapter_url
        )
        chapter_id = chapter_id_match.group(1) if chapter_id_match else chapter_url

        date_tag = li.select_one(".chapter-release-date .timediff i")
        views_tag = li.select_one(".chapter-release-date .views")

        release_date = clean_text(date_tag.get_text(" ", strip=True)) if date_tag else "N/A"
        views = clean_text(views_tag.get_text(" ", strip=True)) if views_tag else "N/A"

        chapters.append({
            "id": chapter_id,
            "title": title,
            "url": chapter_url,
            "release_date": release_date,
            "views": views,
        })

    return chapters


def format_new_chapter_message(chapter):
    return (
        "🆕 New chapter added!\n\n"
        f"📚 Manga: {MANGA_NAME}\n"
        f"📖 Chapter: {chapter['title']}\n"
        f"📅 Date: {chapter['release_date']}\n"
        f"👁 Views: {chapter['views']}\n\n"
        f"🔗 {chapter['url']}"
    )


def format_startup_message(chapter_count, latest_chapter):
    return (
        "✅ Manga notifier initialized in Infinite Loop mode.\n\n"
        f"📚 Manga: {MANGA_NAME}\n"
        f"📌 Saved chapters: {chapter_count}\n"
        f"🔥 Latest: {latest_chapter['title']}\n\n"
        f"🔗 {latest_chapter['url']}\n\n"
        "Looping every 1 minute..."
    )


def check_routine():
    print(f"[{datetime.utcnow()} UTC] Fetching {MANGA_NAME} data...")
    chapters = fetch_chapters()

    if not chapters:
        print("No chapters found.")
        return

    current_ids = {chapter["id"] for chapter in chapters}
    seen_ids = load_seen()

    first_run = not STATE_FILE.exists()

    if first_run:
        save_seen(current_ids)
        latest_chapter = chapters[0]
        print("First run. Baseline saved.")
        print(f"Saved {len(current_ids)} chapters.")
        
        send_telegram_message(
            format_startup_message(
                chapter_count=len(current_ids),
                latest_chapter=latest_chapter
            )
        )
        return

    new_ids = current_ids - seen_ids

    if not new_ids:
        print(f"No new chapters. Latest: {chapters[0]['title']}")
        return

    new_chapters = [
        chapter for chapter in chapters
        if chapter["id"] in new_ids
    ]

    print(f"Found {len(new_chapters)} new chapter(s). Sending notifications...")

    for chapter in new_chapters:
        print(f"-> {chapter['title']}")
        send_telegram_message(format_new_chapter_message(chapter))

    save_seen(current_ids)


def run_infinite_loop(interval_minutes=1):
    print(f"🚀 Starting background scraper. Interval: {interval_minutes} minute(s).")
    print("Keep this script running to continue fetching.")
    print("-" * 50)
    
    interval_seconds = interval_minutes * 60
    
    while True:
        try:
            check_routine()
        except Exception as e:
            print(f"❌ Error encountered during check: {e}")
            traceback.print_exc()
            
        print(f"💤 Sleeping for {interval_minutes} minute(s)...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    # The loop is now set to 1 minute
    run_infinite_loop(interval_minutes=1)
