import { lazy, Suspense, type ComponentProps, useEffect, useRef, useState, type ReactNode, type FormEvent, type InputHTMLAttributes } from 'react';

export function useJob<T>() {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const clear = () => { controller.current?.abort(); setData(null); setError(''); setBusy(false); };
  const run = async (work: (signal: AbortSignal) => Promise<T>) => {
    controller.current?.abort();
    const current = new AbortController(); controller.current = current;
    setData(null); setError(''); setBusy(true);
    try { const result = await work(current.signal); if (!current.signal.aborted) setData(result); }
    catch (error) { if (!current.signal.aborted) setError(error instanceof Error ? error.message : 'Request failed.'); }
    finally { if (!current.signal.aborted) setBusy(false); }
  };
  return { data, error, busy, run, clear };
}
export function Field({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return <label className="field"><span>{label}</span><input required {...props} /></label>;
}
export function Num({ label, name, value, min, max, step = 'any' }: { label: string; name: string; value: number; min?: number; max?: number; step?: number | string }) {
  return <Field label={label} type="number" name={name} defaultValue={value} min={min} max={max} step={step} />;
}
export function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return <section className="panel"><div className="panel-heading"><h2>{title}</h2>{note && <span>{note}</span>}</div>{children}</section>;
}
export function Metrics({ items }: { items: [string, string][] }) {
  return <div className="metrics">{items.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}
export function Status({ busy, error, empty }: { busy: boolean; error: string; empty?: boolean }) {
  return <>{busy && <div className="notice" role="status"><span className="pulse" />Calculating with MarketLens…</div>}{error && <div className="error" role="alert">{error}</div>}{empty && !busy && !error && <div className="empty"><div className="empty-icon">⌁</div><h3>Your next insight starts here</h3><p>Set your inputs and run the analysis.<br />Results will appear in this workspace.</p></div>}</>;
}
export function Submit({ busy, children }: { busy: boolean; children: ReactNode }) {
  return <button className="primary" type="submit" disabled={busy}>{busy ? 'Working…' : children}<span aria-hidden="true">↗</span></button>;
}
export function formData(event: FormEvent<HTMLFormElement>) { event.preventDefault(); return new FormData(event.currentTarget); }

const LazyChart = lazy(() => import('./Chart'));
export function Chart(props: ComponentProps<typeof LazyChart>) {
  return <Suspense fallback={<div className="chart notice" role="status">Loading chart…</div>}><LazyChart {...props} /></Suspense>;
}
export function CsvInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [error, setError] = useState('');
  return <><label className="field"><span>Data CSV</span><textarea required rows={9} value={value} onChange={event => onChange(event.target.value)} spellCheck={false} /></label>
    <label className="upload">Import CSV<input aria-label="Import CSV" type="file" accept=".csv,text/csv" onChange={async event => {
      const file = event.target.files?.[0]; if (!file) return;
      setError('');
      if (file.size > 5_000_000) { setError('CSV must be smaller than 5 MB.'); return; }
      try { onChange(await file.text()); } catch { setError('Could not read this file.'); }
      event.target.value = '';
    }} /></label>{error && <p role="alert" className="error">{error}</p>}</>;
}
