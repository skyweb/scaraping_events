import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchEtlErrors } from '../api/client'

function EtlErrors() {
  const [page, setPage] = useState(1)
  const [errorType, setErrorType] = useState('')

  const params: Record<string, string> = { page: String(page) }
  if (errorType) params.error_type = errorType

  const { data, isLoading, error } = useQuery({
    queryKey: ['etl-errors', params],
    queryFn: () => fetchEtlErrors(params),
  })

  if (error) return <div className="error">Errore nel caricamento</div>

  const totalPages = data ? Math.ceil(data.count / 25) : 0

  return (
    <>
      <h1>ETL Errors</h1>

      <div className="filters">
        <select value={errorType} onChange={(e) => { setErrorType(e.target.value); setPage(1) }}>
          <option value="">Tutti i tipi</option>
          <option value="missing_required_fields">Missing Required Fields</option>
          <option value="invalid_json">Invalid JSON</option>
          <option value="db_insert_error">DB Insert Error</option>
        </select>
      </div>

      <div className="card">
        {isLoading ? (
          <div className="loading">Caricamento...</div>
        ) : data?.results.length === 0 ? (
          <p style={{ textAlign: 'center', color: '#666', padding: '40px' }}>
            Nessun errore trovato
          </p>
        ) : (
          <>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Tipo Errore</th>
                  <th>Sorgente</th>
                  <th>File JSON</th>
                  <th>Messaggio</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((err) => (
                  <tr key={err.id}>
                    <td>{err.id}</td>
                    <td>
                      <span className="badge badge-error">
                        {err.error_type}
                      </span>
                    </td>
                    <td>{err.source || 'N/D'}</td>
                    <td style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {err.json_file || 'N/D'}
                    </td>
                    <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {err.error_message || 'N/D'}
                    </td>
                    <td>{new Date(err.created_at).toLocaleString('it-IT')}</td>
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

export default EtlErrors
