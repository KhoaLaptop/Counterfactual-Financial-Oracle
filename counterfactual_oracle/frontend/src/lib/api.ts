import axios from 'axios';
import { Scenario, ScenarioStatus, Report, CreateScenarioRequest } from './types';

const api = axios.create({
    baseURL: '/api',
});

export const reportsApi = {
    upload: async (file: File | null, jsonContent: string | null): Promise<Report> => {
        const formData = new FormData();
        if (file) {
            formData.append('file', file);
        }
        if (jsonContent) {
            formData.append('json_data', jsonContent);
        }
        const response = await api.post<Report>('/reports/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },
    get: async (id: string): Promise<Report> => {
        const response = await api.get<Report>(`/reports/${id}`);
        return response.data;
    },
    list: async (skip = 0, limit = 100): Promise<ReportSummary[]> => {
        const response = await api.get<ReportSummary[]>('/reports/', { params: { skip, limit } })
        return response.data
    },
    delete: async (id: string) => {
        await api.delete(`/reports/${id}`)
    },
};

export const scenariosApi = {
    create: async (data: CreateScenarioRequest): Promise<Scenario> => {
        const response = await api.post<Scenario>('/scenarios', data);
        return response.data;
    },
    get: async (id: string): Promise<Scenario> => {
        const response = await api.get<Scenario>(`/scenarios/${id}`);
        return response.data;
    },
    list: async (): Promise<Scenario[]> => {
        const response = await api.get<Scenario[]>('/scenarios/');
        return response.data;
    },
    getStatus: async (id: string): Promise<ScenarioStatus> => {
        const response = await api.get<ScenarioStatus>(`/scenarios/${id}/status`);
        return response.data;
    },
    generateReport: async (id: string): Promise<Blob> => {
        const response = await api.get(`/scenarios/${id}/report`, {
            responseType: 'blob',
        });
        return response.data;
    },
};
