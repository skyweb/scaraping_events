"""
Preprocessing hooks per generare 2 schema OpenAPI separati:
- Pubblico: /api/v1/events/, /version/
- Interno: tutto il resto
"""


def public_endpoint_filter(endpoints: list) -> list:
    """Filtra solo gli endpoint pubblici: /api/v1/events/ e /version/."""
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path.startswith("/api/v1/events/") or path.startswith("/version")
    ]


def internal_endpoint_filter(endpoints: list) -> list:
    """Restituisce tutti gli endpoint (interni + pubblici)."""
    return endpoints