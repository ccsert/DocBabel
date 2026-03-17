import { useState, useEffect, useCallback } from 'react';
import { adminApi } from '../api';
import {
  Users,
  FileText,
  Activity,
  Clock,
  Download,
  HardDrive,
  RefreshCw,
  PackageOpen,
  TriangleAlert,
  Trash2,
  Ban,
  CheckCircle2,
  XCircle,
  Shield,
  ShieldOff,
} from 'lucide-react';

interface Stats {
  user_count: number;
  task_count: number;
  running_tasks: number;
  queued_tasks: number;
}

interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface Task {
  id: number;
  user_id: number;
  status: string;
  original_filename: string;
  lang_in: string;
  lang_out: string;
  progress: number;
  created_at: string;
}

interface OfflineAssetTypeStatus {
  total: number;
  present: number;
  missing: number;
  ready: boolean;
  missing_files: string[];
}

interface OfflineAssetsStatus {
  offline_mode: boolean;
  offline_assets_package_configured: boolean;
  profile: string;
  profile_description: string;
  ready: boolean;
  total_files: number;
  present_files: number;
  missing_files: number;
  missing_file_paths: string[];
  by_type: Record<string, OfflineAssetTypeStatus>;
  export: {
    status: 'idle' | 'running' | 'completed' | 'failed';
    step: string | null;
    message: string | null;
    started_at: string | null;
    finished_at: string | null;
    error: string | null;
    output_path: string | null;
    output_dir: string;
    latest_package: {
      path: string;
      filename: string;
      size_bytes: number;
      modified_at: string;
      download_path: string;
    } | null;
  };
}

