#!/bin/sh
# Crea un utente Keycloak nel realm today-events e invia email di attivazione.
# Uso: ./kc-create-user.sh <email> <nome> <cognome> [ruoli...]
#   Esempio: ./kc-create-user.sh mario@example.com Mario Rossi admin web monitoring
#
# Richiede: curl, sed
# Il container Keycloak deve essere raggiungibile su http://keycloak:8080

set -e

EMAIL="${1:?Uso: $0 <email> <nome> <cognome> [ruoli...]}"
FIRST_NAME="${2:?Manca il nome}"
LAST_NAME="${3:?Manca il cognome}"
shift 3
ROLES="${*:-web}"

KC_URL="http://keycloak:8080"
REALM="today-events"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"

echo "Creo utente: ${EMAIL} (${FIRST_NAME} ${LAST_NAME})"
echo "Ruoli: ${ROLES}"
echo ""

# 1. Token admin
TOKEN=$(curl -sf -X POST "${KC_URL}/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${ADMIN_USER}&password=${ADMIN_PASS}&grant_type=password&client_id=admin-cli" \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "${TOKEN}" ]; then
    echo "ERRORE: impossibile ottenere token admin"
    exit 1
fi

AUTH="Authorization: Bearer ${TOKEN}"

# 2. Username dall'email (parte prima della @)
USERNAME=$(echo "${EMAIL}" | cut -d@ -f1)

# 3. Crea utente
STATUS=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  "${KC_URL}/admin/realms/${REALM}/users" \
  -H "${AUTH}" -H "Content-Type: application/json" \
  -d "{
    \"username\": \"${USERNAME}\",
    \"email\": \"${EMAIL}\",
    \"firstName\": \"${FIRST_NAME}\",
    \"lastName\": \"${LAST_NAME}\",
    \"enabled\": true,
    \"emailVerified\": false
  }")

if [ "${STATUS}" = "201" ]; then
    echo "Utente creato."
elif [ "${STATUS}" = "409" ]; then
    echo "Utente gia' esistente, aggiorno ruoli..."
else
    echo "ERRORE: creazione utente fallita (HTTP ${STATUS})"
    exit 1
fi

# 4. Trova user ID
USER_ID=$(curl -sf -H "${AUTH}" \
  "${KC_URL}/admin/realms/${REALM}/users?username=${USERNAME}&exact=true" \
  | sed -n 's/.*"id":"\([^"]*\)".*/\1/p' | head -1)

echo "User ID: ${USER_ID}"

# 5. Assegna ruoli
for ROLE_NAME in ${ROLES}; do
    # Trova role ID
    ROLE_JSON=$(curl -sf -H "${AUTH}" \
      "${KC_URL}/admin/realms/${REALM}/roles/${ROLE_NAME}" 2>/dev/null || echo "")

    if [ -z "${ROLE_JSON}" ]; then
        echo "  Ruolo '${ROLE_NAME}' non trovato, skip."
        continue
    fi

    ROLE_ID=$(echo "${ROLE_JSON}" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')

    curl -sf -o /dev/null -X POST \
      "${KC_URL}/admin/realms/${REALM}/users/${USER_ID}/role-mappings/realm" \
      -H "${AUTH}" -H "Content-Type: application/json" \
      -d "[{\"id\":\"${ROLE_ID}\",\"name\":\"${ROLE_NAME}\"}]"

    echo "  Ruolo '${ROLE_NAME}' assegnato."
done

# 6. Invia email di attivazione (execute actions: UPDATE_PASSWORD + VERIFY_EMAIL)
curl -sf -o /dev/null -X PUT \
  "${KC_URL}/admin/realms/${REALM}/users/${USER_ID}/execute-actions-email" \
  -H "${AUTH}" -H "Content-Type: application/json" \
  -d '["UPDATE_PASSWORD", "VERIFY_EMAIL"]'

echo ""
echo "Email di attivazione inviata a ${EMAIL}."
echo "L'utente ricevera' un link per impostare la password e verificare l'email."
