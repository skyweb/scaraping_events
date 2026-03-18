#!/bin/sh
# =============================================================================
# APISIX init-routes.sh — Configurazione dichiarativa route/upstream
# Eseguito dal container apisix-init (one-shot) al primo avvio.
#
# Flusso:
#   Browser → APISIX (TLS + OIDC/JWT) → upstream
#
# APISIX è l'unico entry point: gestisce TLS termination, autenticazione
# OIDC/JWT, e reverse proxy verso tutti i servizi.
# =============================================================================
set -e

ADMIN_URL="http://apisix:9180/apisix/admin"
API_KEY="apisix-dev-admin-key"
DOMAIN="${DOMAIN:-127.0.0.1.nip.io}"
KC_SECRET="${KEYCLOAK_BACKOFFICE_CLIENT_SECRET:-CHANGE_ME_BACKOFFICE_SECRET}"
KC_PUBLIC="https://auth.${DOMAIN}/realms/today-events"

# ---------------------------------------------------------------------------
# Attendi che APISIX Admin API sia pronto
# ---------------------------------------------------------------------------
echo "Attendo APISIX admin API..."
until curl -sf -o /dev/null -H "X-API-KEY: ${API_KEY}" "${ADMIN_URL}/routes"; do
    sleep 2
    echo "  ...attendo"
done
echo "APISIX pronto."

# ---------------------------------------------------------------------------
# Helper: PUT su Admin API
# ---------------------------------------------------------------------------
put() {
    local path="$1" data="$2" name="$3"
    echo "  Configuro ${name}..."
    curl -sf -X PUT \
        -H "X-API-KEY: ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "${data}" \
        "${ADMIN_URL}${path}" > /dev/null
}

# ======================= CERTIFICATO SSL =====================================
echo ""
echo "=== Certificato SSL ==="

CERT=$(cat /certs/_wildcard.127.0.0.1.nip.io+1.pem | awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}')
KEY=$(cat /certs/_wildcard.127.0.0.1.nip.io+1-key.pem | awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}')

put "/ssls/1" "{
    \"cert\": \"${CERT}\",
    \"key\": \"${KEY}\",
    \"snis\": [\"*.${DOMAIN}\", \"${DOMAIN}\"]
}" "SSL wildcard certificate"

# ======================= HTTP → HTTPS REDIRECT ===============================
echo ""
echo "=== Global rules ==="

put "/global_rules/1" '{
    "plugins": {
        "serverless-pre-function": {
            "phase": "rewrite",
            "functions": ["return function(conf, ctx) if ngx.var.server_port == \"80\" and ngx.var.uri ~= \"/_internal/oidc-discovery\" then ngx.header[\"Location\"] = \"https://\" .. ngx.var.host .. ngx.var.request_uri; return ngx.exit(301) end end"]
        }
    }
}' "HTTP→HTTPS redirect"

# ======================= UPSTREAMS ==========================================
echo ""
echo "=== Upstreams ==="

put "/upstreams/1" '{
    "name": "backoffice",
    "type": "roundrobin",
    "nodes": {"backoffice:8000": 1},
    "pass_host": "node"
}' "backoffice (Django :8000)"

put "/upstreams/2" '{
    "name": "keycloak",
    "type": "roundrobin",
    "nodes": {"keycloak:8080": 1},
    "pass_host": "rewrite",
    "upstream_host": "keycloak:8080"
}' "keycloak (interno :8080)"

put "/upstreams/3" '{
    "name": "grafana",
    "type": "roundrobin",
    "nodes": {"grafana:3001": 1},
    "pass_host": "node"
}' "grafana (:3001)"

put "/upstreams/4" '{
    "name": "prometheus",
    "type": "roundrobin",
    "nodes": {"prometheus:9090": 1},
    "pass_host": "node"
}' "prometheus (:9090)"

put "/upstreams/5" '{
    "name": "flower",
    "type": "roundrobin",
    "nodes": {"flower:5555": 1},
    "pass_host": "node"
}' "flower (:5555)"

put "/upstreams/6" '{
    "name": "sonarqube",
    "type": "roundrobin",
    "nodes": {"sonarqube:9000": 1},
    "pass_host": "node"
}' "sonarqube (:9000)"

put "/upstreams/7" '{
    "name": "redis-exporter",
    "type": "roundrobin",
    "nodes": {"redis-exporter:9121": 1},
    "pass_host": "node"
}' "redis-exporter (:9121)"

