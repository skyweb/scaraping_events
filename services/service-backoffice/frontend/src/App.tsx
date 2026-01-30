import { Routes, Route, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import EventsList from './pages/EventsList'
import EtlRuns from './pages/EtlRuns'
import EtlErrors from './pages/EtlErrors'

function App() {
  return (
    <>
      <nav>
        <ul>
          <li><Link to="/">Dashboard</Link></li>
          <li><Link to="/events">Eventi</Link></li>
          <li><Link to="/etl-runs">ETL Runs</Link></li>
          <li><Link to="/etl-errors">ETL Errors</Link></li>
        </ul>
      </nav>
      <div className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/events" element={<EventsList />} />
          <Route path="/etl-runs" element={<EtlRuns />} />
          <Route path="/etl-errors" element={<EtlErrors />} />
        </Routes>
      </div>
    </>
  )
}

export default App
