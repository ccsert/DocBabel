import { useCallback, useEffect, useMemo, useState } from 'react';
import { filesApi, tasksApi } from '../api';
import { Archive, Calendar, Download, Search } from 'lucide-react';

interface FileItem {
  file_hash: string;
  original_filename: string;
  latest_task_id: number;
  latest_created_at: string;
  latest_completed_at: string | null;
  latest_duration_seconds: number | null;
  task_count: number;
  output_mono_filename: string | null;
  output_dual_filename: string | null;
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

export default function FilesPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [q, setQ] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const res = await filesApi.list({
        q: q || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      });
      setFiles(res.data.files);
    } finally {
      setLoading(false);
    }
  }, [endDate, q, startDate]);

  useEffect(() => {
    void fetchFiles();
  }, [fetchFiles]);

  const totalTranslations = useMemo(
    () => files.reduce((sum, item) => sum + item.task_count, 0),
    [files],
  );

  const handleDownload = (taskId: number, type: 'mono' | 'dual') => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(taskId, type);
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.blob())
      .then((blob) => {
        const obj = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = obj;
        a.click();
        URL.revokeObjectURL(obj);
      });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">文件库</h1>
          <p className="mt-1 text-sm text-gray-500">集中查看你已经翻译过的文档与可复用结果。</p>
        </div>
        <div className="rounded-xl bg-white px-4 py-3 ring-1 ring-gray-200">
          <p className="text-xs text-gray-500">已归档文件</p>
          <p className="text-lg font-semibold text-gray-900">{files.length}</p>
          <p className="text-xs text-gray-400">累计翻译记录 {totalTranslations}</p>
        </div>
      </div>

      <div className="grid gap-3 rounded-2xl bg-white p-4 ring-1 ring-gray-200 md:grid-cols-[1.5fr_1fr_1fr_auto]">
        <label className="relative block">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            title="文件名搜索"
            placeholder="按文档名称搜索"
            className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm"
          />
        </label>
        <input type="date" title="开始日期" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        <input type="date" title="结束日期" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm" />
        <button type="button" onClick={fetchFiles} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          查询
        </button>
      </div>

      {loading ? (
        <div className="rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">加载中...</div>
      ) : files.length === 0 ? (
        <div className="rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">
          <Archive className="mx-auto h-10 w-10 text-gray-300" />
          <p className="mt-3">暂无已翻译文档</p>
        </div>
      ) : (
        <div className="space-y-3">
          {files.map((item) => (
            <div key={item.file_hash} className="rounded-2xl bg-white p-5 ring-1 ring-gray-200">
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-base font-semibold text-gray-900">{item.original_filename}</h3>
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
                    <span className="inline-flex items-center gap-1"><Calendar className="h-3.5 w-3.5" />最近完成 {item.latest_completed_at ? new Date(item.latest_completed_at).toLocaleString() : '-'}</span>
                    <span>累计译文版本 {item.task_count}</span>
                    <span>最近耗时 {formatDuration(item.latest_duration_seconds)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {item.output_mono_filename && (
                    <button onClick={() => handleDownload(item.latest_task_id, 'mono')} className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">
                      <Download className="h-3.5 w-3.5" />译文
                    </button>
                  )}
                  {item.output_dual_filename && (
                    <button onClick={() => handleDownload(item.latest_task_id, 'dual')} className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">
                      <Download className="h-3.5 w-3.5" />双语
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
