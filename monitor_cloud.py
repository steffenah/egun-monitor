"""
eGun Monitor – Cloud-Version für GitHub Actions.
Wird einmal ausgeführt, prüft auf neue Sofortkauf-Inserate über MIN_PRICE€
und sendet eine E-Mail wenn neue gefunden wurden.
Zustand wird in seen_items.json gespeichert (wird ins Repo committed).
"""

import json
import os
import re
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
SEEN_FILE = BASE_DIR / "seen_items.json"

URL = "https://egun.de/market/list_items.php?cat=492"
MIN_PRICE = 45.0

# Zugangsdaten kommen aus GitHub Secrets (Umgebungsvariablen)
SENDER_EMAIL    = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]


def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def load_seen() -> dict:
    if not SEEN_FILE.exists():
        return {}
    with open(SEEN_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen: dict):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def parse_price(text: str):
    match = re.search(r"(\d+(?:[.,]\d{1,2})?)\s*EUR", text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            pass
    return None


def fetch_listings() -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(URL, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    listings = []
    seen_ids: set[str] = set()

    for link in soup.find_all("a", href=re.compile(r"item\.php\?id=\d+")):
        title = link.get_text(strip=True)
        if not title:
            continue
        item_id_match = re.search(r"id=(\d+)", link["href"])
        if not item_id_match:
            continue
        item_id = item_id_match.group(1)
        if item_id in seen_ids:
            continue
        seen_ids.add(item_id)

        price = None
        is_sofortkauf = False
        row = link.find_parent("tr")
        if row:
            row_text = row.get_text(" ", strip=True)
            price = parse_price(row_text)
            if row.find(class_="ls-buynow") or row.find(attrs={"title": "Sofortkauf-Artikel"}):
                is_sofortkauf = True
            elif "Gebote" not in row_text and "Gebot" not in row_text:
                is_sofortkauf = True

        listings.append({
            "id": item_id,
            "title": title,
            "price": price,
            "is_sofortkauf": is_sofortkauf,
            "url": f"https://egun.de/market/item.php?id={item_id}",
        })

    return listings


def send_email(new_items: list[dict]):
    subject = f"eGun: {len(new_items)} neues Inserat{'e' if len(new_items) > 1 else ''} – Sofortkauf über {MIN_PRICE:.0f}€"

    lines = [f"Neue Sofortkauf-Inserate auf eGun (Kategorie 492) über {MIN_PRICE:.0f}€:\n"]
    for item in new_items:
        price_str = f"{item['price']:.2f}€" if item["price"] else "Preis unbekannt"
        lines += [f"• {item['title']}", f"  Preis: {price_str}", f"  Link:  {item['url']}\n"]
    lines += [f"\nGefunden am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}", f"Quelle: {URL}"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText("\n".join(lines), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SENDER_EMAIL, SENDER_PASSWORD)
        s.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

    log(f"E-Mail gesendet: {subject}")


def main():
    log("=== eGun Monitor Cloud-Lauf gestartet ===")
    seen = load_seen()
    log(f"Bekannte Inserate: {len(seen)}")

    listings = fetch_listings()
    log(f"{len(listings)} Inserate gefunden.")

    new_items = []
    for item in listings:
        if item["id"] not in seen:
            if item["is_sofortkauf"] and item["price"] and item["price"] > MIN_PRICE:
                new_items.append(item)
                log(f"  NEU: {item['title']} – {item['price']:.2f}€")
            seen[item["id"]] = {
                "title": item["title"],
                "price": item["price"],
                "is_sofortkauf": item["is_sofortkauf"],
                "first_seen": datetime.now().isoformat(),
            }

    if new_items:
        send_email(new_items)
    else:
        log("Keine neuen Inserate.")

    save_seen(seen)
    log("=== Lauf beendet ===")


if __name__ == "__main__":
    main()
