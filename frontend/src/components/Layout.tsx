import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  FileText,
  Upload,
  Archive,
  BookOpen,
  Cpu,
  Shield,
  LogOut,
  Menu,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '../use-auth';

const navItems = [
  { to: '/', icon: Upload, label: '翻译' },
  { to: '/files', icon: Archive, label: '文件库' },
  { to: '/tasks', icon: FileText, label: '任务' },
  { to: '/glossaries', icon: BookOpen, label: '术语表' },
  { to: '/models', icon: Cpu, label: '模型' },
];

export default function Layout() {
  const { user, logout, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
      isActive
        ? 'bg-blue-50 text-blue-700'
        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
    }`;

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white transition-transform lg:static lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-16 items-center gap-2 border-b border-gray-200 px-6">
          <FileText className="h-6 w-6 text-blue-600" />
          <span className="text-lg font-bold text-gray-900">BabelDOC</span>
        </div>

        <nav className="flex-1 space-y-1 p-4">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClass} onClick={() => setSidebarOpen(false)}>
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
          {isAdmin && (
            <NavLink to="/admin" className={linkClass} onClick={() => setSidebarOpen(false)}>
              <Shield className="h-5 w-5" />
              管理
            </NavLink>
          )}
        </nav>

        <div className="border-t border-gray-200 p-4">
          <div className="mb-3 px-4">
            <p className="text-sm font-medium text-gray-900">{user?.username}</p>
            <p className="text-xs text-gray-500">{user?.email}</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-sm font-medium text-gray-600 transition-colors hover:bg-red-50 hover:text-red-600"
          >
            <LogOut className="h-5 w-5" />
            退出登录
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-16 items-center border-b border-gray-200 bg-white px-6 lg:hidden">
          <button onClick={() => setSidebarOpen(true)} className="text-gray-600">
            {sidebarOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
          <span className="ml-4 text-lg font-bold text-gray-900">BabelDOC</span>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
