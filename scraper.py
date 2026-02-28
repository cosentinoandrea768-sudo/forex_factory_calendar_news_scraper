import time
import argparse
import json
import pandas as pd
import os
import requests
from datetime import datetime
from config import ALLOWED_ELEMENT_TYPES, ICON_COLOR_MAP
from utils import save_csv
import config
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from flask import Flask
import threading

app = Flask(__name__)


def send_telegram_message(message: str):
    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    if not bot_token or not chat_id:
        print("[WARNING] BOT_TOKEN or CHAT_ID not set.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        requests.post(url, json=payload, timeout=10)
        print("[INFO] Startup message sent to Telegram.")
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")


def init_driver(headless=True) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1920x1080")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def scroll_to_end(driver):
    previous_position = None
    while True:
        current_position = driver.execute_script("return window.pageYOffset;")
        driver.execute_script("window.scrollTo(0, window.pageYOffset + 500);")
        time.sleep(2)
        if current_position == previous_position:
            break
        previous_position = current_position


def parse_table(driver, month, year):
    data = []
    table = driver.find_element(By.CLASS_NAME, "calendar__table")

    for row in table.find_elements(By.TAG_NAME, "tr"):
        row_data = {}
        event_id = row.get_attribute("data-event-id")

        for element in row.find_elements(By.TAG_NAME, "td"):
            class_name = element.get_attribute('class')

            if class_name in ALLOWED_ELEMENT_TYPES:
                class_name_key = ALLOWED_ELEMENT_TYPES.get(
                    f"{class_name}", "cell")

                if "calendar__impact" in class_name:
                    impact_elements = element.find_elements(By.TAG_NAME, "span")
                    color = None
                    for impact in impact_elements:
                        impact_class = impact.get_attribute("class")
                        color = ICON_COLOR_MAP.get(impact_class)
                    row_data[f"{class_name_key}"] = color if color else "impact"

                elif "calendar__detail" in class_name and event_id:
                    detail_url = f"https://www.forexfactory.com/calendar?month={month}#detail={event_id}"
                    row_data[f"{class_name_key}"] = detail_url

                elif element.text:
                    row_data[f"{class_name_key}"] = element.text
                else:
                    row_data[f"{class_name_key}"] = "empty"

        if row_data:
            data.append(row_data)

    save_csv(data, month, year)
    return data, month


def main_scraper():
    send_telegram_message("🚀 Bot Forex Factory avviato correttamente su Render.")

    parser = argparse.ArgumentParser(
        description="Scrape Forex Factory calendar.")
    parser.add_argument("--months", nargs="+",
                        help='Target months: e.g., this next')

    args = parser.parse_args(args=[])
    month_params = args.months if args.months else ["this"]

    for param in month_params:
        param = param.lower()
        url = f"https://www.forexfactory.com/calendar?month={param}"

        driver = init_driver()
        driver.get(url)
        detected_tz = driver.execute_script(
            "return Intl.DateTimeFormat().resolvedOptions().timeZone")
        config.SCRAPER_TIMEZONE = detected_tz
        scroll_to_end(driver)

        if param == "this":
            now = datetime.now()
            month = now.strftime("%B")
            year = now.year
        elif param == "next":
            now = datetime.now()
            next_month = (now.month % 12) + 1
            year = now.year if now.month < 12 else now.year + 1
            month = datetime(year, next_month, 1).strftime("%B")
        else:
            month = param.capitalize()
            year = datetime.now().year

        try:
            parse_table(driver, month, str(year))
        except Exception as e:
            print(f"[ERROR] Failed to scrape {param} ({month} {year}): {e}")

        driver.quit()
        time.sleep(3)


@app.route("/")
def index():
    return "Bot Forex Factory è attivo! 🚀"


@app.route("/run")
def run_scraper():
    thread = threading.Thread(target=main_scraper)
    thread.start()
    return "Scraper avviato! 🚀"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
