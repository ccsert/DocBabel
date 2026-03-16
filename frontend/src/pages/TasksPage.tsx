import { useState, useEffect, useCallback } from 'react';
import { tasksApi } from '../api';
import {
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  Download,
  Ban,
  RefreshCw,
} from 'lucide-react';

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
  queue_position: number | null;
  created_at: string;
  completed_at: string | null;
  output_mono_filename: string | null;
  output_dual_filename: string | null;
}

const statusConfig: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  pending: { icon: Clock, label: '等待中', color: 'text-yellow-600 bg-yellow-50' },
  queued: { icon: Clock, label: '排队中', color: 'text-yellow-600 bg-yellow-50' },
  running: { icon: Loader2, label: '翻译中', color: 'text-blue-600 bg-blue-50' },
  completed: { icon: CheckCircle2, label: '已完成', color: 'text-green-600 bg-green-50' },
  failed: { icon: XCircle, label: '失败', color: 'text-red-600 bg-red-50' },
  cancelled: { icon: Ban, label: '已取消', color: 'text-gray-600 bg-gray-50' },
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filterStatus, setFilterStatus] = useState('');

  const fetchTasks = useCallback(async () => {
    const params: Record<string, any> = { page, page_size: 20 };
    if (filterStatus) params.status = filterStatus;
    const res = await tasksApi.list(params);
    setTasks(res.data.tasks);
    setTotal(res.data.total);
  }, [page, filterStatus]);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  const handleCancel = async (id: number) => {
    await tasksApi.cancel(id);
    fetchTasks();
  };

  const handleDownload = (id: number, type: 'mono' | 'dual') => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(id, type);
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    // Use fetch for auth header
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const u = URL.createObjectURL(blob);
        a.href = u;
        a.click();
        URL.revokeObjectURL(u);
      });
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">翻译任务</h1>
        <div className="flex items-center gap-3">
          <select
            value={filterStatus}
            onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm"
          >
            <option value="">全部状态</option>
            <option value="pending">等待中</option>
            <option value="running">翻译中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
          <button
            onClick={fetchTasks}
            className="rounded-lg border border-gray-300 bg-white p-2 text-gray-600 hover:bg-gray-50"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="space-y-3">
        {tasks.length === 0 ? (
          <div className="rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">
            暂无翻译任务
          </div>
        ) : (
          tasks.map((task) => {
            const sc = statusConfig[task.status] || statusConfig.pending;
            const Icon = sc.icon;
            return (
              <div
                key={task.id}
                className="rounded-xl bg-white p-5 ring-1 ring-gray-200"
              >
                <div className="flex items-start justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="truncate text-sm font-medium text-gray-900">
                        {task.original_filename}
                      </h3>
                      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${sc.color}`}>
                        <Icon className={`h-3.5 w-3.5 ${task.status === 'running' ? 'animate-spin' : ''}`} />
                        {sc.label}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {task.lang_in} → {task.lang_out} · {new Date(task.created_at).toLocaleString()}
                    </p>

                    {task.status === 'running' && (
                      <div className="mt-3">
                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{task.progress_message || '翻译中...'}</span>
                          <span>{task.progress.toFixed(1)}%</span>
                        </div>
                        <div className="mt-1 h-1.5 rounded-full bg-gray-100">
                          <div
                            className="h-1.5 rounded-full bg-blue-500 transition-all"
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {task.status === 'failed' && task.error_message && (
                      <p className="mt-2 text-xs text-red-500">{task.error_message}</p>
                    )}

                    {task.token_usage && (
                      <p className="mt-1 text-xs text-gray-400">
                        Token: {task.token_usage.total_tokens?.toLocaleString()}
                      </p>
                    )}
                  </div>

                  <div className="ml-4 flex items-center gap-2">
                    {task.status === 'completed' && (
                      <>
                        {task.output_mono_filename && (
                          <button
                            onClick={() => handleDownload(task.id, 'mono')}
                            className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                          >
                            <Download className="h-3.5 w-3.5" />
                            译文
                          </button>
                        )}
                        {task.output_dual_filename && (
                          <button
                            onClick={() => handleDownload(task.id, 'dual')}
                            className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                          >
                            <Download className="h-3.5 w-3.5" />
                            双语
                          </button>
                        )}
                      </>
                    )}
                    {['pending', 'queued', 'running'].includes(task.status) && (
                      <button
                        onClick={() => handleCancel(task.id)}
                        className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50"
                      >
                        取消
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="mt-6 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            上一页
          </button>
          <span className="text-sm text-gray-500">
            {page} / {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * 20 >= total}
            className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
