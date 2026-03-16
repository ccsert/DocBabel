import { useState, useEffect } from 'react';
import { glossariesApi } from '../api';
import { Plus, Trash2, BookOpen, X } from 'lucide-react';

interface GlossaryEntry {
  id: number;
  source: string;
  target: string;
  target_language: string | null;
}

interface GlossarySet {
  id: number;
  name: string;
  description: string | null;
  entries: GlossaryEntry[];
  created_at: string;
  updated_at: string;
}

export default function GlossariesPage() {
  const [glossaries, setGlossaries] = useState<GlossarySet[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newSource, setNewSource] = useState('');
  const [newTarget, setNewTarget] = useState('');

  const fetchGlossaries = async () => {
    const res = await glossariesApi.list();
    setGlossaries(res.data);
  };

  useEffect(() => {
    fetchGlossaries();
  }, []);

  const selected = glossaries.find((g) => g.id === selectedId);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await glossariesApi.create({ name: newName, description: newDesc || undefined });
    setNewName('');
    setNewDesc('');
    setShowCreate(false);
    fetchGlossaries();
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除该术语表吗？')) return;
    await glossariesApi.delete(id);
    if (selectedId === id) setSelectedId(null);
    fetchGlossaries();
  };

  const handleAddEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) return;
    await glossariesApi.addEntry(selectedId, { source: newSource, target: newTarget });
    setNewSource('');
    setNewTarget('');
    fetchGlossaries();
  };

  const handleDeleteEntry = async (entryId: number) => {
    if (!selectedId) return;
    await glossariesApi.deleteEntry(selectedId, entryId);
    fetchGlossaries();
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">术语表管理</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          新建术语表
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Glossary List */}
        <div className="space-y-2">
          {glossaries.length === 0 ? (
            <div className="rounded-xl bg-white p-8 text-center text-sm text-gray-500 ring-1 ring-gray-200">
              <BookOpen className="mx-auto h-8 w-8 text-gray-300" />
              <p className="mt-2">暂无术语表</p>
            </div>
          ) : (
            glossaries.map((g) => (
              <div
                key={g.id}
                onClick={() => setSelectedId(g.id)}
                className={`cursor-pointer rounded-xl bg-white p-4 ring-1 transition-colors ${
                  selectedId === g.id ? 'ring-blue-500' : 'ring-gray-200 hover:ring-gray-300'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">{g.name}</h3>
                    <p className="text-xs text-gray-500">{g.entries.length} 条词条</p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(g.id); }}
                    className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Glossary Detail */}
        <div className="lg:col-span-2">
          {selected ? (
            <div className="rounded-xl bg-white p-6 ring-1 ring-gray-200">
              <h2 className="mb-1 text-lg font-semibold text-gray-900">{selected.name}</h2>
              {selected.description && (
                <p className="mb-4 text-sm text-gray-500">{selected.description}</p>
              )}

              {/* Add entry form */}
              <form onSubmit={handleAddEntry} className="mb-4 flex gap-2">
                <input
                  type="text"
                  value={newSource}
                  onChange={(e) => setNewSource(e.target.value)}
                  placeholder="原文术语"
                  required
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <input
                  type="text"
                  value={newTarget}
                  onChange={(e) => setNewTarget(e.target.value)}
                  placeholder="译文"
                  required
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                >
                  添加
                </button>
              </form>

              {/* Entries table */}
              <div className="overflow-hidden rounded-lg border border-gray-200">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2.5 text-left font-medium text-gray-700">原文</th>
                      <th className="px-4 py-2.5 text-left font-medium text-gray-700">译文</th>
                      <th className="w-12 px-4 py-2.5"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {selected.entries.length === 0 ? (
                      <tr>
                        <td colSpan={3} className="px-4 py-8 text-center text-gray-400">
                          暂无词条
                        </td>
                      </tr>
                    ) : (
                      selected.entries.map((entry) => (
                        <tr key={entry.id} className="hover:bg-gray-50">
                          <td className="px-4 py-2.5 text-gray-900">{entry.source}</td>
                          <td className="px-4 py-2.5 text-gray-900">{entry.target}</td>
                          <td className="px-4 py-2.5">
                            <button
                              onClick={() => handleDeleteEntry(entry.id)}
                              className="rounded p-1 text-gray-400 hover:text-red-500"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">
              选择一个术语表查看详情
            </div>
          )}
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <form onSubmit={handleCreate} className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">新建术语表</h2>
            <div className="mb-4">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">名称</label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="mb-6">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">描述</label>
              <textarea
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
              >
                创建
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
