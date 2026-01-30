import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchEtlRuns } from '../api/client'

function EtlRuns() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')

  const params: Record<string, string> = { page: String(page) }
  if (status) params.status = status

  const { data, isLoading, error } = useQuery({
    queryKey: ['etl-runs', params],
    queryFn: () => fetchEtlRuns(params),
  })

  if (error) return <div className="error">Errore nel caricamento</div>

  const totalPages = data ? Math.ceil(data.count / 25) : 0

  return (
    <>
      <h1>ETL Runs</h1>

      <div className="filters">
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
          <option value="">Tutti gli stati</option>
          <option value="success">Success</option>
          <option value="running">Running</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <div className="card">
        {isLoading ? (
          <div className="loading">Caricamento...</div>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Tipo</th>
                  <th>Sorgente</th>
                  <th>Stato</th>
                  <th>Staging</th>
                  <th>Inseriti</th>
                  <th>Aggiornati</th>
                  <th>Invariati</th>
                  <th>Durata</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((run) => (
                  <tr key={run.id}>
                    <td>{run.id}</td>
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
                    <td>{run.unchanged_count}</td>
                    <td>
                      {run.duration_seconds
                        ? `${Math.round(run.duration_seconds)}s`
                        : 'N/D'}
                    </td>
                    <td>{new Date(run.started_at).toLocaleString('it-IT')}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="pagination">
                <button onClick={() => setPage(p => p - 1)} disabled={page === 1}>
                  Precedente
                </button>
                <span style={{ padding: '8px 16px' }}>
                  Pagina {page} di {totalPages}
                </span>
                <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages}>
                  Successiva
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

export default EtlRuns
