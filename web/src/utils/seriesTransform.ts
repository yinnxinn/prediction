/**
 * 序列清洗与归一化：IQR 截尾（Winsorize）减轻异常值影响；
 * Min-Max 将各指标映射到同一相对量纲 [0, 100] 便于同图对比。
 */

function quantileSorted(sorted: number[], p: number): number {
  if (sorted.length === 0) return NaN;
  const pos = (sorted.length - 1) * p;
  const base = Math.floor(pos);
  const rest = pos - base;
  const a = sorted[base];
  const b = sorted[base + 1];
  if (b === undefined) return a;
  return a + rest * (b - a);
}

/** 对有限数值序列做 IQR Winsorize；null/NaN 保持为 null */
export function winsorizeSeries(values: (number | null | undefined)[], factor = 1.5): (number | null)[] {
  const nums: number[] = [];
  for (const v of values) {
    if (v != null && Number.isFinite(v)) nums.push(v);
  }
  if (nums.length < 4) {
    return values.map((v) => (v != null && Number.isFinite(v) ? v : null));
  }
  const sorted = [...nums].sort((a, b) => a - b);
  const q1 = quantileSorted(sorted, 0.25);
  const q3 = quantileSorted(sorted, 0.75);
  const iqr = q3 - q1;
  const lo = q1 - factor * iqr;
  const hi = q3 + factor * iqr;

  return values.map((v) => {
    if (v == null || !Number.isFinite(v)) return null;
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
  });
}

/** 单序列 Min-Max 到 [0, 100]；全为常数时映射为 50 */
export function minMaxTo100(values: (number | null)[]): (number | null)[] {
  const finite = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (finite.length === 0) return values.map(() => null);
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = max - min;
  if (span === 0) {
    return values.map((v) => (v != null && Number.isFinite(v) ? 50 : null));
  }
  return values.map((v) => {
    if (v == null || !Number.isFinite(v)) return null;
    return ((v - min) / span) * 100;
  });
}

export type TransformedPair = {
  raw: (number | null)[];
  norm: (number | null)[];
};

/** 数据已在上游做过 IQR 时，仅做 0–100 归一化 */
export function normalize100Only(values: (number | null | undefined)[]): TransformedPair {
  const raw = values.map((v) => (v != null && Number.isFinite(v) ? v : null));
  const norm = minMaxTo100(raw);
  return { raw, norm };
}

/** 与示数差图表同一顺序：历史 + 预测按列 IQR，表格与卡片与曲线口径一致 */
export function winsorizeReadingDiffSplit<
  H extends { components: Record<string, number> },
  P extends { components: Record<string, number> },
>(history: H[], predictions: P[], keys: readonly string[]): { history: H[]; predictions: P[] } {
  const merged = [...history, ...predictions];
  if (merged.length === 0) return { history: [], predictions: [] };
  const byKey = keys.map((k) => winsorizeSeries(merged.map((r) => r.components?.[k] ?? null)));
  const apply = (row: H | P, i: number) => {
    const components: Record<string, number> = { ...row.components };
    keys.forEach((k, ki) => {
      const v = byKey[ki][i];
      if (v != null && Number.isFinite(v)) components[k] = v;
    });
    return { ...row, components } as H & P;
  };
  return {
    history: history.map((row, i) => apply(row, i) as H),
    predictions: predictions.map((row, j) => apply(row, history.length + j) as P),
  };
}

type KwhRow = { timestamp: string; total_kwh: number | null };

/** 用电量一列 IQR，与用电量曲线一致 */
export function winsorizeKwhTable(
  history: KwhRow[],
  forecast: KwhRow[],
): { history: KwhRow[]; forecast: KwhRow[] } {
  const kwhCol = [...history.map((h) => h.total_kwh), ...forecast.map((f) => f.total_kwh)];
  const kwhW = winsorizeSeries(kwhCol);
  const histN = history.length;
  const histOut = history.map((row, i) => ({
    ...row,
    total_kwh: kwhW[i] ?? row.total_kwh,
  }));
  const foreOut = forecast.map((row, j) => ({
    ...row,
    total_kwh: kwhW[histN + j] ?? row.total_kwh,
  }));
  return { history: histOut, forecast: foreOut };
}
