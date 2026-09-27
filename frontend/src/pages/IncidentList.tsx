import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, Search } from 'lucide-react';
import { api } from '../api/client';

export function IncidentList() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchIncidents = async () => {
    try {
      const data = await api.getIncidents();
      setIncidents(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 5000);
    return () => clearInterval(interval);
  }, []);

  const filtered = incidents.filter(i =>
    i.title.toLowerCase().includes(search.toLowerCase()) ||
    i.incident_id.toLowerCase().includes(search.toLowerCase()) ||
    i.affected_service?.toLowerCase().includes(search.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'DETECTED':
      case 'INVESTIGATING': return 'badge-warning';
      case 'PENDING_APPROVAL': return 'badge-info';
      case 'RESOLVED': return 'badge-success';
      default: return 'badge-neutral';
    }
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'CRITICAL':
      case 'HIGH': return 'badge-danger';
      case 'MEDIUM': return 'badge-warning';
      default: return 'badge-info';
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="card-title" style={{ fontSize: '1.5rem' }}>
          <AlertCircle className="icon" /> Incident Overview
        </h1>
      </div>

      <div className="grid-4 mb-6">
        <div className="stat-card">
          <div className="text-secondary text-sm">Total Incidents</div>
          <div className="stat-value">{incidents.length}</div>
        </div>
        <div className="stat-card">
          <div className="text-secondary text-sm">Investigating</div>
          <div className="stat-value">{incidents.filter(i => i.status === 'INVESTIGATING').length}</div>
        </div>
        <div className="stat-card">
          <div className="text-secondary text-sm">Pending Approval</div>
          <div className="stat-value">{incidents.filter(i => i.status === 'PENDING_APPROVAL').length}</div>
        </div>
        <div className="stat-card">
          <div className="text-secondary text-sm">Resolved</div>
          <div className="stat-value">{incidents.filter(i => i.status === 'RESOLVED').length}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="flex gap-4 w-full">
            <div className="flex items-center gap-2" style={{ flex: 1, background: 'var(--bg-main)', padding: '0.5rem 1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              <Search size={18} className="text-secondary" />
              <input
                type="text"
                placeholder="Search incidents..."
                style={{ background: 'transparent', border: 'none', color: 'inherit', outline: 'none', width: '100%' }}
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="center-content">
            <div className="loading-spinner"></div>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Service</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Time</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(inc => (
                  <tr key={inc.incident_id}>
                    <td className="font-mono text-sm">{inc.incident_id}</td>
                    <td>{inc.title}</td>
                    <td>{inc.affected_service || '-'}</td>
                    <td><span className={`badge ${getSeverityBadge(inc.severity)}`}>{inc.severity}</span></td>
                    <td><span className={`badge ${getStatusBadge(inc.status)}`}>{inc.status}</span></td>
                    <td className="text-secondary text-sm">{new Date(inc.created_at).toLocaleString()}</td>
                    <td>
                      <Link to={`/incidents/${inc.incident_id}`} className="btn btn-primary" style={{ padding: '0.25rem 0.75rem', fontSize: '0.75rem' }}>
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }} className="text-secondary">
                      No incidents found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
