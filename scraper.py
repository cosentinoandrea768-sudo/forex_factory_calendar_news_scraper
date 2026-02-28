import os
import time
import requests
from datetime import datetime
from flask import Flask
from bs4 import BeautifulSoup
import pandas as pd
from config import ALLOWED_ELEMENT_TYPES, ICON_COLOR_MAP
from utils import save_csv
import config
import threading

app = Flask(__name__)

# --- Telegram ---
def send_telegram_message(message: str):
    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not bot_token or not chat_id:
        print("[WARNING] BOT_TOKEN or CHAT_ID not set.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        requests.post(url, json=payload, timeout=10)
        print("[INFO] Startup message sent to Telegram.")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")


# --- Scraper senza Selenium ---
def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text


def parse_table_html(html, month, year):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="calendar__table")
    if not table:
        print(f"[WARNING] Table not found for {month} {year}")
        return [], month

    data = []

    for row in table.find_all("tr"):
        row_data = {}
        event_id = row.get("data-event-id")

        for element in row.find_all("td"):
            class_name = element.get("class")
            if not class_name:
                continue
            class_name = " ".join(class_name)

            if class_name in ALLOWED_ELEMENT_TYPES:
                class_name_key = ALLOWED_ELEMENT_TYPES.get(class_name, "cell")

                if "calendar__impact" in class_name:
                    span = element.find("span")
                    color = ICON_COLOR_MAP.get(span["class"][0]) if span else "impact"
                    row_data[class_name_key] = color

                elif "calendar__detail" in class_name and event_id:
                    detail_url = f"https://www.forexfactory.com/calendar?month={month}#detail={event_id}"
                    row_data[class_name_key] = detail_url

                elif element.text.strip():
                    row_data[class_name_key] = element.text.strip()
                else:
                    row_data[class_name_key] = "empty"

        if row_data:
            data.append(row_data)

    save_csv(data, month, year)
    return data, month


# --- Main scraper ---
def main_scraper():
    send_telegram_message("🚀 Bot Forex Factory avviato correttamente su Render.")

    months = ["this"]  # Default, puoi cambiare o leggere da parametri se vuoi
    for param in months:
        param = param.lower()
        url = f"https://www.forexfactory.com/calendar?month={param}"
        print(f"[INFO] Fetching {url}")

        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
            continue

        # Determina mese/anno leggibile
        now = datetime.now()
        if param == "this":
            month = now.strftime("%B")
            year = now.year
        elif param == "next":
            next_month = (now.month % 12) + 1
            year = now.year if now.month < 12 else now.year + 1
            month = datetime(year, next_month, 1).strftime("%B")
        else:
            month = param.capitalize()
            year = now.year

        try:
            parse_table_html(html, month, str(year))
        except Exception as e:
            print(f"[ERROR] Failed to parse table for {month} {year}: {e}")

        time.sleep(3)


# --- Flask routes ---
@app.route("/")
def index():
    return "Bot Forex Factory è attivo! 🚀"


@app.route("/run")
def run_scraper():
    thread = threading.Thread(target=main_scraper)
    thread.start()
    return "Scraper avviato! 🚀"


# --- Start Flask Web Service ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
