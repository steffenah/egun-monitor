"""
Monitor Web-Interface – Streamlit App
Verwalte alle Monitore von überall über den Browser.
"""

import json
import uuid
import streamlit as st
from github import Github, GithubException

# ── Seiten-Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitor Einstellungen",
    page_icon="🛒",
    layout="wide",
)

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def get_repo():
    g = Github(st.secrets["github"]["token"])
    return g.get_repo(st.secrets["github"]["repo"])


def load_monitors() -> list[dict]:
    try:
        repo = get_repo()
        f = repo.get_contents("monitors.json")
        return json.loads(f.decoded_content)["monitors"]
    except Exception as e:
        st.error(f"Fehler beim Laden: {e}")
        return []


def save_monitors(monitors: list[dict]) -> bool:
    try:
        repo = get_repo()
        f = repo.get_contents("monitors.json")
        new_content = json.dumps({"monitors": monitors}, ensure_ascii=False, indent=2)
        repo.update_file(
            "monitors.json",
            "chore: monitors via Web-UI aktualisiert [skip ci]",
            new_content,
            f.sha,
        )
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False


def detect_site_type(url: str) -> str:
    if "egun.de" in url:
        return "egun"
    if "kleinanzeigen.de" in url:
        return "kleinanzeigen"
    return "generic"


# ── Login ──────────────────────────────────────────────────────────────────────

def show_login():
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.image("https://em-content.zobj.net/source/google/387/shopping-cart_1f6d2.png", width=80)
        st.title("Monitor Einstellungen")
        st.markdown("---")
        username = st.text_input("👤 Benutzername")
        password = st.text_input("🔒 Passwort", type="password")
        if st.button("Anmelden", use_container_width=True, type="primary"):
            if (username == st.secrets["login"]["username"] and
                    password == st.secrets["login"]["password"]):
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ Falscher Benutzername oder Passwort")


# ── Haupt-App ──────────────────────────────────────────────────────────────────

