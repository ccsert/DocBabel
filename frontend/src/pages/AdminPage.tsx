import { useState, useEffect, useCallback } from 'react';
import { adminApi } from '../api';
import {
  Users,
  FileText,
  Activity,
  Clock,
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

export default function AdminPage() {
  const [tab, setTab] = useState<'dashboard' | 'users' | 'tasks'>('dashboard');
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskTotal, setTaskTotal] = useState(0);
  const [taskPage, setTaskPage] = useState(1);

  const fetchStats = async () => {
    const res = await adminApi.stats();
    setStats(res.data);
  };

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
      const res = await adminApi.stats();
      if (active) {
        setStats(res.data);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

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
