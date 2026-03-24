import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import styles from "./ReadingDiffChart.module.css";
import { normalize100Only, winsorizeSeries } from "../utils/seriesTransform";

type Point = { timestamp: string; total_kwh: number | null };
type ForecastPoint = { timestamp: string; total_kwh: number | null };

type Props = {
  history: Point[];
  forecast: ForecastPoint[];
  /** true：IQR 后映射到 0–100 */
  normalize?: boolean;
  /** true：history/forecast 已在父组件按列做过 IQR */
  preWinsorized?: boolean;
};

export default function KwhTrendChart({
  history,
  forecast,
  normalize = true,
  preWinsorized = false,
}: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || history.length === 0) return;

    const chart = echarts.init(el);
    const x = [
      ...history.map((h) => h.timestamp.slice(0, 7)),
      ...forecast.map((f) => f.timestamp.slice(0, 7)),
    ];
    const merged = [...history.map((h) => h.total_kwh), ...forecast.map((f) => f.total_kwh)];
    const kwhCleaned = preWinsorized
      ? merged.map((v) => (v != null && Number.isFinite(v) ? v : null))
      : winsorizeSeries(merged);
    const { raw: kwhRaw, norm } = normalize100Only(kwhCleaned);
    const plot = normalize ? norm : kwhRaw;

    chart.setOption({
      backgroundColor: "transparent",
      textStyle: { color: "#aeb8de" },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          if (!Array.isArray(params) || params.length === 0) return "";
          const p0 = params[0] as { dataIndex?: number; axisValue?: string; value?: number | null };
          const idx = p0.dataIndex ?? 0;
          const month = p0.axisValue ?? x[idx] ?? "";
          const kwh = kwhRaw[idx];
          const kwhStr =
            kwh != null && Number.isFinite(kwh) ? Number(kwh).toLocaleString("zh-CN") : "—";
          if (normalize) {
            const n = p0.value;
            const nStr = n != null && Number.isFinite(Number(n)) ? Number(n).toFixed(1) : "—";
            return `<div style="font-weight:600;margin-bottom:4px">${month}</div>归一 ${nStr} <span style="opacity:.75">(kWh ${kwhStr})</span>`;
          }
          return `<div style="font-weight:600;margin-bottom:4px">${month}</div>用电量: ${kwhStr} kWh`;
        },
      },
      legend: {
        data: normalize ? ["用电量(归一)"] : ["用电量(kWh)"],
        textStyle: { color: "#c9d4ff" },
        top: 0,
      },
      grid: { left: 56, right: 24, top: 40, bottom: 44 },
      xAxis: {
        type: "category",
        data: x,
        axisLabel: { color: "#8b96b8", rotate: x.length > 10 ? 28 : 0 },
      },
      yAxis: normalize
        ? {
            type: "value",
            name: "相对指标 (0–100)",
            min: 0,
            max: 100,
            axisLabel: { color: "#8b96b8" },
            splitLine: { lineStyle: { color: "#1e2a4a" } },
            nameTextStyle: { color: "#8b96b8" },
          }
        : {
            type: "value",
            name: "kWh",
            axisLabel: { color: "#8b96b8" },
            splitLine: { lineStyle: { color: "#1e2a4a" } },
            nameTextStyle: { color: "#8b96b8" },
          },
      series: [
        {
          name: normalize ? "用电量(归一)" : "用电量(kWh)",
          type: "line",
          smooth: true,
          data: plot,
          lineStyle: { color: "#22d3a6", width: 2 },
          areaStyle: { color: "rgba(34, 211, 166, 0.08)" },
        },
      ],
    });

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.dispose();
    };
  }, [history, forecast, normalize, preWinsorized]);

  if (history.length === 0) return null;

  return (
    <div className={styles.wrap}>
      <h3 className={styles.title}>用电量曲线</h3>
      <p className={styles.hint}>
        历史与预测在同一时间轴；已对用电量做 IQR 异常值截尾
        {normalize ? "，并归一化到 0–100（tooltip 仍显示 kWh）" : ""}。
      </p>
      <div ref={ref} className={styles.chart} />
    </div>
  );
}
