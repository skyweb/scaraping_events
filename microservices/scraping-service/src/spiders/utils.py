# -*- coding: utf-8 -*-
"""
Utilità condivise per tutti gli spider di eventi.

Contiene costanti e funzioni pure (senza stato) usate da più spider.
"""

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# User-Agent e impostazioni di scraping di default
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Settings usabili come base in ogni spider con spread operator:
#   custom_settings = {**DEFAULT_CRAWL_SETTINGS, "DOWNLOAD_DELAY": 1.0}
DEFAULT_CRAWL_SETTINGS: dict = {
    "USER_AGENT": DEFAULT_USER_AGENT,
    "ROBOTSTXT_OBEY": True,
    "CONCURRENT_REQUESTS": 2,
    "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    "DOWNLOAD_DELAY": 2.0,
    "RANDOMIZE_DOWNLOAD_DELAY": True,
}


# ---------------------------------------------------------------------------
# Date in italiano
# ---------------------------------------------------------------------------

# Mappa mesi italiani → numero mese
MESI_IT: dict[str, int] = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}


_ALLOWED_HTML_TAGS = frozenset({"p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "a", "h2", "h3", "h4"})


def sanitize_html(html_content: str) -> Optional[str]:
    """
    Pulisce HTML mantenendo solo tag essenziali (p, br, strong, em, a, liste, heading).

    Rimuove: div, script, style, commenti, attributi data-*, class, slot pubblicitari.
    Usata da spider che conservano HTML nella descrizione (es. city_today).
    """
    text = re.sub(r"<!--.*?-->", "", html_content, flags=re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<div[^>]*data-move[^>]*>.*?</div>\s*</div>\s*</div>", "", text, flags=re.DOTALL)
    text = re.sub(r'<div[^>]*class="slot[^"]*"[^>]*>.*?</div>', "", text, flags=re.DOTALL)

    def _replace_tag(match: re.Match) -> str:
        tag_name = match.group(1).lower().split()[0]
        if tag_name.lstrip("/") in _ALLOWED_HTML_TAGS:
            if tag_name == "a":
                href = re.search(r'href="([^"]*)"', match.group(0))
                return f'<a href="{href.group(1)}">' if href else "<a>"
            return f"<{tag_name}>"
        return ""

    text = re.sub(r"<(/?\w[^>]*)>", _replace_tag, text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text if text else None


def parse_italian_date_time(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Converte una stringa data/ora italiana in (YYYY-MM-DD, HH:MM).

    Gestisce:
    - "venerdì 13 marzo 2026 H: 21:00"
    - "venerdì 13 marzo 2026H: 21:00"   (senza spazio prima di H:)
    - "venerdì 13 marzo 2026"
    - "13 marzo 2026"
    - "13 marzo"

    Returns:
        Tupla (data YYYY-MM-DD o None, ora HH:MM o None)
    """
    text = text.strip()

    # Estrai orario se presente (es: "H: 21:00", "H:21:00", "H 21:00")
    time_match = re.search(r"H:?\s*(\d{1,2}:\d{2})", text, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else None
    # Rimuovi la parte orario per parsare la data
    date_text = re.sub(r"H:?\s*\d{1,2}:\d{2}", "", text, flags=re.IGNORECASE).strip()

    parts = date_text.lower().split()
    # Rimuovi giorno della settimana se la prima parola non è un numero
    if parts and not parts[0][0].isdigit():
        parts = parts[1:]

    if len(parts) < 2:
        return None, time_str

    try:
        day = int(parts[0])
        month = MESI_IT.get(parts[1])
        if not month:
            return None, time_str
        year = int(parts[2]) if len(parts) >= 3 else datetime.now().year
        return f"{year:04d}-{month:02d}-{day:02d}", time_str
    except (ValueError, IndexError):
        return None, time_str
