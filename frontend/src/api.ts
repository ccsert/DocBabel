import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;

// ─── Auth ────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  register: (username: string, email: string, password: string) =>
    api.post('/auth/register', { username, email, password }),
  me: () => api.get('/auth/me'),
};

// ─── Tasks ───────────────────────────────────────────────
export const tasksApi = {
  create: (formData: FormData) =>
    api.post('/tasks', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  list: (params?: { status?: string; q?: string; start_date?: string; end_date?: string; page?: number; page_size?: number }) =>
    api.get('/tasks', { params }),
  get: (id: number) => api.get(`/tasks/${id}`),
  cancel: (id: number) => api.post(`/tasks/${id}/cancel`),
  delete: (id: number) => api.delete(`/tasks/${id}`),
  downloadUrl: (id: number, fileType: 'mono' | 'dual') =>
    `/api/tasks/${id}/download/${fileType}`,
  saveGlossary: (id: number, name: string, description?: string) =>
    api.post(`/tasks/${id}/save-glossary`, { name, description }),
};

export const filesApi = {
  list: (params?: { q?: string; start_date?: string; end_date?: string }) =>
    api.get('/files', { params }),
};

// ─── Glossaries ──────────────────────────────────────────
export const glossariesApi = {
  list: () => api.get('/glossaries'),
  create: (data: { name: string; description?: string; is_collaborative?: boolean; entries?: Array<{ source: string; target: string; target_language?: string }> }) =>
    api.post('/glossaries', data),
  get: (id: number) => api.get(`/glossaries/${id}`),
  update: (id: number, data: { name?: string; description?: string; is_collaborative?: boolean }) =>
    api.patch(`/glossaries/${id}`, data),
  delete: (id: number) => api.delete(`/glossaries/${id}`),
  addEntry: (glossaryId: number, data: { source: string; target: string; target_language?: string }) =>
    api.post(`/glossaries/${glossaryId}/entries`, data),
  updateEntry: (glossaryId: number, entryId: number, data: { source?: string; target?: string; target_language?: string | null }) =>
    api.patch(`/glossaries/${glossaryId}/entries/${entryId}`, data),
  contribute: (glossaryId: number, data: { source: string; target: string; target_language?: string }) =>
    api.post(`/glossaries/${glossaryId}/contributions`, data),
  approveContribution: (glossaryId: number, contributionId: number, review_note?: string) =>
    api.post(`/glossaries/${glossaryId}/contributions/${contributionId}/approve`, { review_note }),
  rejectContribution: (glossaryId: number, contributionId: number, review_note?: string) =>
    api.post(`/glossaries/${glossaryId}/contributions/${contributionId}/reject`, { review_note }),
  deleteEntry: (glossaryId: number, entryId: number) =>
    api.delete(`/glossaries/${glossaryId}/entries/${entryId}`),
  importFile: (glossaryId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/glossaries/${glossaryId}/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// ─── Models ──────────────────────────────────────────────
export interface ModelData {
  name: string;
  model_name: string;
  base_url?: string;
  api_key: string;
  extra_body?: Record<string, unknown>;
  send_temperature?: boolean;
  temperature?: number;
  reasoning?: string;
  disable_thinking?: boolean;
  enable_json_mode?: boolean;
}

export const modelsApi = {
  list: () => api.get('/models'),
  create: (data: ModelData) => api.post('/models', data),
  get: (id: number) => api.get(`/models/${id}`),
  update: (id: number, data: Partial<ModelData>) => api.patch(`/models/${id}`, data),
  delete: (id: number) => api.delete(`/models/${id}`),
  test: (data: Partial<ModelData>) => api.post('/models/test', data),
  testExisting: (id: number) => api.post(`/models/${id}/test`),
};

// ─── Admin ───────────────────────────────────────────────
export const adminApi = {
  stats: () => api.get('/admin/stats'),
  listUsers: () => api.get('/admin/users'),
  updateUser: (id: number, data: { email?: string; is_active?: boolean; role?: string }) =>
    api.patch(`/admin/users/${id}`, data),
  deleteUser: (id: number) => api.delete(`/admin/users/${id}`),
  listTasks: (params?: { status?: string; page?: number; page_size?: number }) =>
    api.get('/admin/tasks', { params }),
  cancelTask: (id: number) => api.post(`/admin/tasks/${id}/cancel`),
};
