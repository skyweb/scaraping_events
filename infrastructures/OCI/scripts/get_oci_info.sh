#!/bin/bash

echo "--- RECUPERO DATI OCI (Versione Corretta) ---"

# 1. Recupero Tenancy OCID (Dalla configurazione attuale)
# Usiamo 'get' invece di 'list'
TENANCY_OCID=$(oci iam tenancy get --tenancy-id $(grep -m 1 "tenancy" ~/.oci/config | cut -d'=' -f2 | tr -d ' ') --query "data.id" --raw-output)
echo "TENANCY OCID:     $TENANCY_OCID"

# 2. Recupero User OCID 
# Se 'list' fallisce per permessi, lo leggiamo dal config locale
USER_OCID=$(grep -m 1 "user" ~/.oci/config | cut -d'=' -f2 | tr -d ' ')
echo "USER OCID:        $USER_OCID"

# 3. Recupero Compartment OCID
echo ""
echo "ELENCO COMPARTMENT ATTIVI:"
oci iam compartment list --all --compartment-id-in-subtree true --access-level ACCESSIBLE --query "data[?\"lifecycle-state\" == 'ACTIVE'].{Name:name, State:\"lifecycle-state\", OCID:id}" --output table

# 4. Recupero dati dal file di configurazione locale
echo ""
echo "DATI CONFIGURAZIONE LOCALE (~/.oci/config):"
if [ -f ~/.oci/config ]; then
    echo "FINGERPRINT:  $(grep -m 1 "fingerprint" ~/.oci/config | cut -d'=' -f2 | tr -d ' ')"
    echo "KEY PATH:     $(grep -m 1 "key_file" ~/.oci/config | cut -d'=' -f2 | tr -d ' ')"
    echo "REGION:       $(grep -m 1 "region" ~/.oci/config | cut -d'=' -f2 | tr -d ' ')"
else
    echo "Errore: File ~/.oci/config non trovato."
fi

echo "------------------------"