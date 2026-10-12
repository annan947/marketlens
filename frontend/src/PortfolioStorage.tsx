import { useEffect, useState } from 'react';
import { api } from './api';
import { Status, useJob } from './ui';

export interface PortfolioDefinition {
  assets: string[]; dates: string[]; returns: number[][]; weights: number[];
  periods_per_year: number; risk_free_rate: number;
}
interface SavedSummary { id: string; name: string; notes: string; version: number; updated_at: string }
interface Saved extends SavedSummary { definition: PortfolioDefinition }
interface Listing { items: SavedSummary[]; total: number; offset: number; limit: number }

export default function PortfolioStorage({ getDefinition, onLoad, canSave }: {
  getDefinition: () => PortfolioDefinition; onLoad: (definition: PortfolioDefinition) => void; canSave: boolean;
}) {
  const list = useJob<Listing>();
  const action = useJob<string>();
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Saved | null>(null);
  const [name, setName] = useState('');
  const [notes, setNotes] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const refresh = () => list.run(signal => api(`/api/v1/saved-portfolios?limit=10&offset=${offset}`, undefined, signal));
  useEffect(() => { void refresh(); }, [offset]);
  const busy = action.busy;
  const save = (update: boolean) => action.run(async signal => {
    if (!name.trim()) throw new Error('Enter a name for the saved portfolio.');
    const body = { name: name.trim(), notes, definition: getDefinition() };
    const saved = await api<Saved>(update ? `/api/v1/saved-portfolios/${selected!.id}` : '/api/v1/saved-portfolios',
      update ? { ...body, version: selected!.version } : body, signal, update ? 'PUT' : undefined);
    if (!signal.aborted) { setSelected(saved); setConfirmDelete(false); void refresh(); }
    return update ? 'Portfolio updated.' : 'Portfolio saved.';
  });
  return <section className="storage" aria-label="Saved portfolios"><div className="storage-heading"><h3>Saved portfolios</h3><button type="button" className="secondary" disabled={list.busy || busy} onClick={refresh}>Refresh</button></div>
    <Status busy={list.busy} error={list.error} />
    {list.data && <><div className="saved-list">{list.data.items.map(item => <button type="button" key={item.id} disabled={busy} className={selected?.id === item.id ? 'selected' : ''} onClick={() => action.run(async signal => {
      const saved = await api<Saved>(`/api/v1/saved-portfolios/${item.id}`, undefined, signal);
      if (!signal.aborted) { setSelected(saved); setName(saved.name); setNotes(saved.notes); setConfirmDelete(false); onLoad(saved.definition); }
      return 'Portfolio loaded. Run analysis to calculate results.';
    })}><strong>{item.name}</strong><small>Version {item.version} · {new Date(item.updated_at).toLocaleDateString()}</small></button>)}</div>
      {list.data.total === 0 && <p className="footnote">No saved portfolios yet.</p>}
      <div className="storage-actions"><button type="button" className="secondary" disabled={!offset || busy || list.busy} onClick={() => setOffset(Math.max(0, offset-10))}>Previous</button><span>{list.data.total} saved</span><button type="button" className="secondary" disabled={offset+10 >= list.data.total || busy || list.busy} onClick={() => setOffset(offset+10)}>Next</button></div></>}
    <label className="field"><span>Portfolio name</span><input value={name} maxLength={120} onChange={event => { setName(event.target.value); action.clear(); }} disabled={busy} placeholder="e.g. Balanced research portfolio" /></label>
    <label className="field"><span>Research notes</span><textarea value={notes} rows={2} maxLength={2000} onChange={event => { setNotes(event.target.value); action.clear(); }} disabled={busy} /></label>
    <div className="storage-actions"><button type="button" className="secondary" disabled={busy || !canSave} onClick={() => save(false)}>Save as new</button>{selected && <button type="button" className="secondary" disabled={busy || !canSave} onClick={() => save(true)}>Update selected</button>}</div>
    {!canSave && <p className="footnote">Switch to Analyze allocation to save input weights. Optimized weights must first be applied to the analysis form.</p>}
    {selected && <div className="storage-actions"><span>Selected: {selected.name}</span><button type="button" className="danger" disabled={busy} onClick={() => setConfirmDelete(true)}>Delete selected</button></div>}
    {confirmDelete && selected && <div className="delete-confirm" role="group" aria-label="Confirm deletion"><p>Delete “{selected.name}” permanently?</p><div className="storage-actions"><button type="button" className="danger" disabled={busy} onClick={() => action.run(async signal => {
      await api<void>(`/api/v1/saved-portfolios/${selected.id}?version=${selected.version}`, undefined, signal, 'DELETE');
      if (!signal.aborted) { setSelected(null); setConfirmDelete(false); void refresh(); }
      return 'Saved portfolio deleted. Current form inputs were kept.';
    })}>Confirm delete</button><button type="button" className="secondary" disabled={busy} onClick={() => setConfirmDelete(false)}>Cancel</button></div></div>}
    <Status busy={action.busy} error={action.error} />{action.data && <p className="storage-success" role="status">{action.data}</p>}
  </section>;
}
