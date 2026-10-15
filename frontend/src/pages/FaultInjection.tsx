import { useEffect, useState, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import {
  Flame,
  RefreshCw,
  Play,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Info,
  Sliders,
  Send,
  Radio,
  RotateCcw,
  WifiOff
} from 'lucide-react';
import { api } from '../api/client';
import type { FaultModel, FaultRequest, IncidentModel } from '../api/client';
import { formatTime } from '../utils/date';

interface FaultScenarioMeta {
  type: string;
  label: string;
  defaultService: string;
  supportedServices: string[];
  description: string;
  paramFields: {
    key: string;
    label: string;
    type: 'number' | 'text' | 'boolean';
    defaultValue: any;
    min?: number;
    max?: number;
    step?: number;
    helperText: string;
  }[];
}

const SCENARIOS: Record<string, FaultScenarioMeta> = {
  http_500_spike: {
    type: 'http_500_spike',
    label: 'HTTP 500 Spike',
    defaultService: 'payment-service',
    supportedServices: ['payment-service'],
    description: 'Injects HTTP 500 Internal Server Errors on downstream payment operations at a configurable failure rate.',
    paramFields: [
      {
        key: 'error_rate',
        label: 'Failure Rate (0.0 - 1.0)',
        type: 'number',
        defaultValue: 1.0,
        min: 0.1,
        max: 1.0,
        step: 0.1,
        helperText: '1.0 = 100% failure rate; 0.5 = 50% chance of failure on each transaction.'
      }
    ]
  },
  payment_service_crash: {
    type: 'payment_service_crash',
    label: 'Payment Service Crash',
    defaultService: 'payment-service',
    supportedServices: ['payment-service'],
    description: 'Simulates service outage on payment processing by raising HTTP 503 Service Unavailable.',
    paramFields: []
  },
  artificial_latency: {
    type: 'artificial_latency',
    label: 'Artificial Latency',
    defaultService: 'payment-service',
    supportedServices: ['payment-service'],
    description: 'Introduces artificial processing delay to simulate heavy load, network degradation, or resource starvation.',
    paramFields: [
      {
        key: 'delay_ms',
        label: 'Delay (milliseconds)',
        type: 'number',
        defaultValue: 2000,
        min: 100,
        max: 10000,
        step: 100,
        helperText: 'Simulated latency in milliseconds added before the service responds.'
      }
    ]
  },
  db_connection_exhaustion: {
    type: 'db_connection_exhaustion',
    label: 'Database Connection Pool Exhaustion',
    defaultService: 'payment-service',
    supportedServices: ['payment-service'],
    description: 'Simulates database pool saturation causing transaction timeouts and connection failures.',
    paramFields: []
  },
  bad_configuration: {
    type: 'bad_configuration',
    label: 'Bad Configuration',
    defaultService: 'payment-service',
    supportedServices: ['payment-service'],
    description: 'Simulates invalid downstream endpoint configuration causing HTTP 502 Bad Gateway.',
    paramFields: []
  }
};

interface OrderTestResult {
  index: number;
  status: number | null;
  success: boolean;
  isConnectionError: boolean;
  orderId?: string;
  errorMessage?: string;
  durationMs: number;
  timestamp: string;
}

export function FaultInjection() {
  // Fault State
  const [activeFaults, setActiveFaults] = useState<FaultModel[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>('http_500_spike');
  const [targetService, setTargetService] = useState<string>('payment-service');
  const [paramValues, setParamValues] = useState<Record<string, any>>({ error_rate: 1.0 });

  // UI state
  const [loadingFaults, setLoadingFaults] = useState<boolean>(true);
  const [injecting, setInjecting] = useState<boolean>(false);
  const [cleaningUpId, setCleaningUpId] = useState<string | null>(null);
  const [confirmInject, setConfirmInject] = useState<boolean>(false);
  const [apiConnected, setApiConnected] = useState<boolean | null>(null);
  const [bannerMessage, setBannerMessage] = useState<{
    type: 'success' | 'error' | 'info';
    text: string;
    incidentId?: string;
  } | null>(null);

  // Track fault IDs that have already created an incident to prevent duplicates
  const createdIncidentFaultIdsRef = useRef<Set<string>>(new Set());

  // Order Test Panel State
  const [testRequestCount, setTestRequestCount] = useState<number>(5);
  const [testRunning, setTestRunning] = useState<boolean>(false);
  const [orderResults, setOrderResults] = useState<OrderTestResult[]>([]);
  const [testSummary, setTestSummary] = useState<{ total: number; success: number; failed: number } | null>(null);

  // Fetch active faults and supported types
  const refreshFaultData = useCallback(async () => {
    setLoadingFaults(true);
    try {
      const [, faults] = await Promise.all([
        api.getFaultTypes(),
        api.getActiveFaults()
      ]);
      setActiveFaults(faults);
      setApiConnected(true);
      // Clear banner error if previous connectivity error was shown
      setBannerMessage(prev => prev?.type === 'error' && prev.text.includes('Cannot reach Fault Injection API') ? null : prev);
    } catch (err: any) {
      console.error('Failed to connect to Fault Injection API:', err);
      setApiConnected(false);
      setBannerMessage({
        type: 'error',
        text: 'Cannot reach Fault Injection API via /faults-api (or port 8005). Verify port-forward or proxy connectivity.'
      });
    } finally {
      setLoadingFaults(false);
    }
  }, []);

  useEffect(() => {
    refreshFaultData();
    const interval = setInterval(refreshFaultData, 6000);
    return () => clearInterval(interval);
  }, [refreshFaultData]);

  // When scenario changes, update default parameters and target service
  const handleScenarioChange = (scenarioKey: string) => {
    setSelectedScenario(scenarioKey);
    setConfirmInject(false);
    const meta = SCENARIOS[scenarioKey];
    if (meta) {
      setTargetService(meta.defaultService);
      const initialParams: Record<string, any> = {};
      meta.paramFields.forEach(f => {
        initialParams[f.key] = f.defaultValue;
      });
      setParamValues(initialParams);
    }
  };

  // Inject fault handler
  const handleInjectFault = async () => {
    if (!confirmInject) {
      setConfirmInject(true);
      return;
    }

    setInjecting(true);
    setBannerMessage(null);
    try {
      const meta = SCENARIOS[selectedScenario];
      const payload: FaultRequest = {
        fault_type: selectedScenario,
        target_service: targetService,
        parameters: meta && meta.paramFields.length > 0 ? paramValues : {}
      };

      // 1. Inject fault via Fault Injection API
      const faultResult = await api.injectFault(payload);
      setConfirmInject(false);
      await refreshFaultData();

      // 2. Automatically create corresponding incident via Backend API (deduped by fault_id)
      let incidentResult: IncidentModel | null = null;
      let incidentError: string | null = null;

      if (!createdIncidentFaultIdsRef.current.has(faultResult.fault_id)) {
        try {
          const severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' =
            selectedScenario === 'payment_service_crash' ? 'CRITICAL' : 'HIGH';
          const title = `${meta?.label || faultResult.fault_type} on ${faultResult.target_service}`;
          const description = `Automated incident triggered by fault injection [${faultResult.fault_id}]: ${faultResult.description || meta?.description || ''}`;

          incidentResult = await api.createIncident({
            title,
            description,
            severity,
            affected_service: faultResult.target_service,
            fault_type: faultResult.fault_type
          });
          createdIncidentFaultIdsRef.current.add(faultResult.fault_id);
        } catch (incErr: any) {
          const incDetail = incErr.response?.data?.detail || incErr.message || 'Incident creation failed';
          incidentError = typeof incDetail === 'object' ? JSON.stringify(incDetail) : incDetail;
        }
      }

      // 3. Clear UI feedback distinguishing fault injection from incident creation
      if (incidentResult) {
        setBannerMessage({
          type: 'success',
          text: `Fault [${faultResult.fault_id}] injected successfully on ${faultResult.target_service}. Incident [${incidentResult.incident_id}] created.`,
          incidentId: incidentResult.incident_id
        });
      } else if (incidentError) {
        setBannerMessage({
          type: 'error',
          text: `Fault [${faultResult.fault_id}] injected on ${faultResult.target_service}, but incident creation failed: ${incidentError}`
        });
      } else {
        setBannerMessage({
          type: 'success',
          text: `Injected fault [${faultResult.fault_id}] on ${faultResult.target_service} (${faultResult.fault_type}). Status: ${faultResult.status}.`
        });
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Injection failed';
      setBannerMessage({
        type: 'error',
        text: `Fault injection failed: ${typeof detail === 'object' ? JSON.stringify(detail) : detail}. No incident was created.`
      });
    } finally {
      setInjecting(false);
    }
  };

  // Cleanup fault handler
  const handleCleanupFault = async (faultId: string) => {
    setCleaningUpId(faultId);
    setBannerMessage(null);
    try {
      await api.cleanupFault(faultId);
      setBannerMessage({
        type: 'success',
        text: `Fault [${faultId}] successfully cleaned up. Simulated fault state cleared in Redis.`
      });
      await refreshFaultData();
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || 'Cleanup failed';
      setBannerMessage({
        type: 'error',
        text: `Failed to clean up fault [${faultId}]: ${detail}`
      });
    } finally {
      setCleaningUpId(null);
    }
  };

  // Cleanup all active faults
  const handleCleanupAll = async () => {
    if (activeFaults.length === 0) return;
    setInjecting(true);
    try {
      for (const fault of activeFaults) {
        await api.cleanupFault(fault.fault_id);
      }
      setBannerMessage({
        type: 'success',
        text: `All ${activeFaults.length} active fault(s) successfully cleaned up.`
      });
      await refreshFaultData();
    } catch (err: any) {
      setBannerMessage({
        type: 'error',
        text: `Error during batch cleanup: ${err.message}`
      });
    } finally {
      setInjecting(false);
    }
  };

  // Run Order Test Flow
  const handleRunOrderTest = async () => {
    setTestRunning(true);
    setOrderResults([]);
    setTestSummary(null);

    const count = Math.min(Math.max(1, testRequestCount), 10);
    const results: OrderTestResult[] = [];
    let successCount = 0;
    let failCount = 0;

    for (let i = 1; i <= count; i++) {
      const res = await api.testOrder(100);
      const isSuccess = res.success;
      if (isSuccess) successCount++;
      else failCount++;

      const item: OrderTestResult = {
        index: i,
        status: res.status,
        success: isSuccess,
        isConnectionError: res.isConnectionError,
        orderId: res.data?.order_id,
        errorMessage: !isSuccess ? (
          res.isConnectionError
            ? (res.data?.error || 'Connection Failed')
            : (typeof res.data?.detail === 'string' ? res.data.detail : JSON.stringify(res.data))
        ) : undefined,
        durationMs: res.durationMs,
        timestamp: new Date().toLocaleTimeString()
      };
      results.push(item);
      setOrderResults([...results]);
      // Small delay between requests to simulate realistic traffic
      await new Promise(r => setTimeout(r, 200));
    }

    setTestSummary({
      total: count,
      success: successCount,
      failed: failCount
    });
    setTestRunning(false);
  };

  const currentMeta = SCENARIOS[selectedScenario] || {
    type: selectedScenario,
    label: selectedScenario,
    defaultService: 'payment-service',
    supportedServices: ['payment-service'],
    description: 'Custom fault scenario',
    paramFields: []
  };

  return (
    <div>
      {/* Page Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="card-title" style={{ fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Flame className="icon" style={{ color: 'var(--danger)', width: 28, height: 28 }} />
            Fault Injection Control Center
          </h1>
          <p className="text-secondary text-sm mt-2">
            Simulate downstream microservice failures to observe automated multi-agent detection, root cause analysis, and safety remediation.
          </p>
        </div>

        {/* API Status Badge */}
        <div className="flex items-center gap-2">
          <div
            className="flex items-center gap-2"
            style={{
              background: 'var(--bg-card)',
              padding: '0.4rem 0.8rem',
              borderRadius: '6px',
              border: '1px solid var(--border-color)',
              fontSize: '0.85rem'
            }}
          >
            <Radio
              size={14}
              style={{ color: apiConnected === true ? 'var(--success)' : apiConnected === false ? 'var(--danger)' : 'var(--text-muted)' }}
            />
            <span className="text-secondary">Fault API:</span>
            <span style={{ fontWeight: 600, color: apiConnected === true ? 'var(--success)' : apiConnected === false ? 'var(--danger)' : 'var(--text-muted)' }}>
              {apiConnected === true ? 'ONLINE' : apiConnected === false ? 'OFFLINE' : 'CHECKING...'}
            </span>
          </div>

          <button
            className="btn btn-outline"
            onClick={refreshFaultData}
            disabled={loadingFaults}
            title="Refresh Fault Status"
          >
            <RefreshCw size={16} className={loadingFaults ? 'loading-spinner' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Banner Notifications */}
      {bannerMessage && (
        <div
          className="card"
          style={{
            padding: '1rem 1.25rem',
            marginBottom: '1.5rem',
            borderLeft: `4px solid ${
              bannerMessage.type === 'success' ? 'var(--success)' :
              bannerMessage.type === 'error' ? 'var(--danger)' : 'var(--info)'
            }`,
            background: bannerMessage.type === 'error' ? 'rgba(239, 68, 68, 0.08)' : 'var(--bg-card)'
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-sm">
              {bannerMessage.type === 'success' && <CheckCircle size={18} style={{ color: 'var(--success)' }} />}
              {bannerMessage.type === 'error' && <AlertTriangle size={18} style={{ color: 'var(--danger)' }} />}
              {bannerMessage.type === 'info' && <Info size={18} style={{ color: 'var(--info)' }} />}
              <span>{bannerMessage.text}</span>
              {bannerMessage.incidentId && (
                <Link
                  to={`/incidents/${bannerMessage.incidentId}`}
                  style={{
                    marginLeft: '0.5rem',
                    color: 'var(--primary)',
                    textDecoration: 'underline',
                    fontWeight: 600
                  }}
                >
                  View Incident &rarr;
                </Link>
              )}
            </div>
            <button
              onClick={() => setBannerMessage(null)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              &times;
            </button>
          </div>
        </div>
      )}

      {/* Active Fault Warning Callout */}
      {activeFaults.length > 0 && (
        <div
          className="card"
          style={{
            borderColor: 'var(--danger)',
            background: 'linear-gradient(145deg, rgba(239, 68, 68, 0.12), var(--bg-card))',
            padding: '1.25rem 1.5rem',
            marginBottom: '1.5rem'
          }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ShieldAlert size={28} style={{ color: 'var(--danger)' }} />
              <div>
                <div style={{ fontWeight: 700, color: 'var(--danger)', fontSize: '1rem' }}>
                  ACTIVE FAULT IN PROGRESS ({activeFaults.length})
                </div>
                <div className="text-sm text-secondary mt-1">
                  Synthetic fault injection is actively degrading target service telemetry. Orders through the API gateway will experience failures or high latency.
                </div>
              </div>
            </div>
            <button
              className="btn btn-danger"
              onClick={handleCleanupAll}
              disabled={injecting}
              style={{ whiteSpace: 'nowrap' }}
            >
              <RotateCcw size={16} /> Clean Up All Faults
            </button>
          </div>
        </div>
      )}

      {/* Top Grid: Injector Form & Live Order Tester */}
      <div className="grid-2 mb-6">
        {/* Panel 1: Fault Injection Form */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <Sliders className="icon" /> Scenario Configuration
            </h2>
            <span className="badge badge-info">Step 1</span>
          </div>

          <div className="flex flex-col gap-4">
            {/* Scenario Dropdown */}
            <div>
              <label className="text-sm text-secondary" style={{ display: 'block', marginBottom: '0.4rem', fontWeight: 500 }}>
                Fault Scenario
              </label>
              <select
                value={selectedScenario}
                onChange={e => handleScenarioChange(e.target.value)}
                style={{
                  width: '100%',
                  background: 'var(--bg-main)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  padding: '0.6rem 0.8rem',
                  borderRadius: '6px',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              >
                {Object.entries(SCENARIOS).map(([key, s]) => (
                  <option key={key} value={key}>
                    {s.label} ({key})
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted mt-2">
                {currentMeta.description}
              </p>
            </div>

            {/* Target Service Selector */}
            <div>
              <label className="text-sm text-secondary" style={{ display: 'block', marginBottom: '0.4rem', fontWeight: 500 }}>
                Target Microservice
              </label>
              <select
                value={targetService}
                onChange={e => { setTargetService(e.target.value); setConfirmInject(false); }}
                style={{
                  width: '100%',
                  background: 'var(--bg-main)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  padding: '0.6rem 0.8rem',
                  borderRadius: '6px',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              >
                {currentMeta.supportedServices.map(svc => (
                  <option key={svc} value={svc}>
                    {svc} (Simulated Service)
                  </option>
                ))}
              </select>
            </div>

            {/* Dynamic Parameter Fields */}
            {currentMeta.paramFields.length > 0 ? (
              <div style={{ background: 'var(--bg-main)', padding: '1rem', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                <div className="text-xs text-secondary font-bold uppercase mb-2">Scenario Parameters</div>
                {currentMeta.paramFields.map(param => (
                  <div key={param.key} className="mb-2">
                    <label className="text-sm flex justify-between items-center mb-1">
                      <span>{param.label}</span>
                      <span className="font-mono text-xs text-muted">key: {param.key}</span>
                    </label>
                    <input
                      type={param.type}
                      min={param.min}
                      max={param.max}
                      step={param.step}
                      value={paramValues[param.key] ?? param.defaultValue}
                      onChange={e => {
                        const val = param.type === 'number' ? parseFloat(e.target.value) : e.target.value;
                        setParamValues({ ...paramValues, [param.key]: val });
                        setConfirmInject(false);
                      }}
                      style={{
                        width: '100%',
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                        color: 'var(--text-primary)',
                        padding: '0.5rem 0.75rem',
                        borderRadius: '6px',
                        fontSize: '0.875rem',
                        outline: 'none'
                      }}
                    />
                    <p className="text-xs text-muted mt-1">{param.helperText}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-muted" style={{ background: 'var(--bg-main)', padding: '0.75rem', borderRadius: '6px' }}>
                This scenario does not require custom parameters.
              </div>
            )}

            {/* Injection Trigger Button */}
            <div className="mt-2">
              {confirmInject ? (
                <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)', padding: '0.9rem', borderRadius: '6px' }}>
                  <div className="text-sm font-bold text-danger mb-2 flex items-center gap-2">
                    <AlertTriangle size={16} /> Confirm Fault Injection
                  </div>
                  <p className="text-xs text-secondary mb-3">
                    This will immediately inject <strong>{currentMeta.label}</strong> into <strong>{targetService}</strong>. Downstream orders will fail or experience degradation.
                  </p>
                  <div className="flex gap-2">
                    <button
                      className="btn btn-danger"
                      onClick={handleInjectFault}
                      disabled={injecting}
                      style={{ flex: 1 }}
                    >
                      {injecting ? <span className="loading-spinner"></span> : <Flame size={16} />}
                      Yes, Inject Fault Now
                    </button>
                    <button
                      className="btn btn-outline"
                      onClick={() => setConfirmInject(false)}
                      disabled={injecting}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  className="btn btn-primary"
                  onClick={handleInjectFault}
                  disabled={injecting || apiConnected === false}
                  style={{ width: '100%', padding: '0.7rem' }}
                >
                  <Flame size={18} />
                  Inject Fault Scenario
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Panel 2: Live In-Browser Order Tester */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <Play className="icon" /> Service Health & Order Tester
              </h2>
              <div className="text-xs text-secondary mt-1">
                API Gateway Route (/gateway-api/orders)
              </div>
            </div>
            <span className="badge badge-info">Step 2</span>
          </div>

          <div className="flex flex-col gap-4">
            <p className="text-sm text-secondary">
              Execute live transaction requests through the API Gateway to verify normal baseline operations, confirm fault impact, or validate recovery.
            </p>

            {/* Controls */}
            <div className="flex items-center gap-3">
              <div style={{ flex: 1 }}>
                <label className="text-xs text-muted block mb-1">Number of Requests (1 - 10)</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={testRequestCount}
                  onChange={e => setTestRequestCount(Math.min(10, Math.max(1, parseInt(e.target.value) || 1)))}
                  disabled={testRunning}
                  style={{
                    width: '100%',
                    background: 'var(--bg-main)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    padding: '0.5rem 0.75rem',
                    borderRadius: '6px',
                    fontSize: '0.875rem'
                  }}
                />
              </div>

              <div style={{ alignSelf: 'flex-end' }}>
                <button
                  className="btn btn-success"
                  onClick={handleRunOrderTest}
                  disabled={testRunning}
                  style={{ minWidth: '140px', padding: '0.55rem 1rem' }}
                >
                  {testRunning ? (
                    <>
                      <span className="loading-spinner"></span> Testing...
                    </>
                  ) : (
                    <>
                      <Send size={16} /> Run Test
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Summary Bar */}
            {testSummary && (
              <div
                className="flex justify-between items-center text-sm p-3"
                style={{
                  background: testSummary.failed > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                  borderRadius: '6px',
                  border: `1px solid ${testSummary.failed > 0 ? 'var(--danger)' : 'var(--success)'}`
                }}
              >
                <div className="flex items-center gap-2">
                  {testSummary.failed === 0 ? (
                    <CheckCircle size={18} style={{ color: 'var(--success)' }} />
                  ) : (
                    <XCircle size={18} style={{ color: 'var(--danger)' }} />
                  )}
                  <span style={{ fontWeight: 600 }}>
                    {testSummary.failed === 0 ? '100% Transactions Succeeded' : `${testSummary.failed} of ${testSummary.total} Requests Failed`}
                  </span>
                </div>
                <div className="flex gap-3 text-xs font-mono">
                  <span style={{ color: 'var(--success)' }}>SUCCESS: {testSummary.success}</span>
                  <span style={{ color: 'var(--danger)' }}>FAIL: {testSummary.failed}</span>
                </div>
              </div>
            )}

            {/* Live Results Stream */}
            <div
              style={{
                maxHeight: '220px',
                overflowY: 'auto',
                background: 'var(--bg-main)',
                borderRadius: '6px',
                border: '1px solid var(--border-color)',
                padding: '0.5rem'
              }}
            >
              {orderResults.length === 0 ? (
                <div className="text-center text-muted text-xs p-4">
                  No test executions yet. Click <strong>Run Test</strong> to generate order traffic.
                </div>
              ) : (
                <div className="flex flex-col gap-1">
                  {orderResults.map(res => (
                    <div
                      key={res.index}
                      className="flex justify-between items-center text-xs p-2"
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                        background: res.success ? 'transparent' : 'rgba(239, 68, 68, 0.05)'
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-muted">#{res.index}</span>
                        {res.status !== null ? (
                          <span className={`badge ${res.success ? 'badge-success' : 'badge-danger'}`} style={{ padding: '0.1rem 0.4rem', fontSize: '0.65rem' }}>
                            HTTP {res.status}
                          </span>
                        ) : (
                          <span className="badge badge-danger" style={{ padding: '0.1rem 0.4rem', fontSize: '0.65rem', display: 'inline-flex', alignItems: 'center', gap: '2px' }}>
                            <WifiOff size={10} /> CONNECTION ERROR
                          </span>
                        )}
                        {res.success ? (
                          <span className="font-mono text-muted" style={{ fontSize: '0.75rem' }}>
                            {res.orderId ? `order: ${res.orderId.slice(0, 8)}...` : 'completed'}
                          </span>
                        ) : (
                          <span style={{ color: 'var(--danger)' }}>
                            {res.errorMessage ? res.errorMessage.slice(0, 45) : 'Transaction error'}
                          </span>
                        )}
                      </div>
                      <div className="text-muted font-mono" style={{ fontSize: '0.7rem' }}>
                        {res.durationMs}ms
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Panel: Active Injected Faults Table */}
      <div className="card">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <h2 className="card-title">
              <ShieldAlert className="icon" /> Active Faults Registry
            </h2>
            <span className="badge badge-neutral">{activeFaults.length} Active</span>
          </div>

          <div className="text-xs text-muted">
            State managed in Redis via Fault Injection API
          </div>
        </div>

        {loadingFaults && activeFaults.length === 0 ? (
          <div className="center-content">
            <div className="loading-spinner"></div>
          </div>
        ) : activeFaults.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '2.5rem 1rem' }} className="text-secondary">
            <CheckCircle size={36} style={{ color: 'var(--success)', margin: '0 auto 0.75rem', display: 'block' }} />
            <div style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-primary)' }}>All Systems Baseline Normal</div>
            <div className="text-sm text-muted mt-1">No simulated synthetic faults are currently active.</div>
          </div>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Fault ID</th>
                  <th>Scenario</th>
                  <th>Target Service</th>
                  <th>Parameters</th>
                  <th>Status</th>
                  <th>Started At</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {activeFaults.map(fault => (
                  <tr key={fault.fault_id}>
                    <td className="font-mono text-sm font-bold" style={{ color: 'var(--primary)' }}>
                      {fault.fault_id}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{fault.fault_type}</div>
                      <div className="text-xs text-muted">{fault.description}</div>
                    </td>
                    <td>
                      <span className="font-mono text-xs" style={{ background: 'var(--bg-main)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                        {fault.target_service}
                      </span>
                    </td>
                    <td>
                      <span className="font-mono text-xs text-secondary">
                        {fault.parameters && Object.keys(fault.parameters).length > 0
                          ? JSON.stringify(fault.parameters)
                          : 'none'}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-danger">
                        {fault.status}
                      </span>
                    </td>
                    <td className="text-secondary text-sm">
                      {formatTime(fault.started_at)}
                    </td>
                    <td>
                      <button
                        className="btn btn-outline"
                        onClick={() => handleCleanupFault(fault.fault_id)}
                        disabled={cleaningUpId === fault.fault_id}
                        style={{
                          padding: '0.35rem 0.75rem',
                          fontSize: '0.8rem',
                          borderColor: 'var(--danger)',
                          color: 'var(--danger)'
                        }}
                      >
                        {cleaningUpId === fault.fault_id ? (
                          <span className="loading-spinner"></span>
                        ) : (
                          <RotateCcw size={14} />
                        )}
                        Clean Up
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Safety Notice Callout */}
      <div
        className="card"
        style={{
          background: 'var(--bg-card)',
          borderLeft: '4px solid var(--info)',
          marginTop: '1.5rem',
          padding: '1rem 1.25rem'
        }}
      >
        <div className="flex items-start gap-3 text-xs text-secondary">
          <Info size={18} style={{ color: 'var(--info)', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <strong style={{ color: 'var(--text-primary)' }}>Live Demo & Architecture Safety Notice:</strong>
            <p className="mt-1">
              Fault injection alters simulated state stored in Redis. In the SentryOps architecture, remediation proposals approved by operators update the in-memory simulated infrastructure state (<code>SIMULATED_INFRA_STATE</code>). Real Kubernetes deployments remain safely unchanged at 1 replica. Service recovery from injected faults is achieved by clearing the synthetic fault state via the cleanup action above.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
