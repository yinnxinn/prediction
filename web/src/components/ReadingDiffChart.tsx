import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import styles from "./ReadingDiffChart.module.css";
import { normalize100Only } from "../utils/seriesTransform";

const COMP_KEYS = [
  "peak2_reading_diff",
  "peak_reading_diff",
  "flat_reading_diff",
  "valley_reading_diff",
  "deep_valley_reading_diff",
] as const;

const COLORS = ["#4f7cff", "#22d3a6", "#fbbf24", "#a78bfa", "#fb7185"];

type Props = {
  history: { timestamp: string; components: Record<string, number> }[];
  predictions: { timestamp: string; components: Record<string, number> }[];
  names: Record<string, string>;
  /** 按各分项独立 Min-Max 到 0–100；IQR 请在父组件对 history/predictions 先做完 */
  normalize?: boolean;
};

export default function ReadingDiffChart({
  history,
  predictions,
  names,
  normalize = true,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || history.length === 0) return;

    const chart = echarts.init(el);
    chartRef.current = chart;

    const histMonths = history.map((h) => h.timestamp.slice(0, 7));
    const predMonths = predictions.map((p) => p.timestamp.slice(0, 7));
    const xAxis = [...histMonths, ...predMonths];

    const rawMatrices: (number | null)[][] = [];
    const plotMatrices: (number | null)[][] = [];

    const series = COMP_KEYS.map((k, i) => {
      const merged = [
        ...history.map((h) => (h.components?.[k] != null ? Number(h.components[k]) : null)),
        ...predictions.map((p) => (p.components?.[k] != null ? Number(p.components[k]) : null)),
      ];
      const { raw, norm } = normalize100Only(merged);
      rawMatrices.push(raw);
      const plot = normalize ? norm : raw;
      plotMatrices.push(plot);

      return {
        name: names[k] ?? k,
        type: "line" as const,
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        lineStyle: { width: 2 },
        itemStyle: { color: COLORS[i % COLORS.length] },
        data: plot,
      };
    });

    const yName = normalize ? "相对指标 (0–100)" : "示数差";

    chart.setOption({
      backgroundColor: "transparent",
      textStyle: { color: "#aeb8de" },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        formatter: (params: unknown) => {
          if (!Array.isArray(params) || params.length === 0) return "";
          const first = params[0] as { dataIndex?: number; axisValue?: string };
          const idx = first.dataIndex ?? 0;
          const month = first.axisValue ?? xAxis[idx] ?? "";
          const lines = params.map((p) => {
            const pp = p as { seriesIndex: number; seriesName?: string; value?: number | null };
            const si = pp.seriesIndex;
            const rawVal = rawMatrices[si]?.[idx];
            const plotVal = plotMatrices[si]?.[idx];
            const label = pp.seriesName ?? "";
            if (rawVal == null && plotVal == null) return `${label}: —`;
            const rawStr = rawVal != null && Number.isFinite(rawVal) ? Number(rawVal).toFixed(4) : "—";
            if (normalize) {
              const nStr = plotVal != null && Number.isFinite(plotVal) ? Number(plotVal).toFixed(1) : "—";
              return `${label}: 归一 ${nStr} <span style="opacity:.75">(原始 ${rawStr})</span>`;
            }
            return `${label}: ${rawStr}`;
          });
          return `<div style="font-weight:600;margin-bottom:4px">${month}</div>${lines.join("<br/>")}`;
        },
      },
      legend: {
        data: COMP_KEYS.map((k) => names[k] ?? k),
        top: 0,
        textStyle: { color: "#c9d4ff" },
      },
      grid: { left: 56, right: 24, top: 44, bottom: 48 },
      xAxis: {
        type: "category",
        data: xAxis,
        axisLabel: { color: "#8b96b8", rotate: xAxis.length > 8 ? 35 : 0 },
        axisLine: { lineStyle: { color: "#2a345d" } },
      },
      yAxis: {
        type: "value",
        name: yName,
        min: normalize ? 0 : undefined,
        max: normalize ? 100 : undefined,
        nameTextStyle: { color: "#8b96b8" },
        axisLabel: { color: "#8b96b8" },
        splitLine: { lineStyle: { color: "#1e2a4a" } },
      },
      series,
    });

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, [history, predictions, names, normalize]);

  if (history.length === 0) return null;

  return (
    <div className={styles.wrap}>
      <h3 className={styles.title}>示数差分时曲线</h3>
      <p className={styles.hint}>
        横轴为月份，五条线对应尖峰/峰/平/谷/深谷；表格与曲线均使用按列 IQR 清洗后的值
        {normalize ? "；本图再按各分项独立缩放到 0–100 便于同屏对比" : "；本图为清洗后原始量级"}。
      </p>
      <div ref={ref} className={styles.chart} />
    </div>
  );
}
