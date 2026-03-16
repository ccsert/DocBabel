import { useState, useEffect } from 'react';
import { modelsApi, type ModelData } from '../api';
import { Plus, Trash2, Pencil, Cpu, X, Zap, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../use-auth';

interface Model {
  id: number;
  name: string;
  model_name: string;
  base_url: string | null;
  extra_body: Record<string, unknown> | null;
  send_temperature: boolean;
  temperature: number | null;
  reasoning: string | null;
  disable_thinking: boolean;
  enable_json_mode: boolean;
  created_at: string;
}

interface TestUsage {
  total_tokens?: number;
}

interface TestResult {
  success: boolean;
  result?: string;
  error?: string;
  model?: string;
  usage?: TestUsage;
}

interface ApiErrorLike {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

const defaultForm: ModelData = {
  name: '',
  model_name: '',
  base_url: '',
  api_key: '',
  extra_body: undefined,
  send_temperature: true,
  temperature: 0,
  reasoning: '',
  disable_thinking: false,
  enable_json_mode: false,
};

export default function ModelsPage() {
  const { isAdmin } = useAuth();
  const [models, setModels] = useState<Model[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<ModelData & { extra_body_str: string }>({ ...defaultForm, extra_body_str: '' });
  const [error, setError] = useState('');
  const [testing, setTesting] = useState<number | null>(null);
  const [testResult, setTestResult] = useState<Record<number, TestResult>>({});

  const getErrorDetail = (err: unknown, fallback: string) => {
    const apiError = err as ApiErrorLike;
    return apiError.response?.data?.detail || fallback;
  };

  const fetchModels = async () => {
    const res = await modelsApi.list();
    setModels(res.data);
  };

  useEffect(() => {
    fetchModels();
  }, []);

  const openCreate = () => {
    setEditId(null);
    setForm({ ...defaultForm, extra_body_str: '' });
    setShowForm(true);
    setError('');
  };

  const openEdit = (m: Model) => {
    setEditId(m.id);
    setForm({
      name: m.name,
      model_name: m.model_name,
      base_url: m.base_url || '',
      api_key: '',
      extra_body: m.extra_body || undefined,
      extra_body_str: m.extra_body ? JSON.stringify(m.extra_body, null, 2) : '',
      send_temperature: m.send_temperature,
      temperature: m.temperature ?? undefined,
      reasoning: m.reasoning || '',
      disable_thinking: m.disable_thinking,
      enable_json_mode: m.enable_json_mode,
    });
    setShowForm(true);
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    let extra_body: Record<string, unknown> | undefined;
    if (form.extra_body_str.trim()) {
      try {
        extra_body = JSON.parse(form.extra_body_str);
      } catch {
        setError('extra_body 必须为有效的 JSON');
        return;
      }
    }

    const data: ModelData = {
      name: form.name,
      model_name: form.model_name,
      base_url: form.base_url || undefined,
      api_key: form.api_key,
      extra_body,
      send_temperature: form.send_temperature,
      temperature: form.temperature,
      reasoning: form.reasoning || undefined,
      disable_thinking: form.disable_thinking,
      enable_json_mode: form.enable_json_mode,
    };

    try {
      if (editId) {
        const updateData: Partial<ModelData> = { ...data };
        if (!updateData.api_key) delete updateData.api_key;
        await modelsApi.update(editId, updateData);
      } else {
        await modelsApi.create(data);
      }
      setShowForm(false);
      fetchModels();
    } catch (err: unknown) {
      setError(getErrorDetail(err, '操作失败'));
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除该模型配置吗？')) return;
    await modelsApi.delete(id);
    fetchModels();
  };

  const handleTest = async (id: number) => {
    setTesting(id);
    setTestResult((prev) => { const next = { ...prev }; delete next[id]; return next; });
    try {
      const res = await modelsApi.testExisting(id);
      setTestResult((prev) => ({ ...prev, [id]: res.data }));
    } catch (err: unknown) {
      setTestResult((prev) => ({ ...prev, [id]: { success: false, error: getErrorDetail(err, '请求失败') } }));
    } finally {
      setTesting(null);
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">模型管理</h1>
        {isAdmin ? (
          <button
            onClick={openCreate}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            新建模型
          </button>
        ) : (
          <div className="rounded-lg bg-blue-50 px-4 py-2 text-sm text-blue-700">
            当前页面为只读，模型由管理员统一维护。
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {models.length === 0 ? (
          <div className="col-span-full rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">
            <Cpu className="mx-auto h-8 w-8 text-gray-300" />
            <p className="mt-2">暂无可用模型</p>
          </div>
        ) : (
          models.map((m) => (
            <div key={m.id} className="rounded-xl bg-white p-5 ring-1 ring-gray-200">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-medium text-gray-900">{m.name}</h3>
                  <p className="mt-1 text-xs text-gray-500 font-mono">{m.model_name}</p>
                </div>
                {isAdmin && (
                  <div className="flex gap-1">
                    <button
                      onClick={() => handleTest(m.id)}
                      disabled={testing === m.id}
                      title="测试连接"
                      className="rounded p-1.5 text-gray-400 hover:bg-green-50 hover:text-green-600 disabled:opacity-50"
                    >
                      {testing === m.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                    </button>
                    <button title="编辑模型" onClick={() => openEdit(m)} className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600">
                      <Pencil className="h-4 w-4" />
                    </button>
                    <button title="删除模型" onClick={() => handleDelete(m.id)} className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
              {m.base_url && (
                <p className="mt-2 truncate text-xs text-gray-400">{m.base_url}</p>
              )}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {m.reasoning && (
                  <span className="rounded-full bg-purple-50 px-2 py-0.5 text-xs text-purple-600">reasoning: {m.reasoning}</span>
                )}
                {m.extra_body && Object.keys(m.extra_body).length > 0 && (
                  <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-600">extra_body</span>
                )}
                {m.disable_thinking && (
                  <span className="rounded-full bg-orange-50 px-2 py-0.5 text-xs text-orange-600">no-thinking</span>
                )}
              </div>

              {testResult[m.id] && (
                <div className={`mt-3 rounded-lg p-3 text-xs ${
                  testResult[m.id].success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                }`}>
                  <div className="flex items-center gap-1.5 font-medium">
                    {testResult[m.id].success
                      ? <><CheckCircle2 className="h-3.5 w-3.5" /> 连接成功</>
                      : <><XCircle className="h-3.5 w-3.5" /> 连接失败</>
                    }
                  </div>
                  {testResult[m.id].success ? (
                    <div className="mt-1.5 space-y-0.5">
                      <p>输入: <span className="text-gray-500">Hello, world!</span></p>
                      <p>输出: <span className="font-medium">{testResult[m.id].result}</span></p>
                      {testResult[m.id].model && <p>模型: <span className="font-mono text-gray-500">{testResult[m.id].model}</span></p>}
                      {testResult[m.id].usage && <p>Token: {testResult[m.id].usage?.total_tokens}</p>}
                    </div>
                  ) : (
                    <p className="mt-1 break-all">{testResult[m.id].error}</p>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Create/Edit modal */}
      {showForm && isAdmin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/30 p-4">
          <form onSubmit={handleSubmit} className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                {editId ? '编辑模型' : '新建模型'}
              </h2>
              <button type="button" title="关闭" onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>

            {error && (
              <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>
            )}

            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">配置名称</label>
                <input
                  type="text"
                  title="配置名称"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">模型名称</label>
                <input
                  type="text"
                  title="模型名称"
                  value={form.model_name}
                  onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                  required
                  placeholder="gpt-4o-mini"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">API Base URL</label>
                <input
                  type="url"
                  title="API Base URL"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  placeholder="https://api.openai.com/v1"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">
                  API Key {editId && <span className="text-gray-400">(留空不修改)</span>}
                </label>
                <input
                  type="password"
                  title="API Key"
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  required={!editId}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">extra_body (JSON)</label>
                <textarea
                  title="extra_body JSON"
                  value={form.extra_body_str}
                  onChange={(e) => setForm({ ...form, extra_body_str: e.target.value })}
                  rows={3}
                  placeholder='{"reasoning": {"effort": "high"}, "stream": false}'
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">自定义传递给 API 的额外参数</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Reasoning</label>
                  <select
                    title="Reasoning"
                    value={form.reasoning || ''}
                    onChange={(e) => setForm({ ...form, reasoning: e.target.value || undefined })}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
                  >
                    <option value="">不启用</option>
                    <option value="minimal">minimal</option>
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Temperature</label>
                  <input
                    type="number"
                    title="Temperature"
                    step="0.1"
                    min="0"
                    max="2"
                    value={form.temperature ?? 0}
                    onChange={(e) => setForm({ ...form, temperature: parseFloat(e.target.value) })}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="flex flex-wrap gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    title="发送 temperature"
                    checked={form.send_temperature}
                    onChange={(e) => setForm({ ...form, send_temperature: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  发送 temperature
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    title="禁用 thinking"
                    checked={form.disable_thinking}
                    onChange={(e) => setForm({ ...form, disable_thinking: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  禁用 thinking
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    title="JSON 模式"
                    checked={form.enable_json_mode}
                    onChange={(e) => setForm({ ...form, enable_json_mode: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  JSON 模式
                </label>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                {editId ? '保存' : '创建'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