put "/upstreams/8" '{
    "name": "celery-exporter",
    "type": "roundrobin",
    "nodes": {"celery-exporter:9808": 1},
    "pass_host": "node"
}' "celery-exporter (:9808)"

put "/upstreams/9" '{
    "name": "airflow",
    "type": "roundrobin",
    "nodes": {"airflow-webserver:8080": 1},
    "pass_host": "node"
}' "airflow (:8080)"

put "/upstreams/10" '{
    "name": "apisix-dashboard",
    "type": "roundrobin",
    "nodes": {"apisix-dashboard:9000": 1},
    "pass_host": "node"
}' "apisix-dashboard (:9000)"

put "/upstreams/11" '{
    "name": "scrapyd",
    "type": "roundrobin",
    "nodes": {"dev-scrapyd:6800": 1},
    "pass_host": "node"
}' "scrapyd (:6800)"

put "/upstreams/12" '{
    "name": "loki",
    "type": "roundrobin",
    "nodes": {"loki:3100": 1},
    "pass_host": "node"
}' "loki (:3100)"

put "/upstreams/13" '{
    "name": "minio-console",
    "type": "roundrobin",
    "nodes": {"minio:9001": 1},
    "pass_host": "node"
}' "minio-console (:9001)"

put "/upstreams/14" '{
    "name": "minio-s3",
    "type": "roundrobin",
    "nodes": {"minio:9000": 1},
    "pass_host": "node"
}' "minio-s3 (:9000)"

# ======================= ROUTE INTERNA: OIDC DISCOVERY ======================
# KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true → Keycloak restituisce:
#   - URL pubblici per browser (authorization, end_session) → https://auth.DOMAIN
#   - URL interni per server (token, userinfo, jwks)       → http://keycloak:8080
# Questo avviene impostando X-Forwarded-Host/Proto/Port interni.
# ============================================================================
echo ""
echo "=== Route interna ==="

DISCOVERY_URL="http://127.0.0.1:9080/_internal/oidc-discovery"

put "/routes/100" '{
    "name": "internal-oidc-discovery",
    "uri": "/_internal/oidc-discovery",
    "upstream_id": "2",
    "plugins": {
        "proxy-rewrite": {
            "uri": "/realms/today-events/.well-known/openid-configuration",
            "host": "keycloak:8080",
            "headers": {
                "set": {
                    "X-Forwarded-Host": "keycloak:8080",
                    "X-Forwarded-Proto": "http",
                    "X-Forwarded-Port": "8080"
                }
            }
        }
    }
}' "oidc-discovery proxy"

# ======================= ROUTE DIRETTE (no auth) ============================
echo ""
echo "=== Route dirette (no auth) ==="

# --- Keycloak (Identity Provider, non protetto da SSO) ---
put "/routes/300" "{
    \"name\": \"keycloak-proxy\",
    \"host\": \"auth.${DOMAIN}\",
    \"uri\": \"/*\",
    \"upstream_id\": \"2\",
    \"plugins\": {
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\"
                }
            }
        }
    }
}" "keycloak (no auth)"

# --- MinIO Console (WebSocket + CSP override per Object Browser) ---
put "/routes/301" "{
    \"name\": \"minio-console-proxy\",
    \"host\": \"minio.${DOMAIN}\",
    \"uri\": \"/*\",
    \"upstream_id\": \"13\",
    \"enable_websocket\": true,
    \"plugins\": {
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\"
                }
            }
        },
        \"response-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"Content-Security-Policy\": \"default-src 'self' 'unsafe-eval' 'unsafe-inline'; script-src 'self' https://unpkg.com; connect-src 'self' https://unpkg.com wss://minio.${DOMAIN}; font-src 'self' data:;\"
                }
            }
        }
    }
}" "minio console (no auth, websocket)"

# --- MinIO Console WebSocket (priority alta, rimuove Origin per CheckOrigin) ---
put "/routes/304" "{
    \"name\": \"minio-console-ws\",
    \"host\": \"minio.${DOMAIN}\",
    \"uri\": \"/ws/*\",
    \"priority\": 10,
    \"upstream_id\": \"13\",
    \"enable_websocket\": true,
    \"plugins\": {
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\",
                    \"Origin\": \"\"
                }
            }
        },
        \"response-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"Content-Security-Policy\": \"default-src 'self' 'unsafe-eval' 'unsafe-inline'; script-src 'self' https://unpkg.com; connect-src 'self' https://unpkg.com wss://minio.${DOMAIN}; font-src 'self' data:;\"
                }
            }
        }
    }
}" "minio console WS"

