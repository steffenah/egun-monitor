"""
Monitor-Einstellungen GUI
Verwaltung aller Quellen, Suchbegriffe und Preisschwellen.
"""

import json
import os
import subprocess
import threading
import uuid
from pathlib import Path

import customtkinter as ctk

BASE_DIR = Path(__file__).parent
MONITORS_FILE = BASE_DIR / "monitors.json"
CONFIG_FILE = BASE_DIR / "config.json"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Daten laden/speichern ─────────────────────────────────────────────────────

def load_monitors() -> list[dict]:
    if not MONITORS_FILE.exists():
        return []
    with open(MONITORS_FILE, encoding="utf-8") as f:
        return json.load(f).get("monitors", [])


def save_monitors(monitors: list[dict]):
    with open(MONITORS_FILE, "w", encoding="utf-8") as f:
        json.dump({"monitors": monitors}, f, ensure_ascii=False, indent=2)


def load_email_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"sender_email": "", "sender_password": "", "recipient_email": ""}
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_email_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ── Haupt-App ─────────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🔫 Monitor Einstellungen")
        self.geometry("900x620")
        self.resizable(True, True)
        self.monitors = load_monitors()
        self.selected_index = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        # ── Linke Spalte: Monitor-Liste ──────────────────────────────────────
        left = ctk.CTkFrame(self, width=260, corner_radius=0)
        left.pack(side="left", fill="y", padx=0, pady=0)
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Meine Monitore", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(18, 8), padx=12)

        self.list_frame = ctk.CTkScrollableFrame(left, corner_radius=8)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ctk.CTkButton(left, text="+ Neu hinzufügen", command=self._new_monitor, height=36).pack(padx=10, pady=(0, 12))

        # ── Rechte Seite: Tabs ───────────────────────────────────────────────
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True, padx=0)

        self.tabs = ctk.CTkTabview(right)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=14)
        self.tabs.add("📋 Monitor bearbeiten")
        self.tabs.add("📧 E-Mail Einstellungen")

        self._build_edit_tab(self.tabs.tab("📋 Monitor bearbeiten"))
        self._build_email_tab(self.tabs.tab("📧 E-Mail Einstellungen"))

    # ── Monitor-Liste (links) ─────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, m in enumerate(self.monitors):
            color = "#2b6cb0" if i == self.selected_index else "transparent"
            row = ctk.CTkFrame(self.list_frame, fg_color=color, corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)

            dot = "🟢" if m.get("enabled", True) else "🔴"
            name = m.get("name", "Ohne Namen")
            lbl = ctk.CTkLabel(row, text=f"{dot}  {name}", anchor="w",
                               font=ctk.CTkFont(size=13), cursor="hand2")
            lbl.pack(side="left", fill="x", expand=True, padx=8, pady=6)
            lbl.bind("<Button-1>", lambda e, idx=i: self._select(idx))
            row.bind("<Button-1>", lambda e, idx=i: self._select(idx))

    def _select(self, index: int):
        self.selected_index = index
        self._refresh_list()
        self._load_into_form(self.monitors[index])
        self.tabs.set("📋 Monitor bearbeiten")

    # ── Bearbeiten-Tab (rechts oben) ──────────────────────────────────────────

    def _build_edit_tab(self, parent):
        f = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
        f.pack(fill="both", expand=True)

        def row(label, widget_factory, **kw):
            ctk.CTkLabel(f, text=label, anchor="w", font=ctk.CTkFont(size=13)).pack(fill="x", padx=6, pady=(10, 0))
            w = widget_factory(f, **kw)
            w.pack(fill="x", padx=6, pady=(2, 0))
            return w

        self.e_name = row("Name / Bezeichnung", ctk.CTkEntry, placeholder_text="z.B. eGun Softair", height=36)
        self.e_url  = row("Webseiten-URL", ctk.CTkEntry, placeholder_text="https://...", height=36)

        url_hint = (
            "💡  Kleinanzeigen: Suchbegriff direkt in der URL angeben:\n"
            "     https://www.kleinanzeigen.de/s-oldenburg/monitor-32-zoll/k0\n"
            "     https://www.kleinanzeigen.de/s-oldenburg/airsoft/k0\n"
            "     eGun: https://egun.de/market/list_items.php?cat=492"
        )
        ctk.CTkLabel(f, text=url_hint, anchor="w", justify="left",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(fill="x", padx=6, pady=(2, 0))

        ctk.CTkLabel(f, text="Suchbegriffe (kommagetrennt, leer = alles)", anchor="w",
                     font=ctk.CTkFont(size=13)).pack(fill="x", padx=6, pady=(10, 0))
        ctk.CTkLabel(f, text="z.B.  airsoft, sniper, gbb  – nur Inserate die EINES der Wörter enthalten",
                     anchor="w", font=ctk.CTkFont(size=11), text_color="gray").pack(fill="x", padx=6)
        self.e_keywords = ctk.CTkEntry(f, placeholder_text="leer lassen = alle Inserate melden", height=36)
        self.e_keywords.pack(fill="x", padx=6, pady=(2, 0))

        self.e_price     = row("Mindestpreis in € (0 = kein Limit)", ctk.CTkEntry,
                               placeholder_text="45", height=36)
        self.e_max_price = row("Maximalpreis in € (0 = kein Limit)", ctk.CTkEntry,
                               placeholder_text="200", height=36)

        self.v_sofort  = ctk.BooleanVar(value=True)
        self.v_enabled = ctk.BooleanVar(value=True)
        sw_frame = ctk.CTkFrame(f, fg_color="transparent")
        sw_frame.pack(fill="x", padx=6, pady=(12, 0))
        ctk.CTkSwitch(sw_frame, text="Nur Sofortkauf / Festpreis  (keine Auktionen)",
                      variable=self.v_sofort).pack(side="left", padx=(0, 20))
        ctk.CTkSwitch(sw_frame, text="Monitor aktiv",
                      variable=self.v_enabled).pack(side="left")

        # Buttons
        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.pack(fill="x", padx=6, pady=18)
        ctk.CTkButton(btn_frame, text="💾 Speichern", command=self._save_monitor,
                      width=140, height=38).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="▶ Jetzt testen", command=self._test_monitor,
                      width=140, height=38, fg_color="#2d6a2d").pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="🗑 Löschen", command=self._delete_monitor,
                      width=120, height=38, fg_color="#8b1a1a").pack(side="left")

        # Status-Ausgabe
        ctk.CTkLabel(f, text="Status / Testergebnis:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", padx=6, pady=(4, 0))
        self.status_box = ctk.CTkTextbox(f, height=130, font=ctk.CTkFont(size=12, family="Courier New"))
        self.status_box.pack(fill="x", padx=6, pady=(2, 10))

    def _load_into_form(self, m: dict):
        def set_entry(e, val):
            e.delete(0, "end")
            e.insert(0, str(val) if val else "")

        set_entry(self.e_name, m.get("name", ""))
        set_entry(self.e_url, m.get("url", ""))
        set_entry(self.e_keywords, ", ".join(m.get("keywords", [])))
        set_entry(self.e_price, str(m.get("min_price", 0)))
        set_entry(self.e_max_price, str(m.get("max_price", 0)))
        self.v_sofort.set(m.get("sofortkauf_only", False))
        self.v_enabled.set(m.get("enabled", True))
        self.status_box.delete("1.0", "end")

    def _form_to_dict(self) -> dict | None:
        name = self.e_name.get().strip()
        url  = self.e_url.get().strip()
        if not name or not url:
            self._status("⚠ Name und URL sind Pflichtfelder.")
            return None
        kws = [k.strip() for k in self.e_keywords.get().split(",") if k.strip()]
        try:
            price = float(self.e_price.get().strip() or "0")
        except ValueError:
            price = 0.0
        try:
            max_price = float(self.e_max_price.get().strip() or "0")
        except ValueError:
            max_price = 0.0
        return {
            "name": name,
            "url": url,
            "keywords": kws,
            "min_price": price,
            "max_price": max_price,
            "sofortkauf_only": self.v_sofort.get(),
            "enabled": self.v_enabled.get(),
        }

    def _save_monitor(self):
        data = self._form_to_dict()
        if data is None:
            return
        if self.selected_index is None:
            data["id"] = str(uuid.uuid4())[:8]
            from parsers import detect_site_type
            data["site_type"] = detect_site_type(data["url"])
            self.monitors.append(data)
            self.selected_index = len(self.monitors) - 1
        else:
            existing = self.monitors[self.selected_index]
            data["id"] = existing.get("id", str(uuid.uuid4())[:8])
            from parsers import detect_site_type
            data["site_type"] = detect_site_type(data["url"])
            self.monitors[self.selected_index] = data
        save_monitors(self.monitors)
        self._refresh_list()
        self._status("✅ Gespeichert!")
        self._sync_github()

    def _delete_monitor(self):
        if self.selected_index is None:
            return
        self.monitors.pop(self.selected_index)
        self.selected_index = None
        save_monitors(self.monitors)
        self._refresh_list()
        self._clear_form()
        self._status("🗑 Monitor gelöscht.")
        self._sync_github()

    def _new_monitor(self):
        self.selected_index = None
        self._clear_form()
        self._refresh_list()
        self.tabs.set("📋 Monitor bearbeiten")

    def _clear_form(self):
        for e in (self.e_name, self.e_url, self.e_keywords, self.e_price):
            e.delete(0, "end")
        self.v_sofort.set(False)
        self.v_enabled.set(True)
        self.status_box.delete("1.0", "end")

    def _test_monitor(self):
        data = self._form_to_dict()
        if data is None:
            return
        self._status("⏳ Prüfe Webseite …")
        threading.Thread(target=self._run_test, args=(data,), daemon=True).start()

    def _run_test(self, monitor: dict):
        try:
            from parsers import get_listings, matches_keywords
            listings = get_listings(monitor)
            kws = monitor.get("keywords", [])
            min_p = monitor.get("min_price", 0)
            sofort = monitor.get("sofortkauf_only", False)

            hits = [
                l for l in listings
                if matches_keywords(l["title"], kws)
                and (l["price"] or 0) >= min_p
                and (not sofort or l.get("is_sofortkauf", True))
            ]

            lines = [f"✅ {len(listings)} Einträge gefunden, {len(hits)} passen zu deinen Kriterien:\n"]
            for item in hits[:15]:
                price_str = f"{item['price']:.2f}€" if item["price"] else "—"
                lines.append(f"  • {item['title'][:60]}  [{price_str}]")
            if len(hits) > 15:
                lines.append(f"  … und {len(hits) - 15} weitere")
            self._status("\n".join(lines))
        except Exception as e:
            self._status(f"❌ Fehler: {e}")

    def _status(self, text: str):
        self.status_box.delete("1.0", "end")
        self.status_box.insert("end", text)

    # ── E-Mail-Tab ────────────────────────────────────────────────────────────

    def _build_email_tab(self, parent):
        f = ctk.CTkFrame(parent, corner_radius=0, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=10, pady=10)

        cfg = load_email_config()

        def row(label, key, placeholder="", show=""):
            ctk.CTkLabel(f, text=label, anchor="w", font=ctk.CTkFont(size=13)).pack(fill="x", padx=6, pady=(12, 0))
            e = ctk.CTkEntry(f, placeholder_text=placeholder, height=36, show=show)
            e.insert(0, cfg.get(key, ""))
            e.pack(fill="x", padx=6, pady=(2, 0))
            return e

        self.em_sender    = row("Absender Gmail", "sender_email", "Eguntracker@gmail.com")
        self.em_password  = row("Gmail App-Passwort", "sender_password", "xxxx xxxx xxxx xxxx", show="●")
        self.em_recipient = row("Empfänger E-Mail", "recipient_email", "deine@email.de")

        ctk.CTkLabel(f, text="App-Passwort erstellen: https://myaccount.google.com/apppasswords",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w", padx=6, pady=(4, 0))

        btn_row = ctk.CTkFrame(f, fg_color="transparent")
        btn_row.pack(fill="x", padx=6, pady=16)
        ctk.CTkButton(btn_row, text="💾 Speichern", command=self._save_email, height=36, width=130).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="✉ Test-Mail senden", command=self._send_test_mail, height=36, width=160, fg_color="#2d6a2d").pack(side="left")

        self.email_status = ctk.CTkLabel(f, text="", anchor="w", font=ctk.CTkFont(size=12))
        self.email_status.pack(fill="x", padx=6)

    def _save_email(self):
        cfg = {
            "sender_email":    self.em_sender.get().strip(),
            "sender_password": self.em_password.get().strip(),
            "recipient_email": self.em_recipient.get().strip(),
        }
        save_email_config(cfg)
        self.email_status.configure(text="✅ Gespeichert!", text_color="lightgreen")

    def _send_test_mail(self):
        self._save_email()
        self.email_status.configure(text="⏳ Sende …", text_color="white")
        threading.Thread(target=self._do_test_mail, daemon=True).start()

    def _do_test_mail(self):
        import smtplib
        from email.mime.text import MIMEText
        cfg = load_email_config()
        try:
            msg = MIMEText("Test-Nachricht vom Monitor. Alles funktioniert! ✅", "plain", "utf-8")
            msg["Subject"] = "Monitor – Test erfolgreich"
            msg["From"] = cfg["sender_email"]
            msg["To"] = cfg["recipient_email"]
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                s.login(cfg["sender_email"], cfg["sender_password"])
                s.sendmail(cfg["sender_email"], cfg["recipient_email"], msg.as_string())
            self.email_status.configure(text="✅ Test-Mail gesendet!", text_color="lightgreen")
        except Exception as e:
            self.email_status.configure(text=f"❌ {e}", text_color="red")

    # ── GitHub Sync ───────────────────────────────────────────────────────────

    def _sync_github(self):
        threading.Thread(target=self._do_sync, daemon=True).start()

    def _do_sync(self):
        try:
            import sys
            git = "git"
            repo = BASE_DIR
            subprocess.run([git, "-C", str(repo), "add", "monitors.json"],
                           capture_output=True, check=True)
            result = subprocess.run([git, "-C", str(repo), "diff", "--cached", "--quiet"],
                                    capture_output=True)
            if result.returncode != 0:
                subprocess.run([git, "-C", str(repo), "commit", "-m",
                                "chore: monitors.json aktualisiert [skip ci]"],
                               capture_output=True, check=True)
                subprocess.run([git, "-C", str(repo), "push", "origin", "main"],
                               capture_output=True, check=True)
        except Exception:
            pass  # Sync-Fehler still ignorieren


if __name__ == "__main__":
    app = App()
    app.mainloop()
