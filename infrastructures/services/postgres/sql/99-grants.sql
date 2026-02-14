-- =============================================================================
-- SCHEMA: Crea schema per gli eventi
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS events_data;
CREATE SCHEMA IF NOT EXISTS comuni_istat;
CREATE SCHEMA IF NOT EXISTS events_data;

-- =============================================================================
-- PERMESSI: permessi privileges allo user events
-- =============================================================================
GRANT ALL PRIVILEGES ON SCHEMA events_data TO events;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA events_data TO events;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA events_data TO events;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA events_data TO events;