# --- MinIO S3 API ---
put "/routes/302" "{
    \"name\": \"minio-s3-proxy\",
    \"host\": \"s3.${DOMAIN}\",
    \"uri\": \"/*\",
    \"upstream_id\": \"14\",
    \"plugins\": {
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\"
                }
            }
        }
    }
}" "minio S3 API (no auth)"

# --- Backoffice public (API, static, media, docs, frontend — no SSO) ---
put "/routes/303" "{
    \"name\": \"backoffice-public\",
    \"host\": \"backoffice.${DOMAIN}\",
    \"uri\": \"/*\",
    \"upstream_id\": \"1\",
    \"plugins\": {
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\"
                }
            }
        }
    }
}" "backoffice public (no auth)"

# ======================= ROUTE API (JWT bearer) =============================
echo ""
echo "=== Route API ==="

put "/routes/10" "{
    \"name\": \"api-external-jwt\",
    \"host\": \"backoffice.${DOMAIN}\",
    \"uri\": \"/api/external/*\",
    \"priority\": 10,
    \"upstream_id\": \"1\",
    \"plugins\": {
        \"openid-connect\": {
            \"client_id\": \"backoffice-admin\",
            \"client_secret\": \"${KC_SECRET}\",
            \"discovery\": \"${DISCOVERY_URL}\",
            \"issuer\": \"${KC_PUBLIC}\",
            \"bearer_only\": true,
            \"realm\": \"today-events\",
            \"ssl_verify\": false
        },
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\"
                }
            }
        }
    }
}" "api-external (JWT bearer)"

# ======================= ROUTE SSO (OIDC via Keycloak) ======================
# Helper: crea route con plugin openid-connect.
# Parametri: route_id, name, host, uri, upstream_id, redirect_uri
# Il logout_path viene derivato dal prefisso URI.
# ============================================================================
echo ""
echo "=== Route SSO ==="

oidc_route() {
    local id="$1" name="$2" host="$3" uri="$4" upstream_id="$5" redirect_uri="$6"
    local uri_prefix="${uri%\*}"
    local logout_path="${uri_prefix}sso-logout"
    # Per URI tipo /admin/* aggiungi anche /admin (senza slash)
    local uri_bare="${uri_prefix%/}"
    local uris_json="\"${uri}\""
    if [ -n "${uri_bare}" ] && [ "${uri_bare}" != "" ] && [ "${uri}" != "/*" ]; then
        uris_json="\"${uri_bare}\", \"${uri}\""
    fi

    put "/routes/${id}" "{
        \"name\": \"${name}\",
        \"host\": \"${host}\",
        \"uris\": [${uris_json}],
        \"upstream_id\": \"${upstream_id}\",
        \"plugins\": {
            \"openid-connect\": {
                \"client_id\": \"backoffice-admin\",
                \"client_secret\": \"${KC_SECRET}\",
                \"discovery\": \"${DISCOVERY_URL}\",
                \"issuer\": \"${KC_PUBLIC}\",
                \"scope\": \"openid profile email\",
                \"bearer_only\": false,
                \"realm\": \"today-events\",
                \"redirect_uri\": \"${redirect_uri}\",
                \"logout_path\": \"${logout_path}\",
                \"post_logout_redirect_uri\": \"https://${host}/\",
                \"set_userinfo_header\": true,
                \"set_id_token_header\": true,
                \"set_access_token_header\": true,
                \"access_token_in_authorization_header\": false,
                \"ssl_verify\": false,
                \"session\": {
                    \"secret\": \"apisix-session-secret-dev-32char!\"
                }
            },
            \"proxy-rewrite\": {
                \"headers\": {
                    \"set\": {
                        \"X-Forwarded-Proto\": \"https\"
                    }
                }
            }
        }
    }" "${name}"
}

