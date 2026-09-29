import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { ArrowLeft, Activity, Shield, CheckCircle, XCircle, AlertTriangle, FileText, Database, Server, History, BookOpen, GitCompare } from 'lucide-react';

function ServiceHealth({ service }: { service: string }) {
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const data = await api.getServiceHealth(service);
        setHealth(data);
      } catch (e) {
        console.error("Failed to fetch service health");
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, [service]);

  if (!health) return null;

  return (
    <div className="card border-info" style={{ borderColor: 'var(--info)' }}>
      <h3 className="card-title"><Server className="icon" /> Service Health: {service}</h3>
      <div className="grid-3 mt-4">
        <div>
          <div className="text-sm text-secondary">Status</div>
          <div className="font-bold flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${health.status === 'healthy' ? 'bg-success' : 'bg-danger'}`} style={{ backgroundColor: health.status === 'healthy' ? 'var(--success)' : 'var(--danger)', display: 'inline-block' }}></span>
            {health.status}
          </div>
        </div>
        <div>
          <div className="text-sm text-secondary">Replicas</div>
          <div className="font-bold">{health.replicas}</div>
        </div>
        <div>
          <div className="text-sm text-secondary">Version</div>
          <div className="font-mono">{health.version}</div>
        </div>
      </div>
    </div>
  );
}

