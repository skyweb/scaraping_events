# PostgreSQL Backup & Restore (Docker)

Questo documento descrive come effettuare il dump del database e dello schema `events_data` direttamente dal container Docker.

## 1. Dump completo del database
Esegue il backup dell'intero database `today_events` (inclusi schema `public` di Airflow e schema `events_data`).

```bash
$ docker exec events-postgres pg_dump -U events today_events > full_dump.sql
```

## 2. Dump del solo schema `events_data`
Esegue il backup dei soli dati del progetto (tabelle eventi, funzioni e statistiche ETL), escludendo le tabelle di sistema di Airflow.

```bash
$ docker exec events-postgres pg_dump -U events -n events_data today_events > events_data_schema.sql
```

## 3. Backup compresso (Consigliato)
Per database di grandi dimensioni, è meglio comprimere l'output al volo.

```bash
$ docker exec events-postgres pg_dump -U events -n events_data today_events | gzip > events_data_schema.sql.gz
```

## 4. Ripristino (Restore)

### Ripristino da file SQL
```bash
$ cat events_data_schema.sql | docker exec -i events-postgres psql -U events -d today_events
```

### Ripristino da file compresso
```bash
$ gunzip -c events_data_schema.sql.gz | docker exec -i events-postgres psql -U events -d today_events
```

---

**Nota:** La password viene letta automaticamente se il container è avviato, altrimenti psql potrebbe richiederla (default: `events_secret_2026`).
