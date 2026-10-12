export const pct = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 2 }).format(value);
export const number = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('en', { maximumFractionDigits: 3 }).format(value);
export const numeric = (form: FormData, name: string) => {
  const raw = String(form.get(name) ?? '').trim();
  const value = Number(raw);
  if (!raw || !Number.isFinite(value)) throw new Error(`${name.replaceAll('_', ' ')} must be a finite number.`);
  return value;
};
export const text = (form: FormData, name: string) => String(form.get(name) ?? '').trim();
export function numericList(raw: string) {
  const cells = raw.trim().split(/[\s,]+/);
  if (!raw.trim() || cells.some(cell => !cell || !Number.isFinite(Number(cell)))) throw new Error('Enter finite decimal values separated by commas or spaces.');
  return cells.map(Number);
}

export function parseCsv(raw: string, kind: 'portfolio' | 'prices') {
  const rows = raw.trim().split(/\r?\n/).map(row => row.split(',').map(cell => cell.trim()));
  const header = rows.shift();
  if (!header || header[0]?.toLowerCase() !== 'date' || header.length < 2 || rows.length < 2) throw new Error('CSV needs a date header and at least two data rows.');
  if (kind === 'prices' && (header.length !== 2 || header[1].toLowerCase() !== 'price')) throw new Error('Price CSV must have exactly the columns date,price.');
  const dates: string[] = [], values: number[][] = [];
  for (const [index, row] of rows.entries()) {
    if (row.length !== header.length || row.slice(1).some(cell => !cell || !Number.isFinite(Number(cell)))) throw new Error(`Invalid numeric cells on CSV row ${index + 2}.`);
    const date = row[0];
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || new Date(date).toISOString().slice(0, 10) !== date) throw new Error(`Invalid date on CSV row ${index + 2}.`);
    if (dates.length && date <= dates.at(-1)!) throw new Error('CSV dates must be unique and increasing.');
    dates.push(date); values.push(row.slice(1).map(Number));
  }
  if (rows.length > 10000 || header.length > 51) throw new Error('Limit CSV to 10000 observations and 50 assets.');
  const assets = header.slice(1).map(name => name.toUpperCase());
  if (assets.some(name => !name) || new Set(assets).size !== assets.length) throw new Error('Asset names must be nonempty and unique.');
  return { assets, dates, returns: values, prices: values.map(row => row[0]) };
}

export const portfolioExample = 'date,AAA,BBB\n2025-01-02,-0.01,-0.02\n2025-01-03,-0.01,0.02\n2025-01-06,0.01,-0.02\n2025-01-07,0.01,0.02';
export const backtestExample = 'date,price\n2025-01-02,100\n2025-01-03,110\n2025-01-06,120\n2025-01-07,90\n2025-01-08,80\n2025-01-09,100\n2025-01-10,110';