export default function AdminPage() {
  const [tab, setTab] = useState<'dashboard' | 'users' | 'tasks'>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [offlineAssets, setOfflineAssets] = useState<OfflineAssetsStatus | null>(null);
  const [offlineLoading, setOfflineLoading] = useState(false);
  const [offlineActionLoading, setOfflineActionLoading] = useState<'check' | 'restore' | 'export' | 'download' | null>(null);
  const [offlineError, setOfflineError] = useState('');
  const [users, setUsers] = useState<User[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskTotal, setTaskTotal] = useState(0);
  const [taskPage, setTaskPage] = useState(1);

  const fetchStats = async () => {
    const res = await adminApi.stats();
    setStats(res.data);
  };

  const fetchOfflineAssets = useCallback(async () => {
    setOfflineLoading(true);
    setOfflineError('');
    try {
      const res = await adminApi.offlineAssetsStatus();
      setOfflineAssets(res.data);
    } catch (error) {
      setOfflineError(error instanceof Error ? error.message : '离线资源状态获取失败');
    } finally {
      setOfflineLoading(false);
    }
  }, []);

  const fetchUsers = async () => {
    const res = await adminApi.listUsers();
    setUsers(res.data);
  };

  const fetchTasks = useCallback(async () => {
    const res = await adminApi.listTasks({ page: taskPage, page_size: 20 });
    setTasks(res.data.tasks);
    setTaskTotal(res.data.total);
  }, [taskPage]);

  useEffect(() => {
    let active = true;

    void (async () => {
      const [statsRes, offlineRes] = await Promise.all([
        adminApi.stats(),
        adminApi.offlineAssetsStatus(),
      ]);
      if (active) {
        setStats(statsRes.data);
        setOfflineAssets(offlineRes.data);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (tab !== 'dashboard' || offlineAssets?.export.status !== 'running') {
      return undefined;
    }

    const timer = window.setInterval(() => {
      void fetchOfflineAssets();
    }, 3000);

    return () => {
      window.clearInterval(timer);
    };
  }, [tab, offlineAssets?.export.status, fetchOfflineAssets]);

  useEffect(() => {
    let active = true;

    void (async () => {
      if (tab === 'users') {
        const res = await adminApi.listUsers();
        if (active) {
          setUsers(res.data);
        }
      }

      if (tab === 'tasks') {
        const res = await adminApi.listTasks({ page: taskPage, page_size: 20 });
        if (active) {
          setTasks(res.data.tasks);
          setTaskTotal(res.data.total);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [tab, taskPage]);

  const toggleUserActive = async (user: User) => {
    await adminApi.updateUser(user.id, { is_active: !user.is_active });
    fetchUsers();
  };

  const toggleUserRole = async (user: User) => {
    await adminApi.updateUser(user.id, { role: user.role === 'admin' ? 'user' : 'admin' });
    fetchUsers();
  };

  const deleteUser = async (id: number) => {
    if (!confirm('确定要删除该用户吗？所有相关数据将被删除。')) return;
    await adminApi.deleteUser(id);
    fetchUsers();
    fetchStats();
  };

  const cancelTask = async (id: number) => {
    await adminApi.cancelTask(id);
    fetchTasks();
  };

  const checkOfflineAssets = async () => {
    setOfflineActionLoading('check');
    setOfflineError('');
    try {
      const res = await adminApi.checkOfflineAssets();
      setOfflineAssets(res.data);
    } catch (error) {
      setOfflineError(error instanceof Error ? error.message : '离线资源检查失败');
    } finally {
      setOfflineActionLoading(null);
    }
  };

  const restoreOfflineAssets = async () => {
    setOfflineActionLoading('restore');
    setOfflineError('');
    try {
      const res = await adminApi.restoreOfflineAssets();
      setOfflineAssets(res.data);
    } catch (error) {
      setOfflineError(error instanceof Error ? error.message : '离线资源恢复失败');
    } finally {
      setOfflineActionLoading(null);
    }
  };

  const exportOfflineAssets = async () => {
    setOfflineActionLoading('export');
    setOfflineError('');
    try {
      const res = await adminApi.exportOfflineAssets();
      setOfflineAssets(res.data);
    } catch (error) {
      setOfflineError(error instanceof Error ? error.message : '离线资源导出任务启动失败');
    } finally {
      setOfflineActionLoading(null);
    }
  };

  const downloadOfflineAssetsExport = async () => {
    if (!offlineAssets?.export.latest_package) return;
    setOfflineActionLoading('download');
    setOfflineError('');
    try {
      const token = localStorage.getItem('token');
      const resp = await fetch('/api/admin/offline-assets/export/download', {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!resp.ok) {
        throw new Error('离线资源包下载失败');
      }
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = offlineAssets.export.latest_package.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setOfflineError(error instanceof Error ? error.message : '离线资源包下载失败');
    } finally {
      setOfflineActionLoading(null);
    }
  };

  const formatDateTime = (value: string | null) => {
    if (!value) return '-';
    return new Date(value).toLocaleString();
  };

  const formatFileSize = (size: number) => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  const tabClass = (t: string) =>
    `px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
      tab === t ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-100'
    }`;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">系统管理</h1>

      {/* Tabs */}
      <div className="mb-6 flex gap-2">
        <button onClick={() => setTab('dashboard')} className={tabClass('dashboard')}>仪表盘</button>
        <button onClick={() => setTab('users')} className={tabClass('users')}>用户管理</button>
        <button onClick={() => setTab('tasks')} className={tabClass('tasks')}>任务管理</button>
      </div>

      {/* Dashboard */}
      {tab === 'dashboard' && stats && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[
              { icon: Users, label: '用户总数', value: stats.user_count, color: 'text-blue-600 bg-blue-50' },
              { icon: FileText, label: '任务总数', value: stats.task_count, color: 'text-purple-600 bg-purple-50' },
              { icon: Activity, label: '运行中', value: stats.running_tasks, color: 'text-green-600 bg-green-50' },
              { icon: Clock, label: '排队中', value: stats.queued_tasks, color: 'text-yellow-600 bg-yellow-50' },
            ].map((item) => (
              <div key={item.label} className="rounded-xl bg-white p-5 ring-1 ring-gray-200">
                <div className={`inline-flex rounded-lg p-2.5 ${item.color}`}>
                  <item.icon className="h-5 w-5" />
                </div>
                <p className="mt-3 text-2xl font-bold text-gray-900">{item.value}</p>
                <p className="text-sm text-gray-500">{item.label}</p>
              </div>
            ))}
          </div>

          <div className="rounded-xl bg-white p-5 ring-1 ring-gray-200">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <HardDrive className="h-5 w-5 text-gray-700" />
                  <h2 className="text-lg font-semibold text-gray-900">离线资源状态</h2>
                </div>
                <p className="mt-1 text-sm text-gray-500">展示当前服务器上 BabelDOC 离线资源完整度，可用于离线部署前检查。</p>
                {offlineAssets && (
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                    <span className="inline-flex rounded-full bg-gray-100 px-2.5 py-1 font-medium text-gray-700">
                      Profile: {offlineAssets.profile}
                    </span>
                    <span className="text-gray-500">{offlineAssets.profile_description}</span>
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={fetchOfflineAssets}
                  disabled={offlineLoading || offlineActionLoading !== null}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  <RefreshCw className="h-4 w-4" />
                  刷新状态
                </button>
                <button
                  type="button"
                  onClick={checkOfflineAssets}
                  disabled={offlineActionLoading !== null}
                  className="inline-flex items-center gap-2 rounded-lg border border-blue-200 px-3 py-2 text-sm text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                >
                  <RefreshCw className={`h-4 w-4 ${offlineActionLoading === 'check' ? 'animate-spin' : ''}`} />
                  重新检查
                </button>
                <button
                  type="button"
                  onClick={restoreOfflineAssets}
                  disabled={offlineActionLoading !== null || !offlineAssets?.offline_assets_package_configured}
                  className="inline-flex items-center gap-2 rounded-lg border border-amber-200 px-3 py-2 text-sm text-amber-700 hover:bg-amber-50 disabled:opacity-50"
                >
                  <PackageOpen className={`h-4 w-4 ${offlineActionLoading === 'restore' ? 'animate-pulse' : ''}`} />
                  恢复离线包
                </button>
                <button
                  type="button"
                  onClick={exportOfflineAssets}
                  disabled={offlineActionLoading !== null || offlineAssets?.export.status === 'running'}
                  className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 px-3 py-2 text-sm text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                >
                  <PackageOpen className={`h-4 w-4 ${offlineActionLoading === 'export' || offlineAssets?.export.status === 'running' ? 'animate-pulse' : ''}`} />
                  预热并导出离线包
                </button>
              </div>
            </div>

            {offlineError && (
              <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {offlineError}
              </div>
            )}

            {offlineAssets && (
              <>
                <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
                  {[
                    {
                      label: '离线模式',
                      value: offlineAssets.offline_mode ? '开启' : '关闭',
                      color: offlineAssets.offline_mode ? 'text-amber-700 bg-amber-50' : 'text-gray-700 bg-gray-50',
                    },
                    {
                      label: '资源状态',
                      value: offlineAssets.ready ? '已就绪' : '未完成',
                      color: offlineAssets.ready ? 'text-green-700 bg-green-50' : 'text-red-700 bg-red-50',
                    },
                    {
                      label: '已就绪文件',
                      value: `${offlineAssets.present_files}/${offlineAssets.total_files}`,
                      color: 'text-blue-700 bg-blue-50',
                    },
                    {
                      label: '缺失文件',
                      value: String(offlineAssets.missing_files),
                      color: offlineAssets.missing_files === 0 ? 'text-green-700 bg-green-50' : 'text-red-700 bg-red-50',
                    },
                  ].map((item) => (
                    <div key={item.label} className="rounded-xl border border-gray-100 p-4">
                      <div className={`inline-flex rounded-lg px-2.5 py-1 text-sm font-medium ${item.color}`}>{item.value}</div>
                      <p className="mt-2 text-sm text-gray-500">{item.label}</p>
                    </div>
                  ))}
                </div>

                <div className="mt-5 grid gap-4 lg:grid-cols-4">
                  {Object.entries(offlineAssets.by_type).map(([type, status]) => (
                    <div key={type} className="rounded-xl border border-gray-100 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-semibold uppercase tracking-wide text-gray-700">{type}</p>
                        {status.ready ? (
                          <span className="inline-flex items-center rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">完整</span>
                        ) : (
                          <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">缺失 {status.missing}</span>
                        )}
                      </div>
                      <p className="mt-3 text-sm text-gray-600">{status.present}/{status.total} 已就绪</p>
                      {!status.ready && status.missing_files.length > 0 && (
                        <div className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                          <div className="flex items-start gap-2">
                            <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <div>
                              {status.missing_files.slice(0, 3).map((file) => (
                                <p key={file} className="truncate">{file}</p>
                              ))}
                              {status.missing_files.length > 3 && (
                                <p>还有 {status.missing_files.length - 3} 个缺失文件</p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {!offlineAssets.ready && offlineAssets.missing_file_paths.length > 0 && (
                  <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
                    <p className="text-sm font-medium text-amber-800">缺失文件预览</p>
                    <div className="mt-2 grid gap-1 text-xs text-amber-700 lg:grid-cols-2">
                      {offlineAssets.missing_file_paths.slice(0, 12).map((file) => (
                        <p key={file} className="truncate">{file}</p>
                      ))}
                    </div>
                    {offlineAssets.missing_file_paths.length > 12 && (
                      <p className="mt-2 text-xs text-amber-700">还有 {offlineAssets.missing_file_paths.length - 12} 个缺失文件未展示。</p>
                    )}
                  </div>
                )}

                {offlineAssets.profile !== 'full' && (
                  <div className="mt-5 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
                    当前使用的是 {offlineAssets.profile} 预检档位。这个档位会降低离线准备成本，但不保证所有 PDF 处理资源都已经齐全。
                  </div>
                )}

                <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-900">离线资源导出</h3>
                      <p className="mt-1 text-sm text-gray-600">该操作会先联网预热全部 BabelDOC 运行资产，再生成完整离线 zip 包，适合带到纯离线环境使用。</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${
                        offlineAssets.export.status === 'completed'
                          ? 'bg-green-50 text-green-700'
                          : offlineAssets.export.status === 'failed'
                            ? 'bg-red-50 text-red-700'
                            : offlineAssets.export.status === 'running'
                              ? 'bg-amber-50 text-amber-700'
                              : 'bg-gray-100 text-gray-700'
                      }`}>
                        {offlineAssets.export.status === 'completed'
                          ? '已完成'
                          : offlineAssets.export.status === 'failed'
                            ? '失败'
                            : offlineAssets.export.status === 'running'
                              ? '执行中'
                              : '未开始'}
                      </span>
                      <button
                        type="button"
                        onClick={downloadOfflineAssetsExport}
                        disabled={offlineActionLoading !== null || !offlineAssets.export.latest_package || offlineAssets.export.status === 'running'}
                        className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                      >
                        <Download className={`h-4 w-4 ${offlineActionLoading === 'download' ? 'animate-bounce' : ''}`} />
                        下载最新离线包
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-lg border border-gray-200 bg-white p-4">
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">任务状态</p>
                      <p className="mt-2 text-sm text-gray-900">{offlineAssets.export.message || '暂无导出任务'}</p>
                      <dl className="mt-3 space-y-2 text-sm text-gray-600">
                        <div className="flex items-start justify-between gap-4">
                          <dt>当前步骤</dt>
                          <dd className="text-right text-gray-900">{offlineAssets.export.step || '-'}</dd>
                        </div>
                        <div className="flex items-start justify-between gap-4">
                          <dt>开始时间</dt>
                          <dd className="text-right text-gray-900">{formatDateTime(offlineAssets.export.started_at)}</dd>
                        </div>
                        <div className="flex items-start justify-between gap-4">
                          <dt>结束时间</dt>
                          <dd className="text-right text-gray-900">{formatDateTime(offlineAssets.export.finished_at)}</dd>
                        </div>
                        <div className="flex items-start justify-between gap-4">
                          <dt>输出目录</dt>
                          <dd className="max-w-[60%] break-all text-right text-gray-900">{offlineAssets.export.output_dir}</dd>
                        </div>
                        <div className="flex items-start justify-between gap-4">
                          <dt>目标文件</dt>
                          <dd className="max-w-[60%] break-all text-right text-gray-900">{offlineAssets.export.output_path || '-'}</dd>
                        </div>
                      </dl>
                      {offlineAssets.export.error && (
                        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                          {offlineAssets.export.error}
                        </div>
                      )}
                    </div>

                    <div className="rounded-lg border border-gray-200 bg-white p-4">
                      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">最新离线包</p>
                      {offlineAssets.export.latest_package ? (
                        <dl className="mt-3 space-y-2 text-sm text-gray-600">
                          <div className="flex items-start justify-between gap-4">
                            <dt>文件名</dt>
                            <dd className="max-w-[60%] break-all text-right text-gray-900">{offlineAssets.export.latest_package.filename}</dd>
                          </div>
                          <div className="flex items-start justify-between gap-4">
                            <dt>大小</dt>
                            <dd className="text-right text-gray-900">{formatFileSize(offlineAssets.export.latest_package.size_bytes)}</dd>
                          </div>
                          <div className="flex items-start justify-between gap-4">
                            <dt>更新时间</dt>
                            <dd className="text-right text-gray-900">{formatDateTime(offlineAssets.export.latest_package.modified_at)}</dd>
                          </div>
                          <div className="flex items-start justify-between gap-4">
                            <dt>文件路径</dt>
                            <dd className="max-w-[60%] break-all text-right text-gray-900">{offlineAssets.export.latest_package.path}</dd>
                          </div>
                        </dl>
                      ) : (
                        <p className="mt-2 text-sm text-gray-600">当前还没有已生成的离线资源包。</p>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Users */}
      {tab === 'users' && (
        <div className="overflow-hidden rounded-xl bg-white ring-1 ring-gray-200">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-700">用户名</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">邮箱</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">角色</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">状态</th>
                <th className="px-4 py-3 text-left font-medium text-gray-700">注册时间</th>
                <th className="px-4 py-3 text-right font-medium text-gray-700">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{u.username}</td>
                  <td className="px-4 py-3 text-gray-500">{u.email}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      u.role === 'admin' ? 'bg-purple-50 text-purple-600' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {u.role === 'admin' ? '管理员' : '用户'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {u.is_active ? (
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        type="button"
                        onClick={() => toggleUserRole(u)}
                        aria-label={u.role === 'admin' ? '降为用户' : '升为管理员'}
                        title={u.role === 'admin' ? '降为用户' : '升为管理员'}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        {u.role === 'admin' ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleUserActive(u)}
                        aria-label={u.is_active ? '禁用用户' : '启用用户'}
                        title={u.is_active ? '禁用' : '启用'}
                        className="rounded p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                      >
                        <Ban className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteUser(u.id)}
                        aria-label="删除用户"
                        title="删除用户"
                        className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tasks */}
      {tab === 'tasks' && (
        <div>
          <div className="overflow-hidden rounded-xl bg-white ring-1 ring-gray-200">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">ID</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">文件名</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">用户</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">语言</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">状态</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">进度</th>
                  <th className="px-4 py-3 text-left font-medium text-gray-700">时间</th>
                  <th className="px-4 py-3 text-right font-medium text-gray-700">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {tasks.map((t) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-500">#{t.id}</td>
                    <td className="max-w-48 truncate px-4 py-3 font-medium text-gray-900">{t.original_filename}</td>
                    <td className="px-4 py-3 text-gray-500">{t.user_id}</td>
                    <td className="px-4 py-3 text-gray-500">{t.lang_in}→{t.lang_out}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        t.status === 'completed' ? 'bg-green-50 text-green-600' :
                        t.status === 'running' ? 'bg-blue-50 text-blue-600' :
                        t.status === 'failed' ? 'bg-red-50 text-red-600' :
                        'bg-gray-100 text-gray-600'
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{t.progress.toFixed(0)}%</td>
                    <td className="px-4 py-3 text-gray-500">{new Date(t.created_at).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      {['pending', 'queued', 'running'].includes(t.status) && (
                        <button
                          onClick={() => cancelTask(t.id)}
                          className="rounded-lg border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                        >
                          取消
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {taskTotal > 20 && (
            <div className="mt-4 flex items-center justify-center gap-2">
              <button onClick={() => setTaskPage((p) => Math.max(1, p - 1))} disabled={taskPage === 1} className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50">上一页</button>
              <span className="text-sm text-gray-500">{taskPage} / {Math.ceil(taskTotal / 20)}</span>
              <button onClick={() => setTaskPage((p) => p + 1)} disabled={taskPage * 20 >= taskTotal} className="rounded-lg border px-3 py-1.5 text-sm disabled:opacity-50">下一页</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
