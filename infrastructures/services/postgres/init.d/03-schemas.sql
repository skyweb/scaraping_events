-- Creazione schemi PostgreSQL custom nel database principale.
-- Eseguito automaticamente al primo avvio (volume vuoto).
-- Tutti gli schemi sono nel DB principale (POSTGRES_DB = today_events).

-- Schema per gli eventi e viste aggregate (app: events, scraping)
CREATE SCHEMA IF NOT EXISTS events_data;

-- Schema per i dati ISTAT dei comuni italiani (app: comuni_istat)
CREATE SCHEMA IF NOT EXISTS comuni;
CREATE SCHEMA IF NOT EXISTS comuni_istat;

-- Schema per le appartenenze regionali (app: comuni_italiani)
CREATE SCHEMA IF NOT EXISTS comuni_italiani;

-- Assegna i permessi all'utente applicativo
GRANT ALL ON SCHEMA events_data TO CURRENT_USER;
GRANT ALL ON SCHEMA comuni TO CURRENT_USER;
GRANT ALL ON SCHEMA comuni_italiani TO CURRENT_USER;
