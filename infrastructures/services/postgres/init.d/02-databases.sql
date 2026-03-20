-- Creazione database per i servizi che usano PostgreSQL separato dal DB principale.
-- Questo script viene eseguito automaticamente al primo avvio di postgres
-- (solo quando il volume è vuoto).
-- NB: il database principale (POSTGRES_DB) è già creato dall'immagine Docker.

-- n8n (workflow automation)
SELECT 'CREATE DATABASE n8n OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n') \gexec

-- Harbor (Docker Registry)
SELECT 'CREATE DATABASE harbor OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'harbor') \gexec

-- Keycloak (identity provider)
SELECT 'CREATE DATABASE keycloak OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak') \gexec

-- Backstage (developer portal)
SELECT 'CREATE DATABASE backstage OWNER ' || current_user
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'backstage') \gexec
