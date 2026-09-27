import { Routes, Route, Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { IncidentList } from './pages/IncidentList';
import { IncidentDetail } from './pages/IncidentDetail';

function App() {
  return (
    <div className="app-container">
      <header className="header">
        <Link to="/" className="header-brand">
          <Activity className="icon" size={24} />
          <span>SENTRYOPS</span>
        </Link>
        <div className="text-secondary text-sm">
          Autonomous Incident Response Platform
        </div>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<IncidentList />} />
          <Route path="/incidents/:id" element={<IncidentDetail />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
