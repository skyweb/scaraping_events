import { useQuery } from '@tanstack/react-query'
import { fetchDashboard } from '../api/client'

function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
  })

  if (isLoading) return <div className="loading">Caricamento...</div>
  if (error) return <div className="error">Errore nel caricamento dei dati</div>
  if (!data) return null

  return (
    <>
      <h1>Dashboard</h1>

      <div className="stats-grid">
        <div className="stat-card">
          <h3>{data.total_events.toLocaleString()}</h3>
          <p>Eventi Totali</p>
        </div>
        <div className="stat-card">
          <h3>{data.active_events.toLocaleString()}</h3>
          <p>Eventi Attivi</p>
        </div>
        <div className="stat-card">
          <h3>{data.staging_count.toLocaleString()}</h3>
          <p>In Staging</p>
        </div>
        <div className="stat-card">
          <h3>{Object.keys(data.events_by_city).length}</h3>
          <p>Citta</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <div className="card">
          <h2>Eventi per Citta</h2>
          <table>
            <thead>
              <tr>
                <th>Citta</th>
                <th>Eventi</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.events_by_city).map(([city, count]) => (
                <tr key={city}>
                  <td>{city || 'N/D'}</td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Eventi per Sorgente</h2>
          <table>
            <thead>
              <tr>
                <th>Sorgente</th>
                <th>Eventi</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.events_by_source).map(([source, count]) => (
                <tr key={source}>
                  <td>{source}</td>
                  <td>{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Ultimi ETL Runs</h2>
        <table>
          <thead>
            <tr>
              <th>Tipo</th>
              <th>Sorgente</th>
              <th>Stato</th>
              <th>Staging</th>
              <th>Inseriti</th>
              <th>Aggiornati</th>
              <th>Data</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_etl_runs.map((run) => (
              <tr key={run.id}>
                <td>{run.run_type}</td>
                <td>{run.source || 'N/D'}</td>
                <td>
                  <span className={`badge badge-${run.status}`}>
                    {run.status}
                  </span>
                </td>
                <td>{run.staging_count}</td>
                <td>{run.inserted_count}</td>
                <td>{run.updated_count}</td>
                <td>{new Date(run.started_at).toLocaleString('it-IT')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default Dashboard
