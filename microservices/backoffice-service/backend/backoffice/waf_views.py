"""
API per gestione regole Coraza WAF via APISIX Admin API.

Permette di leggere, aggiungere, rimuovere e testare le regole WAF
senza accedere direttamente ad APISIX.
"""

import json
import logging

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

logger = logging.getLogger(__name__)

APISIX_ADMIN_URL = "http://apisix:9180/apisix/admin"
APISIX_API_KEY = "apisix-dev-admin-key"
GLOBAL_RULE_ID = "2"


def _apisix_headers():
    return {
        "X-API-KEY": APISIX_API_KEY,
        "Content-Type": "application/json",
    }


def _get_current_rules():
    """Legge le regole WAF correnti da APISIX."""
    try:
        r = requests.get(
            f"{APISIX_ADMIN_URL}/global_rules/{GLOBAL_RULE_ID}",
            headers=_apisix_headers(),
            timeout=5,
        )
        if r.status_code == 404:
            return []
        r.raise_for_status()
        conf_str = r.json().get("value", {}).get("plugins", {}).get("coraza-filter", {}).get("conf", "{}")
        conf = json.loads(conf_str)
        directives = conf.get("directives_map", {}).get("default", [])
        # Filtra solo le SecRule (non le direttive di configurazione)
        rules = []
        config_directives = []
        for d in directives:
            if d.startswith("SecRule"):
                rules.append(d)
            else:
                config_directives.append(d)
        return {"rules": rules, "config": config_directives}
    except Exception as e:
        logger.error("Errore lettura regole WAF: %s", e)
        return None


def _save_rules(config_directives, rules):
    """Salva le regole WAF su APISIX."""
    conf = {
        "directives_map": {
            "default": config_directives + rules,
        },
        "default_directives": "default",
    }
    r = requests.put(
        f"{APISIX_ADMIN_URL}/global_rules/{GLOBAL_RULE_ID}",
        headers=_apisix_headers(),
        json={
            "plugins": {
                "coraza-filter": {
                    "conf": json.dumps(conf),
                },
            },
        },
        timeout=5,
    )
    r.raise_for_status()
    return r.status_code