# Variante Grafana: estrae email da X-Userinfo → X-Auth-Request-Email (auth proxy)
oidc_route_grafana() {
    local id="$1" name="$2" host="$3" upstream_id="$4" redirect_uri="$5"

    put "/routes/${id}" "{
        \"name\": \"${name}\",
        \"host\": \"${host}\",
        \"uri\": \"/*\",
        \"upstream_id\": \"${upstream_id}\",
        \"enable_websocket\": true,
        \"plugins\": {
            \"openid-connect\": {
                \"client_id\": \"backoffice-admin\",
                \"client_secret\": \"${KC_SECRET}\",
                \"discovery\": \"${DISCOVERY_URL}\",
                \"issuer\": \"${KC_PUBLIC}\",
                \"scope\": \"openid profile email\",
                \"bearer_only\": false,
                \"realm\": \"today-events\",
                \"redirect_uri\": \"${redirect_uri}\",
                \"logout_path\": \"/sso-logout\",
                \"post_logout_redirect_uri\": \"https://${host}/\",
                \"set_userinfo_header\": true,
                \"set_id_token_header\": true,
                \"set_access_token_header\": true,
                \"access_token_in_authorization_header\": false,
                \"ssl_verify\": false,
                \"session\": {
                    \"secret\": \"apisix-session-secret-dev-32char!\"
                }
            },
            \"serverless-post-function\": {
                \"phase\": \"rewrite\",
                \"functions\": [\"return function(conf, ctx) local cjson = require('cjson.safe'); local h = ngx.req.get_headers()['X-Userinfo']; if h then local decoded = ngx.decode_base64(h); if decoded then local d = cjson.decode(decoded); if d and d.email then ngx.req.set_header('X-Auth-Request-Email', d.email) end end end end\"]
            },
            \"proxy-rewrite\": {
                \"headers\": {
                    \"set\": {
                        \"X-Forwarded-Proto\": \"https\"
                    }
                }
            }
        }
    }" "${name}"
}

# --- Backoffice Django Admin (/admin/*) ---
oidc_route 200 "backoffice-admin-sso" \
    "backoffice.${DOMAIN}" "/admin/*" 1 \
    "https://backoffice.${DOMAIN}/admin/callback"

# --- Grafana (auth proxy: X-Auth-Request-Email) ---
oidc_route_grafana 201 "grafana-sso" \
    "grafana.${DOMAIN}" 3 \
    "https://grafana.${DOMAIN}/callback"

# --- Prometheus ---
oidc_route 202 "prometheus-sso" \
    "prometheus.${DOMAIN}" "/*" 4 \
    "https://prometheus.${DOMAIN}/callback"

# --- Flower ---
oidc_route 203 "flower-sso" \
    "flower.${DOMAIN}" "/*" 5 \
    "https://flower.${DOMAIN}/callback"

# --- SonarQube ---
oidc_route 204 "sonarqube-sso" \
    "sonarqube.${DOMAIN}" "/*" 6 \
    "https://sonarqube.${DOMAIN}/callback"

# --- Redis Exporter ---
oidc_route 205 "redis-exporter-sso" \
    "redis-exporter.${DOMAIN}" "/*" 7 \
    "https://redis-exporter.${DOMAIN}/callback"

# --- Celery Exporter ---
oidc_route 206 "celery-exporter-sso" \
    "celery-exporter.${DOMAIN}" "/*" 8 \
    "https://celery-exporter.${DOMAIN}/callback"

# --- Airflow static assets (no OIDC, evita race condition redirect) ---
put "/routes/305" "{
    \"name\": \"airflow-static\",
    \"host\": \"airflow.${DOMAIN}\",
    \"uri\": \"/static/*\",
    \"priority\": 10,
    \"upstream_id\": \"9\",
    \"plugins\": {
        \"proxy-rewrite\": {
            \"headers\": {
                \"set\": {
                    \"X-Forwarded-Proto\": \"https\"
                }
            }
        }
    }
}" "airflow static (no auth)"

# --- Airflow (auth proxy: X-Auth-Request-Email per AUTH_REMOTE_USER) ---
oidc_route_grafana 207 "airflow-sso" \
    "airflow.${DOMAIN}" 9 \
    "https://airflow.${DOMAIN}/callback"

# --- APISIX Dashboard ---
oidc_route 208 "apisix-dashboard-sso" \
    "apisix-dashboard.${DOMAIN}" "/*" 10 \
    "https://apisix-dashboard.${DOMAIN}/callback"

# --- Scrapyd ---
oidc_route 209 "scrapyd-sso" \
    "scrapyd.${DOMAIN}" "/*" 11 \
    "https://scrapyd.${DOMAIN}/callback"

# --- Loki ---
oidc_route 210 "loki-sso" \
    "loki.${DOMAIN}" "/*" 12 \
    "https://loki.${DOMAIN}/callback"

# ======================= RIEPILOGO ==========================================
echo ""
echo "=== Route APISIX configurate ==="
curl -sf -H "X-API-KEY: ${API_KEY}" "${ADMIN_URL}/routes" \
    | sed 's/},/},\n/g' | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"//' \
    | while read name; do echo "  - ${name}"; done
echo ""
echo "Done."
