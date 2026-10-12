import { describe, expect, it } from 'vitest';
import { parseCsv, numericList, portfolioExample, pct, numeric } from './data';
describe('CSV input validation', () => {
  it('parses aligned decimal returns', () => {
    const result = parseCsv(portfolioExample, 'portfolio');
    expect(result.assets).toEqual(['AAA', 'BBB']);
    expect(result.returns[0]).toEqual([-.01, -.02]);
    expect(result.dates).toHaveLength(4);
  });
  it.each([
    'date,A\n2025-01-01,\n2025-01-02,0.1',
    'date,A\n2025-01-02,0.1\n2025-01-01,0.1',
    'date,A\n2025-02-30,0.1\n2025-03-03,0.1',
    'date,A,A\n2025-01-01,0.1,0.2\n2025-01-02,0.1,0.2',
    'date,A\n2025-01-01,Infinity\n2025-01-02,0.1',
    'date,A\n2025-01-01,1,2\n2025-01-02,1,2',
  ])('rejects malformed CSV rather than substituting zero: %s', csv => {
    expect(() => parseCsv(csv, 'portfolio')).toThrow();
  });
  it('requires date,price for backtests', () => {
    expect(() => parseCsv(portfolioExample, 'prices')).toThrow(/exactly/);
  });
  it('parses returns and distinguishes undefined ratios', () => {
    expect(numericList('0.1, -0.2\n0.3')).toEqual([.1, -.2, .3]);
    expect(() => numericList('')).toThrow();
    expect(() => numericList('0.1,invalid')).toThrow();
    expect(pct(null)).toBe('—');
    expect(pct(0)).toBe('0%');
    expect(() => numeric(new FormData(), 'missing')).toThrow();
  });
});
