import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchEvents, fetchCities, fetchSources } from '../api/client'

function EventsList() {
  const [page, setPage] = useState(1)
  const [city, setCity] = useState('')
  const [source, setSource] = useState('')
  const [search, setSearch] = useState('')
  const [isActive, setIsActive] = useState('')

  const params: Record<string, string> = { page: String(page) }
  if (city) params.city = city
  if (source) params.source = source
  if (search) params.search = search
  if (isActive) params.is_active = isActive

  const { data, isLoading, error } = useQuery({
    queryKey: ['events', params],
    queryFn: () => fetchEvents(params),
  })

  const { data: cities } = useQuery({
    queryKey: ['cities'],
    queryFn: fetchCities,
  })

  const { data: sources } = useQuery({
    queryKey: ['sources'],
    queryFn: fetchSources,
  })

  if (error) return <div className="error">Errore nel caricamento degli eventi</div>

  const totalPages = data ? Math.ceil(data.count / 25) : 0

  return (
    <>
      <h1>Eventi</h1>

      <div className="filters">
        <input
          type="text"
          placeholder="Cerca..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1) }}
        />
        <select value={city} onChange={(e) => { setCity(e.target.value); setPage(1) }}>
          <option value="">Tutte le citta</option>
          {cities?.map((c) => (
            <option key={c.city} value={c.city}>{c.city} ({c.count})</option>
          ))}
        </select>
        <select value={source} onChange={(e) => { setSource(e.target.value); setPage(1) }}>
          <option value="">Tutte le sorgenti</option>
          {sources?.map((s) => (
            <option key={s.source} value={s.source}>{s.source} ({s.count})</option>
          ))}
        </select>
        <select value={isActive} onChange={(e) => { setIsActive(e.target.value); setPage(1) }}>
          <option value="">Tutti</option>
          <option value="true">Attivi</option>
          <option value="false">Inattivi</option>
        </select>
      </div>

      <div className="card">
        {isLoading ? (
          <div className="loading">Caricamento...</div>
        ) : (
          <>
            <p style={{ marginBottom: '15px', color: '#666' }}>
              {data?.count.toLocaleString()} eventi trovati
            </p>
            <table>
              <thead>
                <tr>
                  <th>Titolo</th>
                  <th>Citta</th>
                  <th>Sorgente</th>
                  <th>Data Inizio</th>
                  <th>Data Fine</th>
                  <th>Stato</th>
                </tr>
              </thead>
              <tbody>
                {data?.results.map((event) => (
                  <tr key={event.id}>
                    <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {event.title}
                    </td>
                    <td>{event.city || 'N/D'}</td>
                    <td>{event.source}</td>
                    <td>{event.date_start ? new Date(event.date_start).toLocaleDateString('it-IT') : 'N/D'}</td>
                    <td>{event.date_end ? new Date(event.date_end).toLocaleDateString('it-IT') : 'N/D'}</td>
                    <td>
                      <span className={`badge ${event.is_active ? 'badge-active' : 'badge-inactive'}`}>
                        {event.is_active ? 'Attivo' : 'Inattivo'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="pagination">
                <button onClick={() => setPage(1)} disabled={page === 1}>
                  Prima
                </button>
                <button onClick={() => setPage(p => p - 1)} disabled={page === 1}>
                  Precedente
                </button>
                <span style={{ padding: '8px 16px' }}>
                  Pagina {page} di {totalPages}
                </span>
                <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages}>
                  Successiva
                </button>
                <button onClick={() => setPage(totalPages)} disabled={page === totalPages}>
                  Ultima
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  )
}

export default EventsList
