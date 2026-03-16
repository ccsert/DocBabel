import { useEffect, useMemo, useState } from 'react';
import { glossariesApi } from '../api';
import { Plus, Trash2, BookOpen, X, Upload, Download, Users, Check, MinusCircle, Pencil, Save } from 'lucide-react';

interface ApiErrorLike {
  response?: {
    data?: {
      detail?: string;
    };
  };
}

interface GlossaryEntry {
  id: number;
  source: string;
  target: string;
  target_language: string | null;
}

interface GlossaryContribution {
  id: number;
  glossary_set_id: number;
  proposer_user_id: number;
  source: string;
  target: string;
  target_language: string | null;
  status: string;
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
}

interface GlossarySet {
  id: number;
  name: string;
  description: string | null;
  is_collaborative: boolean;
  is_owner: boolean;
  entries: GlossaryEntry[];
  pending_contributions: GlossaryContribution[];
  created_at: string;
  updated_at: string;
}

export default function GlossariesPage() {
  const PAGE_SIZE = 12;
  const [glossaries, setGlossaries] = useState<GlossarySet[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newSource, setNewSource] = useState('');
  const [newTarget, setNewTarget] = useState('');
  const [newCollaborative, setNewCollaborative] = useState(false);
  const [editingMeta, setEditingMeta] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editingCell, setEditingCell] = useState<{ entryId: number; field: 'source' | 'target' } | null>(null);
  const [editingValue, setEditingValue] = useState('');
  const [entryPage, setEntryPage] = useState(1);

  const resetSelectionState = (glossary: GlossarySet | null) => {
    setSelectedId(glossary?.id ?? null);
    setEditingMeta(false);
    setEditingCell(null);
    setEditingValue('');
    setEntryPage(1);
    setEditName(glossary?.name ?? '');
    setEditDesc(glossary?.description || '');
  };

  const refreshGlossaries = async (preferredSelectedId?: number | null) => {
    const res = await glossariesApi.list();
    const nextGlossaries = res.data as GlossarySet[];
    setGlossaries(nextGlossaries);

    const nextSelected =
      nextGlossaries.find((item) => item.id === preferredSelectedId) ||
      nextGlossaries[0] ||
      null;

    resetSelectionState(nextSelected);
  };

  const handleSelectGlossary = (glossary: GlossarySet) => {
    resetSelectionState(glossary);
  };

  useEffect(() => {
    let active = true;

    void (async () => {
      const res = await glossariesApi.list();
      if (!active) {
        return;
      }

      const nextGlossaries = res.data as GlossarySet[];
      setGlossaries(nextGlossaries);
      resetSelectionState(nextGlossaries[0] || null);
    })();

    return () => {
      active = false;
    };
  }, []);

  const selected = useMemo(
    () => glossaries.find((g) => g.id === selectedId) ?? null,
    [glossaries, selectedId],
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await glossariesApi.create({ name: newName, description: newDesc || undefined, is_collaborative: newCollaborative });
    setNewName('');
    setNewDesc('');
    setNewCollaborative(false);
    setShowCreate(false);
    await refreshGlossaries();
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确定要删除该术语表吗？')) return;
    await glossariesApi.delete(id);
    await refreshGlossaries(selectedId === id ? null : selectedId);
  };

  const handleSaveMeta = async () => {
    if (!selectedId) return;
    await glossariesApi.update(selectedId, {
      name: editName.trim(),
      description: editDesc.trim() || undefined,
    });
    setEditingMeta(false);
    await refreshGlossaries(selectedId);
  };

  const handleAddEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedId) return;
    const res = await glossariesApi.addEntry(selectedId, { source: newSource, target: newTarget });
    setNewSource('');
    setNewTarget('');
    if (res.data?.mode === 'pending') {
      alert(res.data.detail || '已提交，等待创建者审核');
    }
    await refreshGlossaries(selectedId);
  };

  const handleDeleteEntry = async (entryId: number) => {
    if (!selectedId) return;
    await glossariesApi.deleteEntry(selectedId, entryId);
    await refreshGlossaries(selectedId);
  };

  const startEditCell = (entry: GlossaryEntry, field: 'source' | 'target') => {
    setEditingCell({ entryId: entry.id, field });
    setEditingValue(field === 'source' ? entry.source : entry.target);
  };

  const handleSaveCell = async (entry: GlossaryEntry) => {
    if (!selectedId || !editingCell || editingCell.entryId !== entry.id) return;
    const trimmedValue = editingValue.trim();
    const oldValue = editingCell.field === 'source' ? entry.source : entry.target;

    if (!trimmedValue || trimmedValue === oldValue) {
      setEditingCell(null);
      setEditingValue('');
      return;
    }

    await glossariesApi.updateEntry(selectedId, entry.id, {
      [editingCell.field]: trimmedValue,
    });
    setEditingCell(null);
    setEditingValue('');
    await refreshGlossaries(selectedId);
  };

  const pagedEntries = selected ? selected.entries.slice((entryPage - 1) * PAGE_SIZE, entryPage * PAGE_SIZE) : [];
  const totalEntryPages = selected ? Math.max(1, Math.ceil(selected.entries.length / PAGE_SIZE)) : 1;

  const handleApprove = async (contributionId: number) => {
    if (!selectedId) return;
    await glossariesApi.approveContribution(selectedId, contributionId);
    await refreshGlossaries(selectedId);
  };

  const handleReject = async (contributionId: number) => {
    if (!selectedId) return;
    await glossariesApi.rejectContribution(selectedId, contributionId);
    await refreshGlossaries(selectedId);
  };

  const handleToggleCollaborative = async (checked: boolean) => {
    if (!selectedId) return;
    await glossariesApi.update(selectedId, { is_collaborative: checked });
    await refreshGlossaries(selectedId);
  };

  const handleFileImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedId) return;
    try {
      await glossariesApi.importFile(selectedId, file);
      await refreshGlossaries(selectedId);
    } catch (err: unknown) {
      const apiError = err as ApiErrorLike;
      alert(apiError.response?.data?.detail || '导入失败');
    }
    e.target.value = '';
  };

  const downloadTemplate = () => {
    const csv = '原文,译文,目标语言\nArtificial Intelligence,人工智能,zh\nMachine Learning,机器学习,zh\n';
    const blob = new Blob([new Uint8Array([0xEF, 0xBB, 0xBF]), csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'glossary_template.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">术语表管理</h1>
          <p className="mt-1 text-sm text-gray-500">支持个人术语表与共创术语表，共创词条需创建者审核后生效。</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Plus className="h-4 w-4" />新建术语表
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-2">
          {glossaries.length === 0 ? (
            <div className="rounded-xl bg-white p-8 text-center text-sm text-gray-500 ring-1 ring-gray-200">
              <BookOpen className="mx-auto h-8 w-8 text-gray-300" />
              <p className="mt-2">暂无术语表</p>
            </div>
          ) : (
            glossaries.map((g) => (
              <div key={g.id} onClick={() => handleSelectGlossary(g)} className={`cursor-pointer rounded-xl bg-white p-4 ring-1 transition-colors ${selectedId === g.id ? 'ring-blue-500' : 'ring-gray-200 hover:ring-gray-300'}`}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-gray-900">{g.name}</h3>
                      {g.is_collaborative && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700"><Users className="h-3 w-3" />共创</span>}
                    </div>
                    <p className="text-xs text-gray-500">{g.entries.length} 条词条{g.pending_contributions.length > 0 ? ` · ${g.pending_contributions.length} 条待审核` : ''}</p>
                  </div>
                  {g.is_owner && (
                    <button type="button" title="删除术语表" aria-label="删除术语表" onClick={(e) => { e.stopPropagation(); void handleDelete(g.id); }} className="rounded p-1 text-gray-400 hover:bg-red-50 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="lg:col-span-2">
          {selected ? (
            <div className="rounded-xl bg-white p-6 ring-1 ring-gray-200">
              <div className="mb-4 flex flex-col gap-3 border-b border-gray-100 pb-4 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    {editingMeta ? (
                      <input title="术语表名称" value={editName} onChange={(e) => setEditName(e.target.value)} className="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-900" />
                    ) : (
                      <h2 className="text-lg font-semibold text-gray-900">{selected.name}</h2>
                    )}
                    {selected.is_collaborative && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700"><Users className="h-3 w-3" />共创已开启</span>}
                    {selected.is_owner && !editingMeta && (
                      <button type="button" title="编辑术语表" aria-label="编辑术语表" onClick={() => setEditingMeta(true)} className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"><Pencil className="h-4 w-4" /></button>
                    )}
                  </div>
                  {editingMeta ? (
                    <div className="mt-2 flex items-start gap-2">
                      <textarea title="术语表描述" value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700" placeholder="术语表描述" />
                      <button type="button" title="保存术语表" aria-label="保存术语表" onClick={() => void handleSaveMeta()} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"><Save className="h-4 w-4" /></button>
                    </div>
                  ) : (
                    selected.description && <p className="mt-1 text-sm text-gray-500">{selected.description}</p>
                  )}
                </div>
                {selected.is_owner && (
                  <label className="flex items-center gap-2 text-sm text-gray-700">
                    <input type="checkbox" checked={selected.is_collaborative} onChange={(e) => handleToggleCollaborative(e.target.checked)} className="rounded border-gray-300" />
                    开启共创策略
                  </label>
                )}
              </div>

              {selected.is_owner && (
                <div className="mb-4 flex items-center gap-2">
                  <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100">
                    <Upload className="h-4 w-4" />导入 CSV
                    <input title="导入词条文件" type="file" accept=".csv,.tsv,.txt" onChange={handleFileImport} className="hidden" />
                  </label>
                  <button type="button" onClick={downloadTemplate} className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"><Download className="h-4 w-4" />下载模板</button>
                  <span className="text-xs text-gray-400">支持 CSV / TSV，每行：原文, 译文[, 目标语言]</span>
                </div>
              )}

              <form onSubmit={handleAddEntry} className="mb-6 flex flex-col gap-2 md:flex-row">
                <input type="text" title="原文术语" value={newSource} onChange={(e) => setNewSource(e.target.value)} placeholder={selected.is_owner ? '原文术语' : '提交共创术语原文'} required className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                <input type="text" title="译文术语" value={newTarget} onChange={(e) => setNewTarget(e.target.value)} placeholder={selected.is_owner ? '译文' : '提交共创术语译文'} required className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
                <button type="submit" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">{selected.is_owner ? '添加词条' : '提交共创'}</button>
              </form>

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
                      <tr><td colSpan={3} className="px-4 py-8 text-center text-gray-400">暂无词条</td></tr>
                    ) : (
                      pagedEntries.map((entry) => (
                        <tr key={entry.id} className="hover:bg-gray-50">
                          <td className="px-4 py-2.5 text-gray-900">
                            {editingCell?.entryId === entry.id && editingCell.field === 'source' ? (
                              <input
                                title="编辑原文术语"
                                value={editingValue}
                                onChange={(e) => setEditingValue(e.target.value)}
                                onBlur={() => handleSaveCell(entry)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleSaveCell(entry);
                                  }
                                  if (e.key === 'Escape') {
                                    setEditingCell(null);
                                    setEditingValue('');
                                  }
                                }}
                                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                                autoFocus
                              />
                            ) : (
                              <button
                                type="button"
                                onClick={() => startEditCell(entry, 'source')}
                                className="w-full rounded px-1 py-1 text-left hover:bg-blue-50"
                              >
                                {entry.source}
                              </button>
                            )}
                          </td>
                          <td className="px-4 py-2.5 text-gray-900">
                            {editingCell?.entryId === entry.id && editingCell.field === 'target' ? (
                              <input
                                title="编辑译文术语"
                                value={editingValue}
                                onChange={(e) => setEditingValue(e.target.value)}
                                onBlur={() => handleSaveCell(entry)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleSaveCell(entry);
                                  }
                                  if (e.key === 'Escape') {
                                    setEditingCell(null);
                                    setEditingValue('');
                                  }
                                }}
                                className="w-full rounded border border-gray-300 px-2 py-1 text-sm"
                                autoFocus
                              />
                            ) : (
                              <button
                                type="button"
                                onClick={() => startEditCell(entry, 'target')}
                                className="w-full rounded px-1 py-1 text-left hover:bg-blue-50"
                              >
                                {entry.target}
                              </button>
                            )}
                          </td>
                          <td className="px-4 py-2.5">
                            {selected.is_owner && (
                              <div className="flex items-center gap-1">
                                <button type="button" title="编辑词条" aria-label="编辑词条" onClick={() => startEditCell(entry, 'source')} className="rounded p-1 text-gray-400 hover:text-gray-700"><Pencil className="h-4 w-4" /></button>
                                <button type="button" title="删除词条" aria-label="删除词条" onClick={() => void handleDeleteEntry(entry.id)} className="rounded p-1 text-gray-400 hover:text-red-500"><X className="h-4 w-4" /></button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {selected.entries.length > PAGE_SIZE && (
                <div className="mt-3 flex items-center justify-between text-sm text-gray-500">
                  <span>第 {entryPage} / {totalEntryPages} 页，共 {selected.entries.length} 条词条</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setEntryPage((p) => Math.max(1, p - 1))}
                      disabled={entryPage === 1}
                      className="rounded-lg border border-gray-300 px-3 py-1.5 disabled:opacity-50"
                    >
                      上一页
                    </button>
                    <button
                      type="button"
                      onClick={() => setEntryPage((p) => Math.min(totalEntryPages, p + 1))}
                      disabled={entryPage === totalEntryPages}
                      className="rounded-lg border border-gray-300 px-3 py-1.5 disabled:opacity-50"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              )}

              {selected.is_owner && selected.pending_contributions.length > 0 && (
                <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-amber-900">待你审核的共创词条</h3>
                  <div className="space-y-2">
                    {selected.pending_contributions.map((item) => (
                      <div key={item.id} className="flex flex-col gap-3 rounded-lg bg-white p-3 ring-1 ring-amber-100 md:flex-row md:items-center md:justify-between">
                        <div className="text-sm text-gray-700">
                          <span className="font-medium text-gray-900">{item.source}</span>
                          <span className="mx-2 text-gray-400">→</span>
                          <span>{item.target}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <button type="button" onClick={() => void handleApprove(item.id)} className="flex items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100"><Check className="h-3.5 w-3.5" />通过</button>
                          <button type="button" onClick={() => void handleReject(item.id)} className="flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"><MinusCircle className="h-3.5 w-3.5" />拒绝</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl bg-white p-12 text-center text-sm text-gray-500 ring-1 ring-gray-200">选择一个术语表查看详情</div>
          )}
        </div>
      </div>

      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <form onSubmit={handleCreate} className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">新建术语表</h2>
            <div className="mb-4">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">名称</label>
              <input type="text" title="术语表名称" value={newName} onChange={(e) => setNewName(e.target.value)} required className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div className="mb-4">
              <label className="mb-1.5 block text-sm font-medium text-gray-700">描述</label>
              <textarea title="术语表描述" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} rows={2} className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <label className="mb-6 flex items-center gap-2 text-sm text-gray-700">
              <input type="checkbox" checked={newCollaborative} onChange={(e) => setNewCollaborative(e.target.checked)} className="rounded border-gray-300" />
              创建为可共创术语表
            </label>
            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setShowCreate(false)} className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">取消</button>
              <button type="submit" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">创建</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
