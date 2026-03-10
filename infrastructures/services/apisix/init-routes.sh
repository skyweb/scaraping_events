#!/bin/sh
# Script di inizializzazione route APISIX per dev
# Eseguito dal container apisix-init al primo avvio
# Configurazione dichiarativa: upstream + route via Admin API

set -e

ADMIN_URL="http://apisix:9180/apisix/admin"
API_KEY="apisix-dev-admin-key"
DOMAIN="${DOMAIN:-127.0.0.1.nip.io}"
KC_SECRET="${KEYCLOAK_BACKOFFICE_CLIENT_SECRET:-CHANGE_ME_BACKOFFICE_SECRET}"

# Endpoint Keycloak: interni per server-to-server, pubblici per redirect browser
KC_INTERNAL="http://keycloak:8080/realms/today-events"
KC_PUBLIC="https://keycloak.${DOMAIN}/realms/today-events"

# Attendi che APISIX sia pronto
echo "Attendo APISIX admin API..."
until curl -sf -o /dev/null -H "X-API-KEY: ${API_KEY}" "${ADMIN_URL}/routes"; do
    sleep 2
    echo "  ...attendo"
done
echo "APISIX pronto."

put() {
    local path="$1"
    local data="$2"
    local name="$3"
    echo "Configuro ${name}..."
    curl -sf -X PUT \
        -H "X-API-KEY: ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "${data}" \
        "${ADMIN_URL}${path}" > /dev/null
    echo "  OK"
}

# --- Upstream: backoffice Django ---
put "/upstreams/1" '{
    "name": "backoffice-upstream",
    "type": "roundrobin",
    "nodes": {"backoffice:8000": 1},
    "pass_host": "node"
}' "upstream backoffice"

# --- Upstream: Keycloak interno ---
put "/upstreams/2" '{
    "name": "keycloak-upstream",
    "type": "roundrobin",
    "nodes": {"keycloak:8080": 1},
    "pass_host": "node"
}' "upstream keycloak"

# --- Route 100: discovery OIDC interno ---
# Proxy al discovery di Keycloak con response-rewrite per sostituire
# gli endpoint server-to-server (token, userinfo, jwks, introspection)
# con URL interni, mantenendo quelli browser (authorization, end_session, issuer) pubblici.
# Necessario perché lua-resty-openidc usa SOLO gli endpoint dal discovery,
# ignorando quelli espliciti nella config del plugin openid-connect.
KC_PUBLIC_ESCAPED=$(echo "https://keycloak.${DOMAIN}" | sed 's/\./\\\\./g')
put "/routes/100" "{
    \"name\": \"internal-oidc-discovery\",
    \"uri\": \"/_internal/oidc-discovery\",
    \"upstream_id\": \"2\",
    \"plugins\": {
        \"proxy-rewrite\": {
            \"uri\": \"/realms/today-events/.well-known/openid-configuration\"
        },
        \"response-rewrite\": {
            \"filters\": [
                {
                    \"regex\": \"\\\"token_endpoint\\\":\\\\s*\\\"${KC_PUBLIC_ESCAPED}\",
                    \"replace\": \"\\\"token_endpoint\\\":\\\"http://keycloak:8080\",
                    \"scope\": \"global\"
                },
                {
                    \"regex\": \"\\\"userinfo_endpoint\\\":\\\\s*\\\"${KC_PUBLIC_ESCAPED}\",
                    \"replace\": \"\\\"userinfo_endpoint\\\":\\\"http://keycloak:8080\",
                    \"scope\": \"global\"
                },
                {
                    \"regex\": \"\\\"jwks_uri\\\":\\\\s*\\\"${KC_PUBLIC_ESCAPED}\",
                    \"replace\": \"\\\"jwks_uri\\\":\\\"http://keycloak:8080\",
                    \"scope\": \"global\"
                },
                {
                    \"regex\": \"\\\"introspection_endpoint\\\":\\\\s*\\\"${KC_PUBLIC_ESCAPED}\",
                    \"replace\": \"\\\"introspection_endpoint\\\":\\\"http://keycloak:8080\",
                    \"scope\": \"global\"
                }
            ]
        }
    }
}" "route internal-oidc-discovery"

# URL discovery interno per i plugin openid-connect
DISCOVERY_URL="http://127.0.0.1:9080/_internal/oidc-discovery"

# --- Route 1: gateway-admin — /admin/* con OIDC (browser SSO) ---
# Il discovery viene servito dalla route interna con URL misti:
# - authorization/end_session/issuer = pubblici (redirect browser)
# - token/userinfo/jwks = interni (server-to-server)
put "/routes/1" "{
    \"name\": \"gateway-admin\",
    \"uri\": \"/admin/*\",
    \"upstream_id\": \"1\",
    \"plugins\": {
        \"openid-connect\": {
            \"client_id\": \"backoffice-admin\",
            \"client_secret\": \"${KC_SECRET}\",
            \"discovery\": \"${DISCOVERY_URL}\",
            \"issuer\": \"${KC_PUBLIC}\",
            \"scope\": \"openid profile email\",
            \"bearer_only\": false,
            \"realm\": \"today-events\",
            \"redirect_uri\": \"https://gateway.${DOMAIN}/admin/callback\",
            \"logout_path\": \"/admin/sso-logout\",
            \"post_logout_redirect_uri\": \"https://gateway.${DOMAIN}/admin/\",
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
}" "route gateway-admin"

# --- Route 2: gateway-static — /static/* senza auth ---
put "/routes/2" '{
    "name": "gateway-static",
    "uri": "/static/*",
    "upstream_id": "1",
    "plugins": {}
}' "route gateway-static"

# --- Route 3: api-public — /api/public/* senza auth ---
put "/routes/3" '{
    "name": "api-public",
    "uri": "/api/public/*",
    "priority": 10,
    "upstream_id": "1",
    "plugins": {
        "cors": {
            "allow_origins": "*",
            "allow_methods": "GET,HEAD,OPTIONS",
            "allow_headers": "Content-Type,Authorization",
            "max_age": 3600
        }
    }
}' "route api-public"

# --- Route 4: api-external — /api/external/* con JWT bearer (M2M scraper/airflow) ---
put "/routes/4" "{
    \"name\": \"api-external\",
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
}" "route api-external"

# --- Route 5: gateway-api — /api/* con OIDC (browser SSO per docs/Scalar) ---
put "/routes/5" "{
    \"name\": \"gateway-api\",
    \"uri\": \"/api/*\",
    \"upstream_id\": \"1\",
    \"plugins\": {
        \"openid-connect\": {
            \"client_id\": \"backoffice-admin\",
            \"client_secret\": \"${KC_SECRET}\",
            \"discovery\": \"${DISCOVERY_URL}\",
            \"issuer\": \"${KC_PUBLIC}\",
            \"scope\": \"openid profile email\",
            \"bearer_only\": false,
            \"realm\": \"today-events\",
            \"redirect_uri\": \"https://gateway.${DOMAIN}/api/callback\",
            \"set_userinfo_header\": true,
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
}" "route gateway-api"

echo ""
echo "=== Route APISIX configurate ==="
curl -sf -H "X-API-KEY: ${API_KEY}" "${ADMIN_URL}/routes" \
    | sed 's/},/},\n/g' | grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"//' \
    | while read name; do echo "  - ${name}"; done
echo "Done."
