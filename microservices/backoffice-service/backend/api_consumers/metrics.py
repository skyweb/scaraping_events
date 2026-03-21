"""
Metriche Prometheus per API Consumers.

Esportate via django_prometheus su /metrics.
"""

from prometheus_client import Counter

# Autenticazione consumer
api_consumer_auth_total = Counter(
    "api_consumer_auth_total",
    "Autenticazioni consumer API",
    ["consumer", "plan", "auth_type", "status"],
)

# Accessi negati per scadenza
api_consumer_expired_total = Counter(
    "api_consumer_expired_total",
    "Accessi negati per consumer scaduto",
    ["consumer", "plan", "auth_type"],
)
