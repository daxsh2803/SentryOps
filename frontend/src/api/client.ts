import axios from 'axios';

// Default to same-origin proxies served by Nginx in Kubernetes or Vite proxy in dev.
// Fallback directly to localhost ports if running in a standalone unproxied environment.
const API_URL = import.meta.env.VITE_API_URL || '/api';
const FAULT_API_URL = import.meta.env.VITE_FAULT_API_URL || '/faults-api';
const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL || '/gateway-api';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const faultClient = axios.create({
  baseURL: FAULT_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const gatewayClient = axios.create({
  baseURL: GATEWAY_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface FaultModel {
  fault_id: string;
  incident_id: string;
  fault_type: string;
  target_service: string;
  status: string;
  started_at: string | null;
  ended_at: string | null;
  parameters: Record<string, any>;
  ground_truth_root_cause: string;
  description: string;
}

export interface FaultRequest {
  fault_type: string;
  target_service: string;
  parameters?: Record<string, any>;
}

export interface OrderTestResponse {
  status: number | null;
  success: boolean;
  isConnectionError: boolean;
  data: any;
  durationMs: number;
}

export interface IncidentCreateRequest {
  title: string;
  description?: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  affected_service?: string;
  fault_type?: string;
}

export interface IncidentModel {
  id: number;
  incident_id: string;
  title: string;
  description?: string;
  status: string;
  severity: string;
  affected_service?: string;
  fault_type?: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  resolved_at?: string | null;
}

export const api = {
  createIncident: async (req: IncidentCreateRequest): Promise<IncidentModel> => {
    const res = await apiClient.post('/incidents', req);
    return res.data;
  },
  getIncidents: async () => {
    const res = await apiClient.get('/incidents');
    return res.data;
  },
  getIncident: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}`);
    return res.data;
  },
  investigateIncident: async (id: string) => {
    const res = await apiClient.post(`/incidents/${id}/ai-investigate`);
    return res.data;
  },
  getTimeline: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/timeline`);
    return res.data;
  },
  getEvidence: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/evidence`);
    return res.data;
  },
  getRca: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/rca`);
    return res.data;
  },
  getRemediation: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/remediation`);
    return res.data;
  },
  getRisk: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/risk`);
    return res.data;
  },
  getVerification: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/verification`);
    return res.data;
  },
  approveRemediation: async (id: string, reason?: string) => {
    const res = await apiClient.post(`/incidents/${id}/approve`, { reason });
    return res.data;
  },
  rejectRemediation: async (id: string, reason?: string) => {
    const res = await apiClient.post(`/incidents/${id}/reject`, { reason });
    return res.data;
  },
  getServiceHealth: async (service: string) => {
    const res = await apiClient.get(`/service-health/${service}`);
    return res.data;
  },
  getEvaluation: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/evaluation`);
    return res.data;
  },
  getReplay: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/replay`);
    return res.data;
  },
  getPostmortem: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}/postmortem`);
    return res.data;
  },

  // Fault Injection API (/faults-api or http://localhost:8005)
  getFaultTypes: async (): Promise<string[]> => {
    const res = await faultClient.get('/faults/types');
    return res.data;
  },
  getActiveFaults: async (): Promise<FaultModel[]> => {
    const res = await faultClient.get('/faults');
    return res.data;
  },
  injectFault: async (req: FaultRequest): Promise<FaultModel> => {
    const res = await faultClient.post('/faults/inject', req);
    return res.data;
  },
  cleanupFault: async (faultId: string): Promise<{ status: string }> => {
    const res = await faultClient.post(`/faults/${faultId}/cleanup`);
    return res.data;
  },

  // Service Health / Order Testing (/gateway-api or http://localhost:8080)
  testOrder: async (amount: number = 100): Promise<OrderTestResponse> => {
    const start = performance.now();
    try {
      const res = await gatewayClient.post('/orders', { amount }, { timeout: 10000 });
      const durationMs = Math.round(performance.now() - start);
      return {
        status: res.status,
        success: res.status >= 200 && res.status < 300,
        isConnectionError: false,
        data: res.data,
        durationMs
      };
    } catch (err: any) {
      const durationMs = Math.round(performance.now() - start);
      if (err.response) {
        // The server actually responded with a non-2xx status code (e.g. 500, 502, 503)
        return {
          status: err.response.status,
          success: false,
          isConnectionError: false,
          data: err.response.data || { error: `Server returned HTTP ${err.response.status}` },
          durationMs
        };
      } else {
        // Network or client connection failure (e.g. ECONNREFUSED, Network Error, timeout)
        return {
          status: null,
          success: false,
          isConnectionError: true,
          data: { error: err.message || 'Network connection failed' },
          durationMs
        };
      }
    }
  }
};