@extend_schema(
    summary="Lista regole WAF",
    description="Restituisce tutte le regole Coraza WAF attive su APISIX, divise tra configurazione base e SecRule.",
    tags=["WAF"],
    responses={
        200: {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "rules_count": {"type": "integer"},
                "config": {"type": "array", "items": {"type": "string"}},
                "rules": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    examples=[
        OpenApiExample(
            "WAF attivo con regole",
            value={
                "enabled": True,
                "rules_count": 6,
                "config": [
                    "SecRuleEngine On",
                    "SecRequestBodyAccess On",
                    "SecAuditLog /dev/stdout",
                ],
                "rules": [
                    'SecRule ARGS|ARGS_NAMES "@rx (?i)(union.*select)" "id:1001,phase:2,deny,status:403,log,msg:SQL Injection detected"',
                    'SecRule ARGS|ARGS_NAMES "@rx (?i)(<script)" "id:1002,phase:2,deny,status:403,log,msg:XSS detected"',
                ],
            },
            response_only=True,
        ),
    ],
)
@api_view(["GET"])
@permission_classes([IsAdminUser])
def waf_rules_list(request):
    """Lista tutte le regole WAF attive."""
    data = _get_current_rules()
    if data is None:
        return Response({"enabled": False, "rules_count": 0, "config": [], "rules": []})
    return Response({
        "enabled": True,
        "rules_count": len(data["rules"]),
        "config": data["config"],
        "rules": data["rules"],
    })


@extend_schema(
    summary="Aggiungi regola WAF",
    description="""Aggiunge una nuova SecRule Coraza. La regola viene applicata immediatamente a tutto il traffico.

**Formato regola:**
```
SecRule VARIABILE "@OPERATORE pattern" "id:NNNN,phase:N,deny,status:403,log,msg:Descrizione"
```

**Variabili comuni:**
- `ARGS|ARGS_NAMES` — parametri query string e body
- `REQUEST_URI` — URL della richiesta
- `REQUEST_HEADERS:Header-Name` — header HTTP specifico
- `REQUEST_BODY` — corpo della richiesta

**Operatori:**
- `@rx` — regex
- `@contains` — contiene stringa
- `@eq` — uguale

**Fasi:**
- `phase:1` — request headers (prima del body)
- `phase:2` — request body
- `phase:3` — response headers
- `phase:4` — response body
""",
    tags=["WAF"],
    request={
        "application/json": {
            "type": "object",
            "required": ["rule"],
            "properties": {
                "rule": {"type": "string", "description": "SecRule completa"},
            },
        },
    },
    responses={201: {"type": "object", "properties": {"message": {"type": "string"}, "rules_count": {"type": "integer"}}}},
    examples=[
        OpenApiExample(
            "Blocca SQL Injection",
            value={"rule": 'SecRule ARGS|ARGS_NAMES "@rx (?i)(union.*select|drop\\s+table)" "id:2001,phase:2,deny,status:403,log,msg:Custom SQL Injection rule"'},
            request_only=True,
        ),
        OpenApiExample(
            "Blocca User-Agent specifico",
            value={"rule": 'SecRule REQUEST_HEADERS:User-Agent "@rx (?i)(sqlmap|nikto|nmap)" "id:2002,phase:1,deny,status:403,log,msg:Scanner blocked"'},
            request_only=True,
        ),
        OpenApiExample(
            "Blocca upload file pericolosi",
            value={"rule": 'SecRule REQUEST_HEADERS:Content-Type "@rx (?i)(application/x-php|text/x-php)" "id:2003,phase:1,deny,status:403,log,msg:PHP upload blocked"'},
            request_only=True,
        ),
    ],
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def waf_rules_add(request):
    """Aggiunge una nuova regola WAF."""
    rule = request.data.get("rule", "").strip()
    if not rule.startswith("SecRule"):
        return Response(
            {"error": "La regola deve iniziare con 'SecRule'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = _get_current_rules()
    if data is None:
        return Response({"error": "WAF non configurato"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Verifica ID univoco
    import re
    match = re.search(r'id:(\d+)', rule)
    if match:
        new_id = match.group(1)
        for existing in data["rules"]:
            if f"id:{new_id}" in existing:
                return Response(
                    {"error": f"Una regola con id:{new_id} esiste gia'"},
                    status=status.HTTP_409_CONFLICT,
                )

    data["rules"].append(rule)
    _save_rules(data["config"], data["rules"])

    return Response(
        {"message": "Regola aggiunta", "rules_count": len(data["rules"])},
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="Rimuovi regola WAF",
    description="Rimuove una regola WAF per ID (es. id:1001). La rimozione e' immediata.",
    tags=["WAF"],
    parameters=[
        OpenApiParameter("rule_id", str, description="ID della regola (es. 1001)", required=True),
    ],
    responses={
        200: {"type": "object", "properties": {"message": {"type": "string"}, "rules_count": {"type": "integer"}}},
        404: {"type": "object", "properties": {"error": {"type": "string"}}},
    },
)
@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def waf_rules_delete(request, rule_id):
    """Rimuove una regola WAF per ID."""
    data = _get_current_rules()
    if data is None:
        return Response({"error": "WAF non configurato"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    original_count = len(data["rules"])
    data["rules"] = [r for r in data["rules"] if f"id:{rule_id}" not in r]

    if len(data["rules"]) == original_count:
        return Response({"error": f"Regola id:{rule_id} non trovata"}, status=status.HTTP_404_NOT_FOUND)

    _save_rules(data["config"], data["rules"])

    return Response({"message": f"Regola id:{rule_id} rimossa", "rules_count": len(data["rules"])})


@extend_schema(
    summary="Testa regola WAF",
    description="Valida una SecRule senza applicarla. Verifica che la sintassi sia corretta.",
    tags=["WAF"],
    request={
        "application/json": {
            "type": "object",
            "required": ["rule"],
            "properties": {
                "rule": {"type": "string"},
            },
        },
    },
    responses={
        200: {"type": "object", "properties": {"valid": {"type": "boolean"}, "rule": {"type": "string"}}},
        400: {"type": "object", "properties": {"valid": {"type": "boolean"}, "error": {"type": "string"}}},
    },
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def waf_rules_test(request):
    """Valida una regola WAF senza applicarla."""
    rule = request.data.get("rule", "").strip()

    if not rule.startswith("SecRule"):
        return Response(
            {"valid": False, "error": "La regola deve iniziare con 'SecRule'"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    import re
    if not re.search(r'id:\d+', rule):
        return Response(
            {"valid": False, "error": "La regola deve contenere un id (es. id:1001)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not re.search(r'phase:[1-4]', rule):
        return Response(
            {"valid": False, "error": "La regola deve specificare una fase (phase:1-4)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    required_parts = ["@rx", "@contains", "@eq", "@gt", "@lt", "@ge", "@le", "@pm", "@streq"]
    has_operator = any(op in rule for op in required_parts)
    if not has_operator:
        return Response(
            {"valid": False, "error": f"La regola deve contenere un operatore ({', '.join(required_parts[:4])}, ...)"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({"valid": True, "rule": rule})


@extend_schema(
    summary="Stato WAF (enable/disable)",
    description="Abilita o disabilita il WAF globalmente. Quando disabilitato, tutte le regole restano salvate ma non vengono applicate.",
    tags=["WAF"],
    request={
        "application/json": {
            "type": "object",
            "required": ["enabled"],
            "properties": {
                "enabled": {"type": "boolean", "description": "true=attiva, false=disattiva"},
            },
        },
    },
    responses={200: {"type": "object", "properties": {"enabled": {"type": "boolean"}, "message": {"type": "string"}}}},
    examples=[
        OpenApiExample("Abilita WAF", value={"enabled": True}, request_only=True),
        OpenApiExample("Disabilita WAF", value={"enabled": False}, request_only=True),
    ],
)
@api_view(["POST"])
@permission_classes([IsAdminUser])
def waf_toggle(request):
    """Abilita o disabilita il WAF."""
    enabled = request.data.get("enabled", True)

    if enabled:
        data = _get_current_rules()
        if data is None:
            return Response({"error": "WAF non configurato"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        # Assicura che SecRuleEngine sia On
        data["config"] = [d for d in data["config"] if not d.startswith("SecRuleEngine")]
        data["config"].insert(0, "SecRuleEngine On")
        _save_rules(data["config"], data["rules"])
        return Response({"enabled": True, "message": "WAF abilitato"})
    else:
        data = _get_current_rules()
        if data is None:
            return Response({"enabled": False, "message": "WAF gia' disabilitato"})
        data["config"] = [d for d in data["config"] if not d.startswith("SecRuleEngine")]
        data["config"].insert(0, "SecRuleEngine DetectionOnly")
        _save_rules(data["config"], data["rules"])
        return Response({"enabled": False, "message": "WAF in modalita' detection only (log senza blocco)"})