export function IncidentDetail() {
  const { id } = useParams<{ id: string }>();

  const [incident, setIncident] = useState<any>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [rca, setRca] = useState<any>(null);
  const [remediation, setRemediation] = useState<any>(null);
  const [risk, setRisk] = useState<any>(null);
  const [verification, setVerification] = useState<any>(null);
  const [evaluation, setEvaluation] = useState<any>(null);
  const [replay, setReplay] = useState<any>(null);
  const [postmortem, setPostmortem] = useState<any>(null);

  const [loading, setLoading] = useState(true);
  const [approving, setApproving] = useState(false);

  const fetchAll = async () => {
    if (!id) return;
    try {
      const [incRes, timeRes, evRes, rcaRes, remRes, riskRes, verifRes, evalRes, replayRes, pmRes] = await Promise.all([
        api.getIncident(id).catch(() => null),
        api.getTimeline(id).catch(() => []),
        api.getEvidence(id).catch(() => []),
        api.getRca(id).catch(() => null),
        api.getRemediation(id).catch(() => null),
        api.getRisk(id).catch(() => null),
        api.getVerification(id).catch(() => null),
        api.getEvaluation(id).catch(() => null),
        api.getReplay(id).catch(() => null),
        api.getPostmortem(id).catch(() => null)
      ]);

      setIncident(incRes);
      setTimeline(timeRes);
      setEvidence(evRes);
      setRca(rcaRes?.id ? rcaRes : null);
      setRemediation(remRes?.remediation?.id ? remRes : null);
      setRisk(riskRes?.risk_level ? riskRes : null);
      setVerification(verifRes?.id ? verifRes : null);
      setEvaluation(evalRes?.evaluation_id ? evalRes : null);
      setReplay(replayRes?.replay_id ? replayRes : null);
      setPostmortem(pmRes?.postmortem_id ? pmRes : null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 5000);
    return () => clearInterval(interval);
  }, [id]);

  const handleApprove = async () => {
    if (!id) return;
    setApproving(true);
    try {
      await api.approveRemediation(id, "Approved via Dashboard");
      await fetchAll();
    } catch (e) {
      console.error(e);
      alert('Failed to approve');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!id) return;
    setApproving(true);
    try {
      await api.rejectRemediation(id, "Rejected via Dashboard");
      await fetchAll();
    } catch (e) {
      console.error(e);
      alert('Failed to reject');
    } finally {
      setApproving(false);
    }
  };

  if (loading && !incident) {
    return <div className="center-content"><div className="loading-spinner"></div></div>;
  }

  if (!incident) {
    return <div>Incident not found.</div>;
  }

  return (
    <div>
      <Link to="/" className="btn btn-outline mb-6">
        <ArrowLeft size={16} /> Back to Incidents
      </Link>

      <div className="card">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-4 mb-2">
              <h1 className="text-2xl font-bold">{incident.incident_id}</h1>
              <span className="badge badge-warning">{incident.status}</span>
              <span className="badge badge-danger">{incident.severity}</span>
            </div>
            <h2 className="text-xl text-secondary mb-4">{incident.title}</h2>
            <div className="grid-3 mb-4">
              <div>
                <div className="text-sm text-secondary">Service</div>
                <div className="font-medium">{incident.affected_service || '-'}</div>
              </div>
              <div>
                <div className="text-sm text-secondary">Fault Type</div>
                <div className="font-medium">{incident.fault_type || '-'}</div>
              </div>
              <div>
                <div className="text-sm text-secondary">Created</div>
                <div className="font-medium">{new Date(incident.created_at).toLocaleString()}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid-2">
        <div className="flex-col gap-4">
          {incident.affected_service && (
            <ServiceHealth service={incident.affected_service} />
          )}

          <div className="card">
            <h3 className="card-title"><Activity className="icon" /> Timeline</h3>
            <div className="timeline-container mt-4">
              {timeline.map((ev, i) => (
                <div key={i} className="timeline-item">
                  <div className="font-medium">{ev.event_type}</div>
                  <div className="text-sm text-secondary">{new Date(ev.timestamp).toLocaleString()}</div>
                  <div className="text-sm mt-1 text-muted">{ev.message}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h3 className="card-title"><Database className="icon" /> Evidence</h3>
            {evidence.length === 0 ? <p className="text-secondary text-sm">No evidence collected.</p> : (
              <div className="flex-col gap-4 mt-4">
                {evidence.map(ev => (
                  <div key={ev.evidence_id} className="p-4 border border-color rounded" style={{ borderColor: 'var(--border-color)' }}>
                    <div className="flex justify-between mb-2">
                      <span className="font-mono text-sm">{ev.evidence_id}</span>
                      <span className="badge badge-neutral">{ev.evidence_type}</span>
                    </div>
                    <p className="text-sm mb-2">{ev.summary}</p>
                    <div className="text-xs text-secondary flex gap-4">
                      <span>Source: {ev.source}</span>
                      <span>Confidence: {ev.confidence || 'N/A'}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex-col gap-4">
          <div className="card">
            <h3 className="card-title"><FileText className="icon" /> Root Cause Analysis</h3>
            {!rca ? <p className="text-secondary text-sm">RCA not available yet.</p> : (
              <div className="mt-4">
                <p className="mb-4">{rca.root_cause}</p>
                <div className="text-sm text-secondary mb-2">Confidence: {(rca.confidence * 100).toFixed(0)}%</div>
                {rca.evidence_ids && (
                  <div className="flex gap-2 flex-wrap">
                    {rca.evidence_ids.map((id: string) => <span key={id} className="badge badge-neutral font-mono lowercase">{id}</span>)}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h3 className="card-title"><Shield className="icon" /> Remediation & Risk</h3>
            {!remediation ? <p className="text-secondary text-sm">No remediation proposed yet.</p> : (
              <div className="mt-4">
                <div className="mb-4">
                  <span className="badge badge-info mb-2">{remediation.remediation.action_type}</span>
                  <p className="text-sm mt-2">{remediation.remediation.description}</p>
                  <div className="code-block mt-2">
                    {JSON.stringify(remediation.remediation.parameters, null, 2)}
                  </div>
                </div>

                {risk && (
                  <div className={`p-4 rounded border mt-4 ${risk.risk_level === 'HIGH' ? 'border-danger' : risk.risk_level === 'MEDIUM' ? 'border-warning' : 'border-success'}`} style={{ borderColor: 'var(--border-color)', background: 'rgba(0,0,0,0.2)' }}>
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle size={16} className={risk.risk_level === 'HIGH' ? 'text-danger' : risk.risk_level === 'MEDIUM' ? 'text-warning' : 'text-success'} />
                      <span className="font-bold">Risk: {risk.risk_level}</span>
                    </div>
                    <ul className="text-sm text-secondary ml-4" style={{ listStyle: 'disc' }}>
                      {risk.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}

                {incident.status === 'PENDING_APPROVAL' && (
                  <div className="mt-6 flex gap-4 p-4 border rounded" style={{ borderColor: 'var(--warning)', background: 'rgba(245, 158, 11, 0.1)' }}>
                    <div className="flex-1">
                      <h4 className="font-bold text-warning mb-1">Approval Required</h4>
                      <p className="text-sm text-secondary">Review the remediation and risk assessment before proceeding.</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={handleReject} disabled={approving} className="btn btn-outline border-danger text-danger">Reject</button>
                      <button onClick={handleApprove} disabled={approving} className="btn btn-success">Approve Action</button>
                    </div>
                  </div>
                )}

                {remediation.execution && (
                  <div className="mt-6">
                    <h4 className="font-bold mb-2 flex items-center gap-2"><CheckCircle size={16}/> Execution Result</h4>
                    <div className="p-4 border rounded" style={{ borderColor: 'var(--border-color)' }}>
                      <div className="flex justify-between mb-2">
                        <span className="text-sm">Status: <strong>{remediation.execution.status}</strong></span>
                      </div>
                      <div className="code-block">
                        {JSON.stringify(remediation.execution.result, null, 2)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h3 className="card-title"><CheckCircle className="icon" /> Verification</h3>
            {!verification ? <p className="text-secondary text-sm">Verification not started.</p> : (
              <div className="mt-4">
                <div className="flex items-center gap-2 mb-4">
                  {verification.verified ? <CheckCircle className="text-success" /> : <XCircle className="text-danger" />}
                  <span className="font-bold">{verification.verification_status}</span>
                </div>
                <p className="text-sm mb-4">{verification.summary}</p>

                <div className="flex-col gap-2">
                  {verification.checks.map((chk: any, i: number) => (
                    <div key={i} className="flex justify-between items-center p-3 border rounded text-sm" style={{ borderColor: 'var(--border-color)' }}>
                      <div>
                        <div className="font-medium">{chk.name}</div>
                        <div className="text-xs text-secondary mt-1">Observed: {chk.observed} | Expected: {chk.expected}</div>
                      </div>
                      <div>
                        {chk.passed ? <span className="badge badge-success">Passed</span> : <span className="badge badge-danger">Failed</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title"><Activity className="icon" /> Incident Evaluation</h3>
              {evaluation && (
                <span className={`badge ${
                  evaluation.overall_status === 'PASS' ? 'badge-success' :
                  evaluation.overall_status === 'PARTIAL' ? 'badge-warning' :
                  evaluation.overall_status === 'FAIL' ? 'badge-danger' : 'badge-neutral'
                }`}>
                  {evaluation.overall_status}
                </span>
              )}
            </div>

            {!evaluation ? (
              <p className="text-secondary text-sm">Evaluation not available.</p>
            ) : (
              <div>
                <p className="text-sm mb-4">{evaluation.summary}</p>

                <div className="grid-2 gap-2 mb-4">
                  <div className="p-3 border rounded" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
                    <div className="text-xs text-secondary">Investigation</div>
                    <div className="font-bold text-sm mt-1">{evaluation.investigation_result}</div>
                  </div>
                  <div className="p-3 border rounded" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
                    <div className="text-xs text-secondary">RCA</div>
                    <div className="font-bold text-sm mt-1">{evaluation.rca_result}</div>
                  </div>
                  <div className="p-3 border rounded" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
                    <div className="text-xs text-secondary">Remediation</div>
                    <div className="font-bold text-sm mt-1">{evaluation.remediation_result}</div>
                  </div>
                  <div className="p-3 border rounded" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-main)' }}>
                    <div className="text-xs text-secondary">Verification</div>
                    <div className="font-bold text-sm mt-1">{evaluation.verification_result}</div>
                  </div>
                </div>

                <h4 className="font-bold text-sm mb-2">Evaluation Checks</h4>
                <div className="flex-col gap-2 mb-4">
                  {evaluation.checks?.map((chk: any, i: number) => (
                    <div key={i} className="flex justify-between items-center p-2 border rounded text-xs" style={{ borderColor: 'var(--border-color)' }}>
                      <div>
                        <div className="font-medium">{chk.name}</div>
                        <div className="text-secondary mt-1">{chk.observed}</div>
                      </div>
                      <div>
                        {chk.passed ? (
                          <span className="badge badge-success">Passed</span>
                        ) : (
                          <span className="badge badge-danger">Failed</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {evaluation.recommendations?.length > 0 && (
                  <div>
                    <h4 className="font-bold text-sm mb-2">Recommendations</h4>
                    <ul className="text-xs text-secondary" style={{ paddingLeft: '1.25rem' }}>
                      {evaluation.recommendations.map((rec: string, i: number) => (
                        <li key={i} className="mb-1">{rec}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title"><History className="icon" /> Incident Replay</h3>
              {replay && (
                <span className={`badge ${
                  replay.replay_consistency === 'MATCH' ? 'badge-success' :
                  replay.replay_consistency === 'MISMATCH' ? 'badge-danger' : 'badge-neutral'
                }`}>
                  {replay.replay_consistency}
                </span>
              )}
            </div>

            {!replay ? (
              <p className="text-secondary text-sm">Replay not available.</p>
            ) : (
              <div>
                <p className="text-sm mb-2">{replay.summary}</p>
                <div className="text-xs text-secondary mb-4">
                  Read-only reconstruction — no remediation is re-executed.
                </div>

                {replay.historical_actions?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-bold text-sm mb-2">Historical Actions</h4>
                    {replay.historical_actions.map((act: any, i: number) => (
                      <div key={i} className="p-3 border rounded text-sm mb-2" style={{ borderColor: 'var(--border-color)' }}>
                        <div className="flex justify-between items-center mb-1">
                          <span className="font-mono">{act.action_type}</span>
                          <span className="badge badge-neutral">{act.execution_status || 'NOT EXECUTED'}</span>
                        </div>
                        <div className="text-xs text-secondary">Target: {act.target_service || '-'}</div>
                        <div className="text-xs text-secondary mt-1">{act.note}</div>
                      </div>
                    ))}
                  </div>
                )}

                {replay.differences?.length > 0 ? (
                  <div className="mb-4">
                    <h4 className="font-bold text-sm mb-2"><GitCompare size={14} /> Original vs Replay</h4>
                    <div className="flex-col gap-2">
                      {replay.differences.map((diff: any, i: number) => (
                        <div key={i} className="p-2 border rounded text-xs" style={{ borderColor: 'var(--border-color)' }}>
                          <div className="flex justify-between items-center mb-1">
                            <span className="font-medium">{diff.field}</span>
                            {diff.consistent
                              ? <span className="badge badge-success">Match</span>
                              : <span className="badge badge-danger">Mismatch</span>}
                          </div>
                          <div className="text-secondary">Original: {diff.original ?? 'n/a'}</div>
                          <div className="text-secondary">Replay: {diff.replay ?? 'n/a'}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-secondary text-xs mb-4">No comparable artifacts recorded yet.</p>
                )}

                <h4 className="font-bold text-sm mb-2">Reconstructed Stages</h4>
                <div className="flex-col gap-2">
                  {replay.stages?.map((st: any, i: number) => (
                    <div key={i} className="flex justify-between items-center p-2 border rounded text-xs" style={{ borderColor: 'var(--border-color)' }}>
                      <div>
                        <div className="font-medium">{st.stage}</div>
                        <div className="text-secondary mt-1">{st.summary}</div>
                      </div>
                      <div>
                        {st.available
                          ? <span className="badge badge-success">Available</span>
                          : <span className="badge badge-neutral">Missing</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <h3 className="card-title"><BookOpen className="icon" /> Postmortem</h3>
              {postmortem && <span className="badge badge-neutral">{postmortem.final_status}</span>}
            </div>

            {!postmortem ? (
              <p className="text-secondary text-sm">Postmortem not available.</p>
            ) : (
              <div>
                <p className="text-sm mb-2">{postmortem.summary}</p>
                <p className="text-xs text-secondary mb-4">{postmortem.impact}</p>

                {postmortem.timeline?.length > 0 && (
                  <div className="mb-4">
                    <h4 className="font-bold text-sm mb-2">Timeline</h4>
                    <div className="timeline-container">
                      {postmortem.timeline.map((entry: any, i: number) => (
                        <div key={i} className="timeline-item">
                          <div className="font-medium text-sm">{entry.event}</div>
                          <div className="text-xs text-secondary">
                            {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Timestamp unavailable'}
                          </div>
                          {entry.message && <div className="text-xs mt-1 text-muted">{entry.message}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <h4 className="font-bold text-sm mb-2">Sections</h4>
                <div className="flex-col gap-2 mb-4">
                  {postmortem.sections?.map((sec: any, i: number) => (
                    <div key={i} className="p-3 border rounded text-xs" style={{ borderColor: 'var(--border-color)' }}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-medium">{sec.section}</span>
                        {sec.available
                          ? <span className="badge badge-success">Available</span>
                          : <span className="badge badge-neutral">Missing</span>}
                      </div>
                      <div className="text-secondary">{sec.summary}</div>
                    </div>
                  ))}
                </div>

                {postmortem.lessons?.length > 0 && (
                  <div>
                    <h4 className="font-bold text-sm mb-2">Lessons / Recommendations</h4>
                    <ul className="text-xs text-secondary" style={{ paddingLeft: '1.25rem' }}>
                      {postmortem.lessons.map((lesson: string, i: number) => (
                        <li key={i} className="mb-1">{lesson}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
