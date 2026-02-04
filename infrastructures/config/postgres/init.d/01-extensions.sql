-- Inizializzazione estensioni PostgreSQL con PostGIS

-- Abilita estensioni
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder;

-- Crea schema per gli eventi
CREATE SCHEMA IF NOT EXISTS events_data;