def show_app():
    # Sidebar
    with st.sidebar:
        st.image("https://em-content.zobj.net/source/google/387/shopping-cart_1f6d2.png", width=50)
        st.title("Monitor")
        st.markdown("---")
        if st.button("🚪 Abmelden", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        st.markdown("---")
        st.caption("Änderungen werden direkt zu GitHub synchronisiert und beim nächsten 10-Minuten-Lauf aktiv.")

    st.title("🛒 Monitor Einstellungen")

    tab_monitors, tab_email, tab_info = st.tabs(["📋 Meine Monitore", "📧 E-Mail", "ℹ️ Hilfe & URLs"])

    # ── Tab: Monitore ──────────────────────────────────────────────────────────
    with tab_monitors:
        monitors = load_monitors()

        # Bestehende Monitore anzeigen
        st.subheader(f"Aktive Monitore ({len(monitors)})")

        for i, m in enumerate(monitors):
            status = "🟢" if m.get("enabled", True) else "🔴"
            with st.expander(f"{status} {m.get('name', 'Ohne Namen')}", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    new_name = st.text_input("Name", value=m.get("name", ""), key=f"name_{i}")
                    new_url  = st.text_input("URL", value=m.get("url", ""), key=f"url_{i}")
                    new_kw   = st.text_input(
                        "Suchbegriffe (kommagetrennt, leer = alles)",
                        value=", ".join(m.get("keywords", [])),
                        key=f"kw_{i}",
                        help="z.B.  airsoft, sniper, gbb"
                    )
                with col2:
                    new_price     = st.number_input("Mindestpreis (€)  (0 = kein Limit)", value=float(m.get("min_price", 0)), min_value=0.0, step=5.0, key=f"price_{i}")
                    new_max_price = st.number_input("Maximalpreis (€)  (0 = kein Limit)", value=float(m.get("max_price", 0)), min_value=0.0, step=5.0, key=f"maxprice_{i}")
                    new_sofort    = st.checkbox("Nur Sofortkauf / Festpreis", value=m.get("sofortkauf_only", False), key=f"sofort_{i}")
                    new_active    = st.checkbox("Monitor aktiv", value=m.get("enabled", True), key=f"active_{i}")

                bcol1, bcol2, _ = st.columns([1, 1, 3])
                with bcol1:
                    if st.button("💾 Speichern", key=f"save_{i}", use_container_width=True):
                        kws = [k.strip() for k in new_kw.split(",") if k.strip()]
                        monitors[i] = {
                            **m,
                            "name": new_name,
                            "url": new_url,
                            "keywords": kws,
                            "min_price": new_price,
                            "max_price": new_max_price,
                            "sofortkauf_only": new_sofort,
                            "enabled": new_active,
                            "site_type": detect_site_type(new_url),
                        }
                        if save_monitors(monitors):
                            st.success("✅ Gespeichert und zu GitHub synchronisiert!")
                with bcol2:
                    if st.button("🗑 Löschen", key=f"del_{i}", use_container_width=True):
                        monitors.pop(i)
                        if save_monitors(monitors):
                            st.success("Gelöscht!")
                            st.rerun()

        st.markdown("---")
        st.subheader("➕ Neuen Monitor hinzufügen")

        with st.form("new_monitor", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                n_name  = st.text_input("Name *", placeholder="z.B. Kleinanzeigen Airsoft")
                n_url   = st.text_input("URL *", placeholder="https://www.kleinanzeigen.de/s-oldenburg/airsoft/k0")
                n_kw    = st.text_input("Suchbegriffe (leer = alles)", placeholder="airsoft, sniper, gbb")
            with col2:
                n_price     = st.number_input("Mindestpreis (€)  (0 = kein Limit)", min_value=0.0, step=5.0)
                n_max_price = st.number_input("Maximalpreis (€)  (0 = kein Limit)", min_value=0.0, step=5.0)
                n_sofort    = st.checkbox("Nur Sofortkauf / Festpreis")
                n_active    = st.checkbox("Monitor sofort aktivieren", value=True)

            submitted = st.form_submit_button("➕ Hinzufügen", use_container_width=True, type="primary")
            if submitted:
                if not n_name or not n_url:
                    st.error("Name und URL sind Pflichtfelder.")
                else:
                    kws = [k.strip() for k in n_kw.split(",") if k.strip()]
                    monitors.append({
                        "id": str(uuid.uuid4())[:8],
                        "name": n_name,
                        "url": n_url,
                        "site_type": detect_site_type(n_url),
                        "keywords": kws,
                        "min_price": n_price,
                        "max_price": n_max_price,
                        "sofortkauf_only": n_sofort,
                        "enabled": n_active,
                    })
                    if save_monitors(monitors):
                        st.success(f"✅ Monitor »{n_name}« hinzugefügt!")
                        st.rerun()

    # ── Tab: E-Mail ────────────────────────────────────────────────────────────
    with tab_email:
        st.subheader("📧 E-Mail Einstellungen")
        st.info("Die E-Mail-Einstellungen sind als GitHub Secrets gespeichert und können nur über GitHub geändert werden.")

        st.markdown("""
        **Aktuelle Einstellungen** (aus GitHub Secrets):
        - **Absender:** preisalarmahlers@gmail.com
        - **Empfänger:** Steffen.Ahlers90@gmail.com

        **Zum Ändern:**
        1. Öffne: https://github.com/steffenah/preis-alarm/settings/secrets/actions
        2. Klicke auf das Secret → **Update**
        """)

        st.markdown("---")
        st.subheader("✉ Test-E-Mail senden")
        if st.button("Test-E-Mail jetzt senden", type="primary"):
            try:
                import smtplib
                from email.mime.text import MIMEText
                # Secrets direkt aus GitHub Actions – hier nicht verfügbar,
                # darum Info-Meldung
                st.info("Test-E-Mails können direkt über GitHub Actions ausgelöst werden:\n"
                        "https://github.com/steffenah/preis-alarm/actions")
            except Exception as e:
                st.error(str(e))

    # ── Tab: Hilfe ─────────────────────────────────────────────────────────────
    with tab_info:
        st.subheader("💡 URL-Tipps für verschiedene Seiten")

        st.markdown("""
        ### Kleinanzeigen
        Suchbegriff direkt in der URL – am einfachsten: auf Kleinanzeigen suchen, URL kopieren.
        ```
        https://www.kleinanzeigen.de/s-oldenburg/airsoft/k0
        https://www.kleinanzeigen.de/s-oldenburg/monitor-32-zoll/k0
        https://www.kleinanzeigen.de/s-frankfurt/iphone-15/k0
        ```

        ### eGun
        Kategorie-Nummer in der URL:
        ```
        https://egun.de/market/list_items.php?cat=492   (Softair)
        https://egun.de/market/list_items.php?cat=14    (Pistolen)
        ```

        ### Airsoft-Verzeichnis Forum
        ```
        https://www.airsoft-verzeichnis.de/index.php?status=forum&sp=28
        ```

        ### Weitere Seiten
        Jede beliebige Seite kann überwacht werden – der Monitor erkennt neue Links und prüft ob deine Suchbegriffe darin vorkommen.

        ---
        ### So funktioniert der Monitor
        - Alle **10 Minuten** prüft GitHub Actions alle aktiven Monitore
        - Nur **neue** Einträge lösen eine E-Mail aus (bereits gesehene werden ignoriert)
        - Bei eGun: nur **Sofortkauf**-Angebote über deiner Preisgrenze (wenn aktiviert)
        - Die E-Mail zeigt **Bieterpreis** und **Sofortkaufpreis** getrennt an

        ### Live-Logs ansehen
        👉 https://github.com/steffenah/preis-alarm/actions
        """)


# ── Einstieg ───────────────────────────────────────────────────────────────────

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    show_login()
else:
    show_app()
