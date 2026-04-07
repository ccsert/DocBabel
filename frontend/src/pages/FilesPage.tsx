import { useCallback, useEffect, useMemo, useState } from 'react';
import { filesApi, tasksApi, type BatchFileType } from '../api';
import { Archive, Calendar, Download, Eye, Search, CheckSquare, Square } from 'lucide-react';

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

async function getBlobErrorDetail(err: unknown, fallback: string) {
  const apiError = err as { response?: { data?: Blob } };
  const blob = apiError.response?.data;
  if (!(blob instanceof Blob)) return fallback;

  try {
    const payload = JSON.parse(await blob.text()) as { detail?: string | { message?: string } };
    if (typeof payload.detail === 'string') return payload.detail;
    if (payload.detail?.message) return payload.detail.message;
  } catch {
    return fallback;
  }

  return fallback;
}

export default function FilesPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [q, setQ] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedTaskIds, setSelectedTaskIds] = useState<Set<number>>(new Set());
  const [batchFileType, setBatchFileType] = useState<BatchFileType>('mono');
  const [batchDownloading, setBatchDownloading] = useState(false);
  const [batchError, setBatchError] = useState('');

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

  const selectableTaskIds = useMemo(
    () => files
      .filter((item) => (batchFileType === 'mono' ? Boolean(item.output_mono_filename) : Boolean(item.output_dual_filename)))
      .map((item) => item.latest_task_id),
    [batchFileType, files],
  );

  useEffect(() => {
    setSelectedTaskIds((current) => new Set(Array.from(current).filter((id) => selectableTaskIds.includes(id))));
  }, [selectableTaskIds]);

  const handleDownload = async (taskId: number, type: 'mono' | 'dual', filename: string) => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(taskId, type);
    try {
      const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (!r.ok) throw new Error('下载失败');
      const blob = await r.blob();
      const obj = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = obj;
      const stem = filename.replace(/\.[^.]+$/, '');
      a.download = `${stem}_${type === 'mono' ? '译文' : '双语'}.pdf`;
      a.click();
      URL.revokeObjectURL(obj);
    } catch {
      alert('文件下载失败，请重试');
    }
  };

  const handlePreview = async (taskId: number, type: 'mono' | 'dual') => {
    const token = localStorage.getItem('token');
    const url = tasksApi.downloadUrl(taskId, type);
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

  const toggleSelection = (taskId: number) => {
    setSelectedTaskIds((current) => {
      const next = new Set(current);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  const handleBatchDownload = async () => {
    if (selectedTaskIds.size === 0) return;
    setBatchDownloading(true);
    setBatchError('');
    try {
      const response = await tasksApi.batchDownload({
        task_ids: Array.from(selectedTaskIds),
        file_type: batchFileType,
      });
      const blob = new Blob([response.data], { type: 'application/zip' });
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `archive_batch_${batchFileType === 'mono' ? '译文' : '双语'}.zip`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (err: unknown) {
      setBatchError(await getBlobErrorDetail(err, '批量下载失败，请调整选择后重试'));
    } finally {
      setBatchDownloading(false);
    }
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

      <div className="rounded-2xl bg-white p-4 ring-1 ring-gray-200">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900">批量下载归档文件</p>
            <p className="mt-1 text-xs text-gray-500">按文件库中的最新版本打包下载。</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <select title="批量下载文件类型" value={batchFileType} onChange={(e) => setBatchFileType(e.target.value as BatchFileType)} className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm">
              <option value="mono">译文 PDF</option>
              <option value="dual">双语 PDF</option>
            </select>
            <button type="button" onClick={() => setSelectedTaskIds(new Set(selectableTaskIds))} disabled={selectableTaskIds.length === 0} className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
              <CheckSquare className="h-4 w-4" />全选当前结果
            </button>
            <button type="button" onClick={() => setSelectedTaskIds(new Set())} disabled={selectedTaskIds.size === 0} className="inline-flex items-center justify-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50">
              <Square className="h-4 w-4" />清空选择
            </button>
            <button type="button" onClick={handleBatchDownload} disabled={selectedTaskIds.size === 0 || batchDownloading} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
              {batchDownloading ? '打包中...' : `下载选中 ZIP (${selectedTaskIds.size})`}
            </button>
          </div>
        </div>
        {batchError && <p className="mt-3 text-sm text-red-600">{batchError}</p>}
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
                <div className="md:pt-1">
                  <input
                    type="checkbox"
                    checked={selectedTaskIds.has(item.latest_task_id)}
                    disabled={batchFileType === 'mono' ? !item.output_mono_filename : !item.output_dual_filename}
                    onChange={() => toggleSelection(item.latest_task_id)}
                    title="选择该文件用于批量下载"
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 disabled:cursor-not-allowed disabled:opacity-40"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-base font-semibold text-gray-900">{item.original_filename}</h3>
                  <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500">
                    <span className="inline-flex items-center gap-1"><Calendar className="h-3.5 w-3.5" />最近完成 {item.latest_completed_at ? new Date(item.latest_completed_at).toLocaleString() : '-'}</span>
                    <span>累计译文版本 {item.task_count}</span>
                    <span>最近耗时 {formatDuration(item.latest_duration_seconds)}</span>
                  </div>
                  {batchFileType === 'mono' && !item.output_mono_filename && <p className="mt-2 text-xs text-gray-400">该文件没有可下载的纯译文 PDF</p>}
                  {batchFileType === 'dual' && !item.output_dual_filename && <p className="mt-2 text-xs text-gray-400">该文件没有可下载的双语 PDF</p>}
                </div>
                <div className="flex items-center gap-2">
                  {item.output_mono_filename && (
                    <div className="inline-flex overflow-hidden rounded-lg border border-gray-300 divide-x divide-gray-300">
                      <button onClick={() => handlePreview(item.latest_task_id, 'mono')} title="在新标签页预览译文" className="flex items-center gap-1 px-2.5 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">
                        <Eye className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => handleDownload(item.latest_task_id, 'mono', item.original_filename)} title="下载译文 PDF" className="flex items-center gap-1 px-2.5 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">
                        <Download className="h-3.5 w-3.5" />译文
                      </button>
                    </div>
                  )}
                  {item.output_dual_filename && (
                    <div className="inline-flex overflow-hidden rounded-lg border border-gray-300 divide-x divide-gray-300">
                      <button onClick={() => handlePreview(item.latest_task_id, 'dual')} title="在新标签页预览双语文档" className="flex items-center gap-1 px-2.5 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">
                        <Eye className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => handleDownload(item.latest_task_id, 'dual', item.original_filename)} title="下载双语 PDF" className="flex items-center gap-1 px-2.5 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50">
                        <Download className="h-3.5 w-3.5" />双语
                      </button>
                    </div>
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
