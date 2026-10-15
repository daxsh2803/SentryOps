import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Activity, Flame, AlertCircle } from 'lucide-react';
import { IncidentList } from './pages/IncidentList';
import { IncidentDetail } from './pages/IncidentDetail';
import { FaultInjection } from './pages/FaultInjection';

function App() {
  const location = useLocation();

  return (
    <div className="app-container">
      <header className="header">
        <div className="flex items-center gap-6">
          <Link to="/" className="header-brand">
            <Activity className="icon" size={24} />
            <span>SENTRYOPS</span>
          </Link>

          <nav className="flex items-center gap-2">
            <Link
              to="/"
              className={`btn ${location.pathname === '/' || location.pathname.startsWith('/incidents') ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}
            >
              <AlertCircle size={15} />
              Incidents
            </Link>
            <Link
              to="/faults"
              className={`btn ${location.pathname === '/faults' ? 'btn-primary' : 'btn-outline'}`}
              style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}
            >
              <Flame size={15} />
              Fault Injection
            </Link>
          </nav>
        </div>

        <div className="text-secondary text-sm">
          Autonomous Incident Response Platform
        </div>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<IncidentList />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
          <Route path="/faults" element={<FaultInjection />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
