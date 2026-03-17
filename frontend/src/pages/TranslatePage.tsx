import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { tasksApi, glossariesApi, modelsApi } from '../api';
import { Upload, FileUp, Settings2, ChevronDown, ChevronUp } from 'lucide-react';

interface SelectOption {
  id: number;
  name: string;
}

interface ApiErrorLike {
  response?: {
    status?: number;
    data?: {
      detail?: string | { code?: string; existing_task_id?: number; has_mono?: boolean; has_dual?: boolean };
    };
  };
}

const LANGUAGES = [
  { value: 'en', label: '英语' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日语' },
  { value: 'ko', label: '韩语' },
  { value: 'fr', label: '法语' },
  { value: 'de', label: '德语' },
  { value: 'es', label: '西班牙语' },
  { value: 'pt', label: '葡萄牙语' },
  { value: 'ru', label: '俄语' },
  { value: 'ar', label: '阿拉伯语' },
  { value: 'it', label: '意大利语' },
];

export default function TranslatePage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [langIn, setLangIn] = useState('en');
  const [langOut, setLangOut] = useState('zh');
  const [modelId, setModelId] = useState<string>('');
  const [glossaryId, setGlossaryId] = useState<string>('');
  const [pages, setPages] = useState('');
  const [extraBody, setExtraBody] = useState('');
  const [noDual, setNoDual] = useState(false);
  const [noMono, setNoMono] = useState(false);
  const [enhanceCompat, setEnhanceCompat] = useState(false);
  const [ocrWorkaround, setOcrWorkaround] = useState(false);
  const [autoExtract, setAutoExtract] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [duplicateInfo, setDuplicateInfo] = useState<{
    existingTaskId: number;
    hasMono: boolean;
    hasDual: boolean;
  } | null>(null);
  const [requireConfigChangeForRegenerate, setRequireConfigChangeForRegenerate] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);

  const [glossaries, setGlossaries] = useState<SelectOption[]>([]);
  const [models, setModels] = useState<SelectOption[]>([]);

  const getApiError = (err: unknown) => err as ApiErrorLike;

  useEffect(() => {
    glossariesApi.list().then((r) => setGlossaries(r.data));
    modelsApi.list().then((r) => {
      setModels(r.data);
      if (r.data.length > 0) {
        setModelId(String(r.data[0].id));
      }
    });
  }, []);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f && f.name.toLowerCase().endsWith('.pdf')) setFile(f);
  };

  const triggerDownload = async (taskId: number, type: 'mono' | 'dual') => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(taskId, type);
    const a = document.createElement('a');
    a.download = '';
    const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!resp.ok) throw new Error('下载失败');
    const blob = await resp.blob();
    const objUrl = URL.createObjectURL(blob);
    a.href = objUrl;
    a.click();
    URL.revokeObjectURL(objUrl);
  };

  const buildFormData = (opts?: { reuseExisting?: boolean; forceRegenerate?: boolean }) => {
    if (!file) return null;
    const formData = new FormData();
    formData.append('file', file);
    formData.append('lang_in', langIn);
    formData.append('lang_out', langOut);
    if (modelId) formData.append('model_id', modelId);
    if (glossaryId) formData.append('glossary_id', glossaryId);
    if (pages) formData.append('pages', pages);
    if (extraBody.trim()) formData.append('extra_body', extraBody.trim());
    formData.append('no_dual', String(noDual));
    formData.append('no_mono', String(noMono));
    formData.append('enhance_compatibility', String(enhanceCompat));
    formData.append('ocr_workaround', String(ocrWorkaround));
    formData.append('auto_extract_glossary', String(autoExtract));
    if (customPrompt) formData.append('custom_system_prompt', customPrompt);
    if (opts?.reuseExisting) formData.append('reuse_existing', 'true');
    if (opts?.forceRegenerate || requireConfigChangeForRegenerate) {
      formData.append('force_regenerate', 'true');
    }
    return formData;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    if (!modelId) {
      setError('请先选择一个已配置模型');
      return;
    }
    setError('');
    setLoading(true);
    const formData = buildFormData();
    if (!formData) {
      setLoading(false);
      return;
    }

    try {
      await tasksApi.create(formData);
      navigate('/tasks');
    } catch (err: unknown) {
      const apiError = getApiError(err);
      const detail = apiError.response?.data?.detail;
      if (
        apiError.response?.status === 409
        && typeof detail !== 'string'
        && detail?.code === 'duplicate_translation_exists'
        && typeof detail.existing_task_id === 'number'
      ) {
        setDuplicateInfo({
          existingTaskId: detail.existing_task_id,
          hasMono: Boolean(detail.has_mono),
          hasDual: Boolean(detail.has_dual),
        });
      } else {
        setError(typeof detail === 'string' ? detail : '提交失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReuseAndDownload = async () => {
    const formData = buildFormData({ reuseExisting: true });
    if (!formData) return;
    setModalLoading(true);
    setError('');
    try {
      const res = await tasksApi.create(formData);
      const task = res.data;
      const downloadType: 'mono' | 'dual' | null = task.output_mono_filename ? 'mono' : (task.output_dual_filename ? 'dual' : null);
      if (downloadType) {
        await triggerDownload(task.id, downloadType);
      }
      setDuplicateInfo(null);
      setRequireConfigChangeForRegenerate(false);
      navigate('/tasks');
    } catch (err: unknown) {
      const detail = getApiError(err).response?.data?.detail;
      setError(typeof detail === 'string' ? detail : '复用失败');
    } finally {
      setModalLoading(false);
    }
  };

  const handleRegenerateChoice = () => {
    setDuplicateInfo(null);
    setRequireConfigChangeForRegenerate(true);
    setError('已选择重新生成。请修改任一翻译配置后再次提交，例如术语表、页码、提示词、extra_body、输出选项或模型参数。');
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">翻译文档</h1>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* File Upload */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 transition-colors ${
            dragOver ? 'border-blue-400 bg-blue-50' : 'border-gray-300 bg-white'
          }`}
        >
          {file ? (
            <div className="text-center">
              <FileUp className="mx-auto h-10 w-10 text-blue-500" />
              <p className="mt-2 text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="mt-2 text-xs text-red-500 hover:text-red-600"
              >
                移除
              </button>
            </div>
          ) : (
            <label className="cursor-pointer text-center">
              <Upload className="mx-auto h-10 w-10 text-gray-400" />
              <p className="mt-2 text-sm font-medium text-gray-700">
                拖拽 PDF 文件到此处或{' '}
                <span className="text-blue-600">点击上传</span>
              </p>
              <p className="mt-1 text-xs text-gray-500">仅支持 PDF 格式</p>
              <input
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
              />
            </label>
          )}
        </div>

        {/* Language Selection */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">源语言</label>
            <select
              title="源语言"
              value={langIn}
              onChange={(e) => setLangIn(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">目标语言</label>
            <select
              title="目标语言"
              value={langOut}
              onChange={(e) => setLangOut(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Model & Glossary */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">翻译模型</label>
            <select
              title="翻译模型"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              disabled={models.length === 0}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              {models.length === 0 && <option value="">暂无可用模型，请先到模型页创建</option>}
              {models.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            {models.length === 0 && (
              <div className="mt-2 flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="text-xs text-amber-700">请先在“模型”页面创建至少一个模型配置，再提交翻译任务。</p>
                <button
                  type="button"
                  onClick={() => navigate('/models')}
                  className="shrink-0 rounded-md border border-amber-300 bg-white px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
                >
                  前往模型页
                </button>
              </div>
            )}
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">术语表</label>
            <select
              title="术语表"
              value={glossaryId}
              onChange={(e) => setGlossaryId(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">不使用</option>
              {glossaries.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Advanced settings */}
        <div className="rounded-xl bg-white ring-1 ring-gray-200">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex w-full items-center justify-between px-5 py-3 text-sm font-medium text-gray-700"
          >
            <span className="flex items-center gap-2">
              <Settings2 className="h-4 w-4" />
              高级选项
            </span>
            {showAdvanced ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>

          {showAdvanced && (
            <div className="border-t border-gray-100 px-5 py-4 space-y-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">页码范围</label>
                <input
                  type="text"
                  value={pages}
                  onChange={(e) => setPages(e.target.value)}
                  placeholder="例如: 1-5,8,10-"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">extra_body (JSON)</label>
                <textarea
                  value={extraBody}
                  onChange={(e) => setExtraBody(e.target.value)}
                  placeholder='{"reasoning": {"effort": "high"}}'
                  rows={3}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">传递给翻译 API 的额外参数，会覆盖模型配置中的 extra_body</p>
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">自定义系统提示词</label>
                <textarea
                  title="自定义系统提示词"
                  placeholder="可选：补充领域约束、术语风格或输出要求"
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={noDual} onChange={(e) => setNoDual(e.target.checked)} className="rounded border-gray-300" />
                  不生成双语 PDF
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={noMono} onChange={(e) => setNoMono(e.target.checked)} className="rounded border-gray-300" />
                  不生成纯译文 PDF
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={enhanceCompat} onChange={(e) => setEnhanceCompat(e.target.checked)} className="rounded border-gray-300" />
                  增强兼容性
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input type="checkbox" checked={ocrWorkaround} onChange={(e) => setOcrWorkaround(e.target.checked)} className="rounded border-gray-300" />
                  OCR 模式
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-700 col-span-2">
                  <input type="checkbox" checked={autoExtract} onChange={(e) => setAutoExtract(e.target.checked)} className="rounded border-gray-300" />
                  <span>
                    自动提取术语
                    <span className="ml-1.5 text-xs text-gray-400">翻译前 AI 提取专业术语，保障全文一致性，完成后可保存到术语表</span>
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>
        )}

        <button
          type="submit"
          disabled={!file || !modelId || loading}
          className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? '提交中...' : '开始翻译'}
        </button>
      </form>

      {duplicateInfo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-xl rounded-2xl bg-white shadow-2xl">
            <div className="border-b border-gray-100 px-6 py-4">
              <h2 className="text-lg font-semibold text-gray-900">检测到已有译文</h2>
              <p className="mt-1 text-sm text-gray-600">
                该 PDF 在相同翻译配置下已有译文，可直接复用结果；如果你修改了术语表或其他翻译参数，也可以重新提交。
              </p>
            </div>
            <div className="px-6 py-4 text-sm text-gray-700 space-y-2">
              <p>已有任务 ID: {duplicateInfo.existingTaskId}</p>
              <p>可下载文件: {duplicateInfo.hasMono ? '译文 PDF ' : ''}{duplicateInfo.hasDual ? '双语 PDF' : ''}</p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-gray-100 px-6 py-4">
              <button
                type="button"
                onClick={() => setDuplicateInfo(null)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleRegenerateChoice}
                className="rounded-lg border border-orange-300 px-4 py-2 text-sm font-medium text-orange-700 hover:bg-orange-50"
              >
                重新生成（需修改配置）
              </button>
              <button
                type="button"
                onClick={handleReuseAndDownload}
                disabled={modalLoading}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {modalLoading ? '处理中...' : '直接复用并下载'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
