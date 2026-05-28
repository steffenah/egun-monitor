"""
eGun / Kleinanzeigen Monitor – Cloud-Version für GitHub Actions.
Liest alle Monitore aus monitors.json und prüft jede Quelle.
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

BASE_DIR   = Path(__file__).parent
SEEN_FILE  = BASE_DIR / "seen_items.json"
MON_FILE   = BASE_DIR / "monitors.json"

# Zugangsdaten aus GitHub Secrets
SENDER_EMAIL    = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


def load_monitors() -> list[dict]:
    with open(MON_FILE, encoding="utf-8") as f:
        return json.load(f).get("monitors", [])


def load_seen() -> dict:
    if not SEEN_FILE.exists():
        return {}
    with open(SEEN_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_seen(seen: dict):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def send_email(monitor_name: str, new_items: list[dict], min_price: float):
    count = len(new_items)
    subject = f"🔔 {monitor_name}: {count} neues Inserat{'e' if count > 1 else ''}"

    lines = [f"Neue Treffer für »{monitor_name}«:\n"]
    for item in new_items:
        lines.append(f"• {item['title']}")
        if item.get("auction_price") is not None:
            lines.append(f"  Aktuelles Gebot:  {item['auction_price']:.2f} €")
        if item.get("sofortkauf_price") is not None:
            lines.append(f"  Sofortkauf:       {item['sofortkauf_price']:.2f} €")
        if not item.get("auction_price") and not item.get("sofortkauf_price"):
            p = item.get("price")
            lines.append(f"  Preis: {f'{p:.2f} €' if p else 'nicht angegeben'}")
        lines += [f"  Link:  {item['url']}", ""]
    lines += [
        f"\nGefunden am: {datetime.now().strftime('%d.%m.%Y um %H:%M Uhr')}",
    ]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText("\n".join(lines), "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SENDER_EMAIL, SENDER_PASSWORD)
        s.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

    log(f"  → E-Mail gesendet: {subject}")


def get_listings(monitor: dict) -> list[dict]:
    from parsers import get_listings as _get
    return _get(monitor)


def matches(item: dict, monitor: dict) -> bool:
    keywords    = monitor.get("keywords", [])
    min_price   = monitor.get("min_price", 0)
    max_price   = monitor.get("max_price", 0)   # 0 = kein Limit
    sofort_only = monitor.get("sofortkauf_only", False)

    if keywords:
        title_lower = item["title"].lower()
        if not any(kw.lower() in title_lower for kw in keywords):
            return False

    # Relevanten Preis bestimmen (Sofortkauf bevorzugt, sonst Auktionspreis)
    relevant_price = item.get("sofortkauf_price") or item.get("auction_price") or item.get("price") or 0

    if min_price and relevant_price < min_price:
        return False
    if max_price and relevant_price > max_price:
        return False
    if sofort_only and not item.get("is_sofortkauf", True):
        return False
    return True


def main():
    log("=== Monitor Cloud-Lauf gestartet ===")
    monitors = load_monitors()
    seen     = load_seen()
    log(f"{len(monitors)} Monitor(e) geladen, {len(seen)} bekannte Einträge.")

    for monitor in monitors:
        if not monitor.get("enabled", True):
            log(f"[{monitor['name']}] deaktiviert – übersprungen.")
            continue

        log(f"[{monitor['name']}] prüfe {monitor['url']}")
        try:
            listings = get_listings(monitor)
        except Exception as e:
            log(f"[{monitor['name']}] FEHLER: {e}")
            continue

        log(f"[{monitor['name']}] {len(listings)} Einträge gefunden.")
        new_items = []
        for item in listings:
            key = f"{monitor['id']}::{item['id']}"
            if key not in seen:
                seen[key] = {
                    "title":      item["title"],
                    "price":      item.get("price"),
                    "first_seen": datetime.now().isoformat(),
                }
                if matches(item, monitor):
                    new_items.append(item)
                    log(f"  NEU: {item['title'][:60]}  {item.get('price','–')}€")

        if new_items:
            try:
                send_email(monitor["name"], new_items, monitor.get("min_price", 0))
            except Exception as e:
                log(f"  E-Mail Fehler: {e}")
        else:
            log(f"[{monitor['name']}] keine neuen Treffer.")

    save_seen(seen)
    log("=== Lauf beendet ===")


if __name__ == "__main__":
    main()
