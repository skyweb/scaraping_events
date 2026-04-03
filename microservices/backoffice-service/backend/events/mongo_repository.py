# -*- coding: utf-8 -*-
"""
Repository MongoDB per gli eventi.

Ogni documento nella collection `staging_events` ha due sezioni:
- campi flat (uuid, title, city, location{}, dates{}, ...): usati per query/filtri
- _raw: documento originale inviato dallo spider (nested Scrapy item)

Le letture dell'API esterna vengono tutte da qui.
Postgres resta lo store per admin e API interne.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from pymongo import ASCENDING, DESCENDING, UpdateOne

from backoffice.mongodb import get_collection


def _to_datetime(value) -> Optional[datetime]:
    """Converte un valore in datetime UTC per la persistenza come BSON Date."""
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None

logger = logging.getLogger(__name__)

COLLECTION = "staging_events"

_SORT_FIELDS = {
    "created_at", "dates.start", "dates.end", "city",
    "rank_score", "boost", "title", "source",
}


def _parse_sort(ordering_param: str) -> list[tuple[str, int]]:
    """Converte il parametro ordering DRF in lista di tuple per pymongo sort."""
    result = []
    for part in ordering_param.split(","):
        part = part.strip()
        if not part:
            continue
        direction = DESCENDING if part.startswith("-") else ASCENDING
        field = part.lstrip("-")
        if field in _SORT_FIELDS:
            result.append((field, direction))
    return result or [("boost", DESCENDING), ("rank_score", DESCENDING), ("ingested_at", DESCENDING)]


def _build_filter(params: dict) -> dict:
    """Costruisce il filtro MongoDB dai query params dell'API."""
    mongo_filter: dict = {}

    for field in ("city", "source", "status"):
        if params.get(field):
            mongo_filter[field] = params[field]

    if "is_active" in params and params["is_active"] is not None:
        val = params["is_active"]
        if isinstance(val, str):
            val = val.lower() in ("true", "1", "yes")
        mongo_filter["is_active"] = bool(val)

    if params.get("date_start"):
        try:
            ds = datetime.fromisoformat(str(params["date_start"]))
            mongo_filter.setdefault("dates.start", {})["$gte"] = ds
        except ValueError:
            pass

    if params.get("date_end"):
        try:
            de = datetime.fromisoformat(str(params["date_end"]))
            mongo_filter.setdefault("dates.end", {})["$lte"] = de
        except ValueError:
            pass

    search = params.get("search")
    if search:
        mongo_filter["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"location.name": {"$regex": search, "$options": "i"}},
        ]

    return mongo_filter


def list_events(
    params: dict,
    ordering: str = "-boost,-rank_score,-ingested_at",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    """
    Restituisce (lista_eventi, totale) con filtri, ordinamento e paginazione.

    I campi _id e _raw vengono esclusi dalla proiezione.
    """
    collection = get_collection(COLLECTION)
    if collection is None:
        return [], 0

    mongo_filter = _build_filter(params)
    sort = _parse_sort(ordering)
    skip = (page - 1) * page_size

    total = collection.count_documents(mongo_filter)
    cursor = (
        collection
        .find(mongo_filter, {"_id": 0, "_raw": 0})
        .sort(sort)
        .skip(skip)
        .limit(page_size)
    )
    return list(cursor), total


def get_event(uuid: str) -> Optional[dict]:
    """Recupera singolo evento per uuid. Ritorna None se non trovato."""
    collection = get_collection(COLLECTION)
    if collection is None:
        return None
    return collection.find_one({"uuid": uuid}, {"_id": 0})


def validated_data_to_doc(validated_data: dict, spider: str) -> dict:
    """
    Costruisce il documento MongoDB da validated_data del serializer.

    validated_data proviene da EventScrapingSerializer.to_internal_value()
    e include già tutti i campi normalizzati + raw_data (item originale spider).
    """
    city = validated_data.get("city") or {}
    dates = validated_data.get("dates") or {}

    now = datetime.now(tz=timezone.utc)
    return {
        "uuid": str(validated_data["uuid"]),
        "content_hash": validated_data.get("content_hash"),
        "source": validated_data.get("source", ""),
        "title": validated_data.get("title", ""),
        "category": validated_data.get("category"),
        "description": validated_data.get("description"),
        "city": city.get("city_name"),
        "url": validated_data.get("url"),
        "cover_url": validated_data.get("cover_url"),
        "location": {
            "name": city.get("location_name"),
            "address": city.get("location_address"),
            "url": city.get("location_url"),
            "coordinates": city.get("location_coords"),
        },
        "contacts": validated_data.get("contacts"),
        "dates": {
            "start": _to_datetime(dates.get("date_start")),
            "end": _to_datetime(dates.get("date_end")),
            "display": dates.get("date_display"),
            "orari": dates.get("orari"),
        },
        "batch_file": validated_data.get("batch_file"),
        "area": "staging",
        "status": "SCRAPED",
        "scraped_at": _to_datetime(validated_data.get("scraped_at")),
        "created_at": now,
        "spider": spider,
        "_raw": validated_data.get("raw_data"),
        "is_active": False,
    }


def upsert_events(docs: list[dict]) -> int:
    """
    Upsert batch di documenti evento per uuid (insert o update).

    Ritorna il numero totale di documenti scritti.
    """
    collection = get_collection(COLLECTION)
    if collection is None:
        return 0

    ops = [
        UpdateOne({"uuid": doc["uuid"]}, {"$set": doc}, upsert=True)
        for doc in docs
        if doc.get("uuid")
    ]
    if not ops:
        return 0

    result = collection.bulk_write(ops, ordered=False)
    written = result.upserted_count + result.modified_count
    logger.info("MongoDB upsert: %d documenti scritti in %s", written, COLLECTION)
    return written
