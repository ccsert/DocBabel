import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { tasksApi } from '../api';
import {
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  Download,
  Ban,
  RefreshCw,
  Sparkles,
  BookOpen,
  Trash2,
  Search,
  Eye,
} from 'lucide-react';

interface ApiErrorLike {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

interface Task {
  id: number;
  status: string;
  original_filename: string;
  lang_in: string;
  lang_out: string;
  progress: number;
  progress_message: string | null;
  error_message: string | null;
  token_usage: Record<string, number> | null;
  duration_seconds: number | null;
  queue_position: number | null;
  created_at: string;
  completed_at: string | null;
  output_mono_filename: string | null;
  output_dual_filename: string | null;
  auto_extract_glossary: boolean;
  extracted_glossary_data: Array<{ source: string; target: string }> | null;
}

const statusConfig: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  pending: { icon: Clock, label: '等待中', color: 'text-yellow-600 bg-yellow-50' },
  queued: { icon: Clock, label: '排队中', color: 'text-yellow-600 bg-yellow-50' },
  running: { icon: Loader2, label: '翻译中', color: 'text-blue-600 bg-blue-50' },
  completed: { icon: CheckCircle2, label: '已完成', color: 'text-green-600 bg-green-50' },
  failed: { icon: XCircle, label: '失败', color: 'text-red-600 bg-red-50' },
  cancelled: { icon: Ban, label: '已取消', color: 'text-gray-600 bg-gray-50' },
};

function toDateInputValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDuration(seconds: number | null) {
  if (!seconds || seconds <= 0) return '秒完成/未记录';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const minutes = Math.floor(seconds / 60);
  const remain = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes} 分 ${remain} 秒`;
  const hours = Math.floor(minutes / 60);
  return `${hours} 小时 ${minutes % 60} 分`;
}

function getErrorDetail(err: unknown, fallback: string) {
  const apiError = err as ApiErrorLike;
  return apiError.response?.data?.detail || fallback;
}

export default function TasksPage() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [query, setQuery] = useState('');
  const [startDate, setStartDate] = useState(toDateInputValue(new Date(Date.now() - 3 * 24 * 60 * 60 * 1000)));
  const [endDate, setEndDate] = useState(toDateInputValue(new Date()));

  const [saveModal, setSaveModal] = useState<{ task: Task } | null>(null);
  const [glossaryName, setGlossaryName] = useState('');
  const [savingGlossary, setSavingGlossary] = useState(false);
  const [saveError, setSaveError] = useState('');

  const fetchTasks = useCallback(async () => {
    const params: Record<string, string | number> = {
      page,
      page_size: 100,
      start_date: startDate,
      end_date: endDate,
    };
    if (filterStatus) params.status = filterStatus;
    if (query) params.q = query;
    const res = await tasksApi.list(params);
    setTasks(res.data.tasks);
    setTotal(res.data.total);
  }, [page, filterStatus, query, startDate, endDate]);

  const hasActiveRef = useRef(false);
  hasActiveRef.current = tasks.some((t) => ['running', 'queued', 'pending'].includes(t.status));

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, hasActiveRef.current ? 3000 : 10000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  const groupedTasks = useMemo(() => {
    const groups = new Map<string, Task[]>();
    for (const task of tasks) {
      const key = new Date(task.created_at).toLocaleDateString();
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(task);
    }
    return Array.from(groups.entries());
  }, [tasks]);

  const handleCancel = async (id: number) => {
    await tasksApi.cancel(id);
    fetchTasks();
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除该任务记录吗？删除后将无法恢复。')) return;
    await tasksApi.delete(id);
    fetchTasks();
  };

  const openSaveModal = (task: Task) => {
    const stem = task.original_filename.replace(/\.pdf$/i, '');
    setGlossaryName(`${stem}_术语`);
    setSaveError('');
    setSaveModal({ task });
  };

  const handleSaveGlossary = async () => {
    if (!saveModal || !glossaryName.trim()) return;
    setSavingGlossary(true);
    setSaveError('');
    try {
      await tasksApi.saveGlossary(saveModal.task.id, glossaryName.trim());
      setSaveModal(null);
      navigate('/glossaries');
    } catch (err: unknown) {
      setSaveError(getErrorDetail(err, '保存失败'));
    } finally {
      setSavingGlossary(false);
    }
  };

  const handleDownload = async (id: number, type: 'mono' | 'dual', filename: string) => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(id, type);
    try {
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error('下载失败');
      const blob = await r.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = u;
      const stem = filename.replace(/\.[^.]+$/, '');
      a.download = `${stem}_${type === 'mono' ? '译文' : '双语'}.pdf`;
      a.click();
      URL.revokeObjectURL(u);
    } catch {
      alert('文件下载失败，请重试');
    }
  };

  const handlePreview = async (id: number, type: 'mono' | 'dual') => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(id, type);
    try {
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error('预览失败');
      const blob = new Blob([await r.blob()], { type: 'application/pdf' });
      const u = URL.createObjectURL(blob);
      window.open(u, '_blank');
    } catch {
      alert('文件预览失败，请重试');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">翻译任务</h1>
          <p className="mt-1 text-sm text-gray-500">默认展示近三天任务，可按日期范围、状态和文件名筛选，并按日期分组查看。</p>
        </div>
        <div className="rounded-xl bg-white px-4 py-3 ring-1 ring-gray-200">
          <p className="text-xs text-gray-500">当前结果</p>
          <p className="text-lg font-semibold text-gray-900">{total}</p>
        </div>
      </div>

      <div className="grid gap-3 rounded-2xl bg-white p-4 ring-1 ring-gray-200 xl:grid-cols-[1.4fr_1fr_1fr_180px_auto]">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            title="任务名称搜索"
            placeholder="按文档名称搜索"
            className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm"
          />
        </label>
        <input type="date" title="开始日期" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        <input type="date" title="结束日期" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        <select title="任务状态筛选" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">
          <option value="">全部状态</option>
          <option value="pending">等待中</option>
          <option value="running">翻译中</option>
          <option value="completed">已完成</option>
          <option value="failed">失败</option>
          <option value="cancelled">已取消</option>
        </select>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => { setQuery(searchValue.trim()); setPage(1); }} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">查询</button>
          <button type="button" title="刷新任务列表" aria-label="刷新任务列表" onClick={fetchTasks} className="rounded-lg border border-gray-300 bg-white p-2 text-gray-600 hover:bg-gray-50"><RefreshCw className="h-4 w-4" /></button>
        </div>
      </div>

      {groupedTasks.length === 0 ? (
        <div className="rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">当前筛选条件下暂无任务</div>
      ) : (
        <div className="space-y-6">
          {groupedTasks.map(([dateKey, items]) => (
            <section key={dateKey} className="space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-semibold text-gray-900">{dateKey}</h2>
                <div className="h-px flex-1 bg-gray-200" />
                <span className="text-xs text-gray-400">{items.length} 个任务</span>
              </div>

              {items.map((task) => {
                const sc = statusConfig[task.status] || statusConfig.pending;
                const Icon = sc.icon;
                return (
                  <div key={task.id} className="rounded-xl bg-white p-5 ring-1 ring-gray-200">
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-3">
                          <h3 className="truncate text-sm font-medium text-gray-900">{task.original_filename}</h3>
                          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${sc.color}`}>
                            <Icon className={`h-3.5 w-3.5 ${task.status === 'running' ? 'animate-spin' : ''}`} />
                            {sc.label}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-gray-500">{task.lang_in} → {task.lang_out} · 提交于 {new Date(task.created_at).toLocaleString()}</p>
                        <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-400">
                          <span>耗时: {formatDuration(task.duration_seconds)}</span>
                          {task.completed_at && <span>完成于: {new Date(task.completed_at).toLocaleString()}</span>}
                          {task.token_usage && <span>Token: {task.token_usage.total_tokens?.toLocaleString()}</span>}
                        </div>

                        {task.status === 'queued' && task.queue_position != null && (
                          <p className="mt-2 text-xs text-yellow-600">排队中，当前位置：第 {task.queue_position} 位</p>
                        )}

                        {task.status === 'running' && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between text-xs text-gray-500">
                              <span>{task.progress_message || '翻译中...'}</span>
                              <span>{task.progress.toFixed(1)}%</span>
                            </div>
                            <progress className="translation-progress mt-1" max={100} value={task.progress} />
                          </div>
                        )}

                        {task.status === 'failed' && task.error_message && (
                          <p className="mt-2 text-xs text-red-500">{task.error_message}</p>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center justify-end gap-2">
                        {task.status === 'completed' && task.output_mono_filename && (
                          <div className="inline-flex overflow-hidden rounded-lg border border-gray-300 divide-x divide-gray-300">
                            <button onClick={() => handlePreview(task.id, 'mono')} title="在新标签页预览译文" className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                              <Eye className="h-3.5 w-3.5" />
                            </button>
                            <button onClick={() => handleDownload(task.id, 'mono', task.original_filename)} title="下载译文 PDF" className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                              <Download className="h-3.5 w-3.5" />译文
                            </button>
                          </div>
                        )}
                        {task.status === 'completed' && task.output_dual_filename && (
                          <div className="inline-flex overflow-hidden rounded-lg border border-gray-300 divide-x divide-gray-300">
                            <button onClick={() => handlePreview(task.id, 'dual')} title="在新标签页预览双语文档" className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                              <Eye className="h-3.5 w-3.5" />
                            </button>
                            <button onClick={() => handleDownload(task.id, 'dual', task.original_filename)} title="下载双语 PDF" className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50">
                              <Download className="h-3.5 w-3.5" />双语
                            </button>
                          </div>
                        )}
                        {task.status === 'completed' && task.extracted_glossary_data && task.extracted_glossary_data.length > 0 && (
                          <button onClick={() => openSaveModal(task)} className="flex items-center gap-1 rounded-lg border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100"><Sparkles className="h-3.5 w-3.5" />保存术语表 ({task.extracted_glossary_data.length})</button>
                        )}
                        {['pending', 'queued', 'running'].includes(task.status) ? (
                          <button onClick={() => handleCancel(task.id)} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50">取消</button>
                        ) : (
                          <button onClick={() => handleDelete(task.id)} className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"><Trash2 className="h-3.5 w-3.5" />删除</button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </section>
          ))}
        </div>
      )}

      {saveModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="mx-4 w-full max-w-lg rounded-2xl bg-white shadow-xl">
            <div className="flex items-center gap-3 border-b border-gray-100 px-6 py-4">
              <Sparkles className="h-5 w-5 text-purple-500" />
              <h2 className="text-base font-semibold text-gray-900">保存自动提取的术语表</h2>
            </div>
            <div className="space-y-4 px-6 py-4">
              <div>
                <label className="mb-1.5 block text-sm font-medium text-gray-700">术语表名称</label>
                <input type="text" title="术语表名称" value={glossaryName} onChange={(e) => setGlossaryName(e.target.value)} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500" placeholder="请输入术语表名称" autoFocus />
              </div>
              <div>
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700"><BookOpen className="h-4 w-4" />共 {saveModal.task.extracted_glossary_data!.length} 个术语（预览前 20 条）</div>
                <div className="max-h-60 overflow-y-auto rounded-lg border border-gray-200 text-xs">
                  <table className="w-full">
                    <thead className="sticky top-0 bg-gray-50"><tr><th className="px-3 py-2 text-left font-medium text-gray-600">原文</th><th className="px-3 py-2 text-left font-medium text-gray-600">译文</th></tr></thead>
                    <tbody>
                      {saveModal.task.extracted_glossary_data!.slice(0, 20).map((term, i) => (
                        <tr key={i} className="border-t border-gray-100 hover:bg-gray-50"><td className="px-3 py-2 text-gray-800">{term.source}</td><td className="px-3 py-2 text-gray-800">{term.target}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              {saveError && <p className="text-sm text-red-500">{saveError}</p>}
            </div>
            <div className="flex justify-end gap-3 border-t border-gray-100 px-6 py-4">
              <button onClick={() => setSaveModal(null)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">取消</button>
              <button onClick={handleSaveGlossary} disabled={savingGlossary || !glossaryName.trim()} className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50">
                {savingGlossary ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}保存到术语表
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
