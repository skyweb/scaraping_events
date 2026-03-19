"""
Estrazione dati strutturati da testo eventi tramite spaCy NLP.

Funzionalità:
- NER (Named Entity Recognition) per persone, organizzazioni, luoghi, date
- EntityRuler con pattern italiani (a cura di, presso, ingresso, dalle...alle)
- Classificazione categoria automatica dal testo
- Normalizzazione nomi (maiuscole, prefissi, duplicati)
- Regex per email, telefoni, URL, prezzi, orari

Modello: it_core_news_lg (italiano, 500MB)
"""

import logging
import re
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

_nlp = None

# =============================================================================
# Pattern EntityRuler — regole italiane per eventi
# =============================================================================

ENTITY_RULER_PATTERNS = [
    # "a cura di [PERSONA/ORG]"
    {"label": "CURATOR", "pattern": [{"LOWER": "a"}, {"LOWER": "cura"}, {"LOWER": "di"}, {"IS_TITLE": True, "OP": "+"}, ]},
    {"label": "CURATOR", "pattern": [{"LOWER": "curato"}, {"LOWER": "da"}, {"IS_TITLE": True, "OP": "+"}]},
    # "regia di [PERSONA]"
    {"label": "DIRECTOR", "pattern": [{"LOWER": "regia"}, {"LOWER": "di"}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "DIRECTOR", "pattern": [{"LOWER": "regia"}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "DIRECTOR", "pattern": [{"LOWER": "diretto"}, {"LOWER": "da"}, {"IS_TITLE": True, "OP": "+"}]},
    # "con [PERSONA] (interprete/artista)"
    {"label": "PERFORMER", "pattern": [{"LOWER": "con"}, {"IS_TITLE": True, "OP": "+"}, {"LOWER": {"IN": ["e", ","]}, "OP": "?"}, {"IS_TITLE": True, "OP": "*"}]},
    # "presso [LUOGO]"
    {"label": "VENUE", "pattern": [{"LOWER": "presso"}, {"IS_TITLE": True, "OP": "+"}]},
    {"label": "VENUE", "pattern": [{"LOWER": "presso"}, {"LOWER": {"IN": ["il", "la", "lo", "l'", "i", "le", "gli"]}, "OP": "?"}, {"IS_TITLE": True, "OP": "+"}]},
    # "ingresso [PREZZO]"
    {"label": "PRICE", "pattern": [{"LOWER": {"IN": ["ingresso", "biglietto", "costo"]}}, {"IS_PUNCT": True, "OP": "?"}, {"LIKE_NUM": True}, {"LOWER": {"IN": ["€", "euro"]}, "OP": "?"}]},
    {"label": "PRICE", "pattern": [{"LOWER": {"IN": ["ingresso", "biglietto"]}}, {"LOWER": {"IN": ["gratuito", "libero", "free"]}}]},
    # "dalle [ORA] alle [ORA]"
    {"label": "TIME_RANGE", "pattern": [{"LOWER": {"IN": ["dalle", "ore"]}}, {"SHAPE": {"IN": ["dd:dd", "dd.dd", "d:dd", "d.dd"]}}, {"LOWER": {"IN": ["alle", "-", "–"]}, "OP": "?"}, {"SHAPE": {"IN": ["dd:dd", "dd.dd", "d:dd", "d.dd"]}, "OP": "?"}]},
    # "dal [DATA] al [DATA]"
    {"label": "DATE_RANGE", "pattern": [{"LOWER": "dal"}, {"LIKE_NUM": True}, {"IS_ALPHA": True}, {"LIKE_NUM": True, "OP": "?"}, {"LOWER": "al"}, {"LIKE_NUM": True}, {"IS_ALPHA": True}, {"LIKE_NUM": True, "OP": "?"}]},
]

# =============================================================================
# Classificazione categorie — keyword matching
# =============================================================================

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "musica": [
        "concerto", "concerti", "orchestra", "musicale", "musicista", "jazz", "rock",
        "classica", "sinfonica", "coro", "band", "live music", "dj set", "opera lirica",
        "festival musicale", "recital", "soprano", "tenore", "pianoforte", "violino",
        "chitarra", "cantante", "cantautore", "rapper",
    ],
    "teatro": [
        "teatro", "teatrale", "commedia", "dramma", "spettacolo", "palcoscenico",
        "attore", "attrice", "regista", "regia", "messa in scena", "sipario",
        "compagnia teatrale", "monologo", "prosa", "tragedia", "musical",
    ],
    "danza": [
        "danza", "balletto", "coreografia", "ballerino", "ballerina", "danzatore",
        "contemporanea", "classico", "hip hop", "tango", "flamenco",
    ],
    "mostre": [
        "mostra", "esposizione", "galleria", "museo", "opere d'arte", "pittura",
        "scultura", "fotografia", "installazione", "retrospettiva", "collezione",
        "vernissage", "artista", "quadri",
    ],
    "cinema": [
        "cinema", "film", "proiezione", "cortometraggio", "documentario",
        "rassegna cinematografica", "regista", "pellicola", "sala cinematografica",
    ],
    "sagre_feste": [
        "sagra", "festa", "fiera", "mercato", "mercatino", "tradizione", "folklore",
        "processione", "patronale", "carnevale", "palio", "rievocazione",
        "enogastronomia", "prodotti tipici", "street food",
    ],
    "sport": [
        "sport", "sportivo", "gara", "corsa", "maratona", "ciclismo", "calcio",
        "torneo", "campionato", "pallavolo", "basket", "nuoto", "sci", "trekking",
        "escursione", "arrampicata", "running",
    ],
    "conferenze": [
        "conferenza", "convegno", "seminario", "workshop", "incontro", "dibattito",
        "presentazione", "lectio", "tavola rotonda", "simposio", "congresso",
        "lezione", "formazione",
    ],
    "bambini": [
        "bambini", "famiglie", "ragazzi", "kids", "laboratorio didattico",
        "animazione", "gioco", "burattini", "marionette", "fiabe", "ludoteca",
    ],
    "enogastronomia": [
        "vino", "degustazione", "gastronomia", "cucina", "chef", "ristorante",
        "cantina", "cibo", "ricetta", "pizza", "birra", "olio",
    ],
    "natura": [
        "natura", "escursione", "passeggiata", "parco", "giardino", "botanico",
        "birdwatching", "flora", "fauna", "montagna", "lago", "mare", "bosco",
    ],
}

# =============================================================================
# Normalizzazione nomi
# =============================================================================

# Prefissi/suffissi da rimuovere dai nomi di persone
_PERSON_NOISE = re.compile(
    r"^(il|la|lo|l'|un|una|uno|del|della|dello|dell'|di|da|in|con|su|per|tra|fra|"
    r"sig\.|sig\.ra|dott\.|dott\.ssa|prof\.|prof\.ssa|ing\.|avv\.|arch\.)\s+",
    re.IGNORECASE,
)

# Parole che non sono nomi di persone
_PERSON_BLACKLIST = {
    "direttore", "direttrice", "regista", "curatore", "curatrice",
    "presentazione", "inaugurazione", "apertura", "chiusura",
    "comune", "provincia", "regione", "assessore", "sindaco",
    "lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica",
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    "info", "contatti", "telefono", "email", "sito", "web",
}


def _normalize_name(name: str) -> Optional[str]:
    """Normalizza un nome di persona: pulizia, title case, rimozione noise."""
    if not name or len(name) < 3:
        return None

    # Rimuovi prefissi
    clean = _PERSON_NOISE.sub("", name).strip()
    if not clean or len(clean) < 3:
        return None

    # Blacklist
    if clean.lower() in _PERSON_BLACKLIST:
        return None

    # Se è tutto maiuscolo o tutto minuscolo, converti a Title Case
    if clean.isupper() or clean.islower():
        clean = clean.title()

    # Rimuovi punteggiatura trailing
    clean = clean.rstrip(".,;:!?)")
    if not clean or len(clean) < 3:
        return None

    # Deve avere almeno 2 parole (nome + cognome) o essere un nome noto
    words = clean.split()
    if len(words) < 2:
        return None

    # Ogni parola deve iniziare con maiuscola (dopo normalizzazione)
    if not all(w[0].isupper() or w[0] == "'" for w in words if w):
        return None

    return clean


def _normalize_org(name: str) -> Optional[str]:
    """Normalizza un nome di organizzazione."""
    if not name or len(name) < 3:
        return None
    clean = name.strip().rstrip(".,;:!?)")
    if len(clean) < 3:
        return None
    # Rimuovi organizzazioni generiche
    if clean.lower() in ("comune", "provincia", "regione", "italia", "europe"):
        return None
    return clean


def _normalize_location(name: str) -> Optional[str]:
    """Normalizza un nome di luogo."""
    if not name or len(name) < 2:
        return None
    clean = name.strip().rstrip(".,;:!?)")
    if len(clean) < 2:
        return None
    return clean


# =============================================================================
# Setup pipeline spaCy
# =============================================================================

def _get_nlp():
    """Carica il modello spaCy con EntityRuler custom (lazy, una sola volta)."""
    global _nlp
    if _nlp is None:
        import spacy
        from spacy.language import Language

        try:
            _nlp = spacy.load("it_core_news_lg", disable=["parser", "lemmatizer"])
            logger.info("spaCy modello it_core_news_lg caricato (parser/lemmatizer disabilitati)")
        except OSError:
            try:
                _nlp = spacy.load("it_core_news_sm", disable=["parser", "lemmatizer"])
                logger.warning("Fallback a it_core_news_sm")
            except OSError:
                logger.error("Nessun modello spaCy italiano. Eseguire: python -m spacy download it_core_news_lg")
                raise

        # Aggiungi EntityRuler con pattern italiani (prima del NER per dare priorità)
        ruler = _nlp.add_pipe("entity_ruler", before="ner")
        ruler.add_patterns(ENTITY_RULER_PATTERNS)
        logger.info(f"EntityRuler aggiunto con {len(ENTITY_RULER_PATTERNS)} pattern")

    return _nlp


# =============================================================================
# Classificazione categoria
# =============================================================================

def classify_category(text: str) -> list[str]:
    """
    Classifica il testo in una o più categorie di evento.

    Returns:
        Lista di categorie ordinate per rilevanza (max 3).
    """
    if not text:
        return []

    text_lower = text.lower()
    scores: dict[str, int] = {}

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            count = text_lower.count(kw)
            if count > 0:
                # Peso maggiore per keyword più lunghe (più specifiche)
                score += count * max(1, len(kw.split()))
        if score > 0:
            scores[category] = score

    # Ordina per score decrescente, prendi max 3
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [cat for cat, _ in ranked[:3]]


# =============================================================================
# Estrazione entità
# =============================================================================

def _clean_html(text: str) -> str:
    """Rimuove tag HTML dal testo."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"&\w+;", " ", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def extract_entities(text: str) -> dict:
    """
    Estrae entità dal testo di un evento con NER + EntityRuler + classificazione.

    Returns:
        {
            "persons": [{"name": "Marco Rossi", "role": "performer"}, ...],
            "organizations": ["Teatro Comunale", ...],
            "locations": ["Bari", ...],
            "dates": ["15 marzo 2026", ...],
            "times": ["21:00", ...],
            "time_ranges": ["dalle 21:00 alle 23:00", ...],
            "prices": ["€15", "ingresso gratuito", ...],
            "emails": ["info@example.com", ...],
            "phones": ["+39 080 123456", ...],
            "urls": ["https://example.com", ...],
            "venues": ["Teatro Comunale di Bari", ...],
            "categories": ["musica", "teatro"],
        }
    """
    if not text:
        return {}

    clean_text = _clean_html(text)
    if not clean_text or len(clean_text) < 10:
        return {}

    nlp = _get_nlp()

    if len(clean_text) > 100000:
        clean_text = clean_text[:100000]

    doc = nlp(clean_text)

    persons = []
    organizations = []
    locations = []
    dates = []
    venues = []
    directors = []
    curators = []
    performers = []
    time_ranges = []
    price_entities = []

    seen = set()
    for ent in doc.ents:
        key = (ent.label_, ent.text.strip())
        if key in seen:
            continue
        seen.add(key)

        text_clean = ent.text.strip()
        if len(text_clean) < 2:
            continue

        if ent.label_ == "PER":
            normalized = _normalize_name(text_clean)
            if normalized:
                persons.append(normalized)
        elif ent.label_ == "ORG":
            normalized = _normalize_org(text_clean)
            if normalized:
                organizations.append(normalized)
        elif ent.label_ in ("LOC", "GPE"):
            normalized = _normalize_location(text_clean)
            if normalized:
                locations.append(normalized)
        elif ent.label_ in ("DATE", "TIME"):
            dates.append(text_clean)
        # EntityRuler custom labels
        elif ent.label_ == "VENUE":
            venues.append(text_clean.replace("presso ", "").strip())
        elif ent.label_ == "DIRECTOR":
            name = re.sub(r"^(regia di|regia|diretto da)\s+", "", text_clean, flags=re.IGNORECASE).strip()
            normalized = _normalize_name(name)
            if normalized:
                directors.append(normalized)
        elif ent.label_ == "CURATOR":
            name = re.sub(r"^(a cura di|curato da)\s+", "", text_clean, flags=re.IGNORECASE).strip()
            normalized = _normalize_name(name)
            if normalized:
                curators.append(normalized)
        elif ent.label_ == "PERFORMER":
            name = re.sub(r"^con\s+", "", text_clean, flags=re.IGNORECASE).strip()
            normalized = _normalize_name(name)
            if normalized:
                performers.append(normalized)
        elif ent.label_ == "TIME_RANGE":
            time_ranges.append(text_clean)
        elif ent.label_ == "PRICE":
            price_entities.append(text_clean)

    # Costruisci persons con ruoli
    persons_with_roles = []
    seen_names = set()
    for name in directors:
        if name not in seen_names:
            persons_with_roles.append({"name": name, "role": "regista"})
            seen_names.add(name)
    for name in curators:
        if name not in seen_names:
            persons_with_roles.append({"name": name, "role": "curatore"})
            seen_names.add(name)
    for name in performers:
        if name not in seen_names:
            persons_with_roles.append({"name": name, "role": "performer"})
            seen_names.add(name)
    for name in persons:
        if name not in seen_names:
            persons_with_roles.append({"name": name, "role": None})
            seen_names.add(name)

    # Regex per dati non catturati da spaCy
    emails = list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", clean_text)))
    phones_raw = re.findall(r"(?:\+39\s?)?(?:0\d{1,4}[\s./-]?\d{4,8}|\d{3}[\s./-]?\d{6,7})", clean_text)
    phones = list(set(p.strip() for p in phones_raw if len(p.strip()) >= 8))
    urls = list(set(re.findall(r"https?://[^\s<>\"']+", clean_text)))
    prices = list(set(
        p.strip() for p in re.findall(
            r"(?:€\s*\d+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?\s*(?:€|euro|EUR)|ingresso\s+(?:gratuito|libero|free))",
            clean_text, re.IGNORECASE,
        )
    ))
    # Aggiungi prezzi da EntityRuler
    for p in price_entities:
        if p not in prices:
            prices.append(p)

    times = list(set(re.findall(r"\b\d{1,2}[:.]\d{2}\b", clean_text)))

    # Classificazione categoria
    categories = classify_category(clean_text)

    # Deduplicazione locations vs venues
    all_venues = list(set(venues))

    result = {}
    if persons_with_roles:
        result["persons"] = persons_with_roles
    if organizations:
        result["organizations"] = list(set(organizations))
    if locations:
        result["locations"] = list(set(locations))
    if all_venues:
        result["venues"] = all_venues
    if dates:
        result["dates"] = dates
    if times:
        result["times"] = times
    if time_ranges:
        result["time_ranges"] = time_ranges
    if prices:
        result["prices"] = prices
    if emails:
        result["emails"] = emails
    if phones:
        result["phones"] = phones
    if urls:
        result["urls"] = urls
    if categories:
        result["categories"] = categories

    return result


# =============================================================================
# Analisi staging event
# =============================================================================

def _collect_texts(obj, min_len: int = 10) -> list[str]:
    """Estrae ricorsivamente tutti i testi da un dict/list nested."""
    texts = []
    if isinstance(obj, str):
        if len(obj) >= min_len:
            texts.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            texts.extend(_collect_texts(v, min_len))
    elif isinstance(obj, list):
        for item in obj:
            texts.extend(_collect_texts(item, min_len))
    return texts


def analyze_staging_event(event) -> dict:
    """
    Analizza un StagingEvent e restituisce i dati NLP estratti.

    Combina description + raw_data.data.section (ricorsivo) per il massimo dei dati.
    """
    texts = []

    # 1. Description
    if event.description:
        texts.append(event.description)

    # 2. Section da raw_data (ricorsivo)
    raw = event.raw_data or {}
    data_block = raw.get("data") or raw
    section = data_block.get("section")
    if section:
        texts.extend(_collect_texts(section))

    # 3. Campi extra
    for key in ("informazioni", "info_e_costi", "info_e_contatti"):
        val = data_block.get(key) or (section.get(key) if isinstance(section, dict) else None)
        if val:
            texts.extend(_collect_texts(val))

    combined = "\n\n".join(texts)
    return extract_entities(combined)
