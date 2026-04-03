# -*- coding: utf-8 -*-
"""
Client MongoDB lazy singleton.

Utilizzo:
    from backoffice.mongodb import get_collection
    col = get_collection("staging_events")
    col.insert_many(docs)

La connessione è opzionale: se MONGODB_URI non è configurato o MongoDB non è
raggiungibile, get_collection() ritorna None e il chiamante deve gestire il caso.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_client = None
_db = None


def get_collection(collection_name: str):
    """Ritorna la collection MongoDB, o None se non disponibile."""
    global _client, _db

    if _client is None:
        from django.conf import settings
        uri = getattr(settings, "MONGODB_URI", None)
        if not uri:
            return None
        try:
            from pymongo import MongoClient
            from pymongo.errors import ConnectionFailure
            _client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            # Verifica connessione al primo accesso
            _client.admin.command("ping")
            db_name = getattr(settings, "MONGODB_DB", "today_events")
            _db = _client[db_name]
            logger.info("MongoDB connesso: %s / %s", uri, db_name)
        except Exception as exc:
            logger.warning("MongoDB non disponibile, dual-write disabilitato: %s", exc)
            _client = None
            return None

    if _db is None:
        return None

    return _db[collection_name]
