import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  getIncidents: async () => {
    const res = await apiClient.get('/incidents');
    return res.data;
  },
  getIncident: async (id: string) => {
    const res = await apiClient.get(`/incidents/${id}`);
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
  }
};
