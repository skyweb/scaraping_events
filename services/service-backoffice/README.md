# Service Backoffice - Today Events

Questo servizio gestisce il pannello di amministrazione per Today Events, composto da un backend Django e un frontend React/Vite.

## Prerequisiti

Assicurati che l'infrastruttura principale (PostgreSQL) sia in esecuzione:

```bash
$ cd infrastructures
$ docker-compose up -d
```

## Quick Start (Sviluppo)

1. Spostati nella directory del servizio:
   ```bash
   $ cd services/service-backoffice
   ```

2. Avvia i container di sviluppo:
   ```bash
   $  docker compose -f docker-compose.dev.yml up -d
   ```

3. Verifica che i servizi siano attivi:
   ```bash
   $ docker compose -f docker-compose.dev.yml ps
   ```

4. lancio manuale
   ```bash
   $ export DJANGO_DEBUG=True
   $ export POSTGRES_HOST=localhost 
   ```

## Accesso ai Servizi

- **Frontend (Backoffice UI):** [http://localhost:3000](http://localhost:3000)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **Django Admin:** [http://localhost:8000/admin](http://localhost:8000/admin)

## Gestione Utenti (Django)

### Creare un Superuser

Per accedere all'interfaccia di amministrazione di Django o al Backoffice come amministratore, devi creare un superuser. Esegui questo comando mentre i container sono attivi:

```bash
docker exec -it backoffice-backend-dev python manage.py createsuperuser
```

Segui le istruzioni a schermo per impostare username, email e password.

## Comandi Utili

### Database Migrations

Applicare le migrazioni:
```bash
docker exec -it backoffice-backend-dev python manage.py migrate
```

Creare nuove migrazioni (dopo aver modificato i modelli):
```bash
docker exec -it backoffice-backend-dev python manage.py makemigrations
```

### Logs

Vedere i log del backend:
```bash
docker logs -f backoffice-backend-dev
```

Vedere i log del frontend:
```bash
docker logs -f backoffice-frontend-dev
```

## Struttura

- **backend/**: Applicazione Django (API + Admin)
- **frontend/**: Applicazione React/Vite (UI personalizzata)
- **docker-compose.dev.yml**: Configurazione Docker per l'ambiente di sviluppo
