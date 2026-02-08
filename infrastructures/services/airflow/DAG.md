## Configurazione API Variables

Il DAG usa le **Airflow Variables** per le credenziali API (con fallback sulle variabili d'ambiente).

### Configurazione da UI (consigliato)

1. Accedi a Airflow: `http://localhost:8080`
2. Vai su `Admin` → `Variables`
3. Aggiungi le seguenti variabili:

| Key | Valore | Descrizione |
|-----|--------|-------------|
| `API_BASE_URL` | `http://backoffice:8000` | URL del servizio backoffice |
| `API_CLIENT_ID` | `airflow-client` | Client ID per autenticazione API |
| `API_CLIENT_SECRET` | `your-secret` | Client Secret per autenticazione API |

Le modifiche sono **immediate**, senza necessità di riavviare Airflow.

### Configurazione da CLI

```bash
# Imposta le variabili via CLI
docker exec events-airflow-webserver airflow variables set API_BASE_URL "http://backoffice:8000"
docker exec events-airflow-webserver airflow variables set API_CLIENT_ID "airflow-client"
docker exec events-airflow-webserver airflow variables set API_CLIENT_SECRET "your-secret"

# Verifica le variabili
docker exec events-airflow-webserver airflow variables list
docker exec events-airflow-webserver airflow variables get API_CLIENT_ID
```

### Fallback

Se le Variables non sono configurate, il DAG usa le variabili d'ambiente dal `.env`:
- `API_BASE_URL` → default: `http://backoffice:8000`
- `API_CLIENT_ID` → default: vuoto
- `API_CLIENT_SECRET` → default: vuoto

---

## Esecuzione manuale tramite Airflow CLI                                                                                                                                                                                                                                                                                                                                                                 
                                  
```bash                                                                                                                                                                                                                                                                                                                                                                          
# Entra nel container Airflow                                                                                                                                                                                                                                                                                                                                                                             
$ docker exec -it airflow-webserver bash                                                                                                                                                                                                                                                                                                                                                                    
                                                                                                                                                                                                                                                                                                                                                                                                            
# Testa il DAG per errori di sintassi                                                                                                                                                                                                                                                                                                                                                                     
$ airflow dags test etl_events_daily 2026-01-28                                                                                                                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                                                                                                                                                            
# Esegui un singolo task                                                                                                                                                                                                                                                                                                                                                                                  
$ airflow tasks test etl_events_daily truncate_staging 2026-01-28                                                                                                                                                                                                                                                                                                                                           
$ airflow tasks test etl_events_daily load_to_staging 2026-01-28                                                                                                                                                                                                                                                                                                                                            
```

## Esecuzione con filtro città (un solo task)                                                                                                                                                                                                                                                                                                                                                             
```bash
# Oppure via CLI:                                                                                                                                                                                                                                                                                                                                                                                         
$ airflow dags trigger etl_events_daily --conf '{"city": "milano"}'                                                                                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                                                                                                                            
# Oppure filtra per source specifico:                                                                                                                                                                                                                                                                                                                                                                     
$ airflow dags trigger etl_events_daily --conf '{"cities_today": "milano,roma"}'                                                                                                                                                                                                                                                                                                                            
$ airflow dags trigger etl_events_daily --conf '{"cities_zero": "milano"}'                                                                                                                                                                                                                                                                                                                                  
``` 

                                                                                                                                                                                                                                                                                                                                                                                                            
```bash
# Log del DAG processor
$ tail -f infrastructures/services/airflow/logs/dag_processor_manager/dag_processor_manager.log

# Log dei task (dalla directory logs di Airflow)
$ ls infrastructures/services/airflow/logs/
```

## testare le funzioni ETL direttamente:        

```python                                                                                                                                                                                                                                                                                                                                                                                                            
# Test load_json_to_staging                                                                                                                                                                                                                                                                                                                                                                               
from dags.scrape_events import load_json_to_staging                                                                                                                                                                                                                                                                                                                                                       
```

```bash
# Esegui solo Milano                                                                                                                                                                                                                                                                                                                                                                                      
$ docker exec -it events-airflow-webserver airflow dags trigger etl_events_daily --conf '{"city": "milano"}'                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                                        
# Test di un singolo task (senza salvare nel DB)                                                                                                                                                                                                                                                                                                                                                          
$ docker exec -it events-airflow-webserver airflow tasks test etl_events_daily truncate_staging 2026-01-2
```

Per eseguire solo il task scrape_zero_eu di Milano:                                                                                                                                                                                                                                                                                                                                                       
       
```bash                                                                                                                                                                                                                                                                                                                                                                                                     
# Test singolo task (non salva nel DB, utile per debug)                                                                                                                                                                                                                                                                                                                                                   
$ docker exec events-airflow-webserver airflow tasks test etl_events_daily process_milano.scrape_zero_eu 2026-01-28                                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                                                                                                                   
# Oppure run (salva nel DB)                                                                                                                                                                                                                                                                                                                                                                               
$ docker exec events-airflow-webserver airflow tasks run etl_events_daily process_milano.scrape_zero_eu 2026-01-28                                                                                                                                                                                                                                                                                          
```                                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                            
Se invece vuoi triggerare il DAG completo ma eseguire solo zero_eu per milano, usa la config:
      
```bash                                                                                                                                                                                                                                                                                                                                                                                                      
$ docker exec events-airflow-webserver airflow dags trigger etl_events_daily --conf '{"city": "milano", "cities_today": []}'                                                                                                                                                                                                                                                                                
```