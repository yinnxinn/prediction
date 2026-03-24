import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchJson } from "../api";
import KwhTrendChart from "../components/KwhTrendChart";
import ReadingDiffChart from "../components/ReadingDiffChart";
import styles from "./Dashboard.module.css";
import { winsorizeKwhTable, winsorizeReadingDiffSplit } from "../utils/seriesTransform";

type ReadingDiffOverview = {
  history: { timestamp: string; components: Record<string, number> }[];
  predictions: {
    timestamp: string;
    components: Record<string, number>;
    reasons: Record<string, string>;
  }[];
  component_names: Record<string, string>;
  status: string;
  error: string | null;
};

/** 与 /ui/price-overview 一致；页面仅展示 total_kwh */
type ConsumptionOverview = {
  realtime: { timestamp: string; total_kwh: number | null } | null;
  next_prediction: {
    timestamp: string;
    total_kwh: number | null;
  } | null;
  history: { timestamp: string; total_kwh: number | null }[];
  forecast: {
    timestamp: string;
    total_kwh: number | null;
  }[];
  prediction_status: string;
  prediction_error: string | null;
};

const COMP_KEYS = [
  "peak2_reading_diff",
  "peak_reading_diff",
  "flat_reading_diff",
  "valley_reading_diff",
  "deep_valley_reading_diff",
] as const;

export default function Dashboard() {
  const [rd, setRd] = useState<ReadingDiffOverview | null>(null);
  const [consumption, setConsumption] = useState<ConsumptionOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [trainBusy, setTrainBusy] = useState(false);
  /** 曲线是否缩放到 0–100 同量纲；表格始终为 IQR 清洗后的物理量 */
  const [chartNormalize, setChartNormalize] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setMsg("");
    try {
      const r = await fetchJson<ReadingDiffOverview>("/ui/reading-diff-overview?months=3");
      setRd(r);
    } catch (e) {
      setRd(null);
      setMsg(e instanceof Error ? e.message : "示数差接口不可用");
    }
    try {
      const p = await fetchJson<ConsumptionOverview>("/ui/price-overview?months=3");
      setConsumption(p);
    } catch {
      setConsumption(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function trainReadingDiff() {
    setTrainBusy(true);
    setMsg("");
    try {
      await fetchJson("/reading-diff/train", { method: "POST" });
      await load();
      setMsg("示数差模型已训练并刷新");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "训练失败");
    }
    setTrainBusy(false);
  }

  const names = rd?.component_names ?? {};

  const rdClean = useMemo(() => {
    if (!rd?.history?.length) return null;
    return winsorizeReadingDiffSplit(rd.history, rd.predictions ?? [], COMP_KEYS);
  }, [rd]);

  const kwhClean = useMemo(() => {
    if (!consumption?.history?.length) return null;
    return winsorizeKwhTable(consumption.history, consumption.forecast ?? []);
  }, [consumption]);

  const lastHist = rdClean?.history?.length ? rdClean.history[rdClean.history.length - 1] : null;
  const firstPred = rdClean?.predictions?.length ? rdClean.predictions[0] : null;

  return (
    <div className={styles.wrap}>
      <header className={styles.head}>
        <div>
          <Link to="/" className={styles.back}>
            ← MAS 首页
          </Link>
          <h1 className={styles.title}>有功示数差 · 功能页</h1>
          <p className={styles.sub}>
            数据以表格展示，示数差与<strong>用电量预测</strong>配有 ECharts 曲线；预测行在表中单独标注「预测」。
          </p>
        </div>
        <div className={styles.actions}>
          <label className={styles.toggleNorm}>
            <input
              type="checkbox"
              checked={chartNormalize}
              onChange={(e) => setChartNormalize(e.target.checked)}
            />
            曲线归一化 0–100
          </label>
          <button type="button" className="btn-ghost" onClick={load} disabled={loading}>
            刷新
          </button>
          <button type="button" className="btn-primary" onClick={trainReadingDiff} disabled={trainBusy}>
            {trainBusy ? "训练中…" : "训练示数差模型"}
          </button>
        </div>
      </header>

      <section className={styles.pipeline}>
        <h2 className={styles.h2}>有功功率（示数差）在本页的展示过程</h2>
        <ol className={styles.steps}>
          <li>
            <strong>数据层</strong>：CSV（如 <code>data/processed/*有功示数*.csv</code>）由「聚合 Agent」产出。
          </li>
          <li>
            <strong>接口层</strong>：<code>GET /ui/reading-diff-overview</code> 返回历史序列与预测。
          </li>
          <li>
            <strong>呈现层</strong>：下方<strong>表格</strong>汇总历史/预测行（按列 IQR 异常值处理）；<strong>曲线图</strong>可选归一化到 0–100 同量纲。
          </li>
        </ol>
      </section>

      {msg && <div className={styles.banner}>{msg}</div>}

      {rd?.error && (rd.status === "unavailable" || (rd.history?.length ?? 0) === 0) && (
        <div className={styles.bannerWarn}>
          <strong>示数差数据：</strong>
          {rd.error}
        </div>
      )}

      <section className={styles.section}>
        <h2 className={styles.h2}>分项示数差（最新 vs 下期预测）</h2>
        {loading && <p className={styles.muted}>加载中…</p>}
        {!loading && !rd && (
          <p className={styles.warn}>
            无法连接后端。请确认 uvicorn 已启动（默认端口 8001），且 web/vite.config 中代理或 web/.env 的 VITE_PROXY_TARGET 与之一致。
          </p>
        )}
        {rd && (
          <div className={styles.grid5}>
            {COMP_KEYS.map((k) => (
              <div key={k} className={styles.card}>
                <div className={styles.cardLabel}>{names[k] ?? k}</div>
                <div className={styles.cardVal}>最新 {fmt(lastHist?.components?.[k])}</div>
                <div className={styles.cardPred}>预测 {fmt(firstPred?.components?.[k])}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {rd && rdClean && (rd.history?.length ?? 0) > 0 && (
        <>
          <ReadingDiffChart
            history={rdClean.history}
            predictions={rdClean.predictions}
            names={names}
            normalize={chartNormalize}
          />

          <section className={styles.section}>
            <h2 className={styles.h2}>示数差数据表（历史 + 预测，IQR 清洗后）</h2>
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>月份</th>
                    <th>类型</th>
                    {COMP_KEYS.map((k) => (
                      <th key={k}>{names[k] ?? k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rdClean.history.map((row) => (
                    <tr key={`h-${row.timestamp}`}>
                      <td>{row.timestamp.slice(0, 7)}</td>
                      <td>
                        <span className={styles.tagHist}>历史</span>
                      </td>
                      {COMP_KEYS.map((k) => (
                        <td key={k}>{fmt(row.components?.[k])}</td>
                      ))}
                    </tr>
                  ))}
                  {rdClean.predictions.map((row) => (
                    <tr key={`p-${row.timestamp}`} className={styles.rowPred}>
                      <td>{row.timestamp.slice(0, 7)}</td>
                      <td>
                        <span className={styles.tagPred}>预测</span>
                      </td>
                      {COMP_KEYS.map((k) => (
                        <td key={k}>{fmt(row.components?.[k])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {rd && rd.predictions.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.h2}>示数差预测理由</h2>
          {rd.predictions.map((p) => (
            <div key={p.timestamp} className={styles.predBlock}>
              <div className={styles.predMonth}>{p.timestamp.slice(0, 7)}</div>
              <div className={styles.reasonGrid}>
                {Object.entries(p.reasons).map(([col, text]) => (
                  <div key={col} className={styles.reasonItem}>
                    <div className={styles.reasonTitle}>{names[col] ?? col}</div>
                    <div className={styles.reasonText}>{text}</div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {consumption && consumption.prediction_status === "unavailable" && consumption.prediction_error && (
        <section className={styles.section}>
          <p className={styles.muted}>{consumption.prediction_error}</p>
        </section>
      )}

      {consumption && kwhClean && consumption.history && consumption.history.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.h2}>用电量预测</h2>
          <KwhTrendChart
            history={kwhClean.history}
            forecast={kwhClean.forecast}
            normalize={chartNormalize}
            preWinsorized
          />

          <h3 className={styles.h3}>用电量数据表（历史 + 预测，IQR 清洗后）</h3>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>月份</th>
                  <th>类型</th>
                  <th>用电量（kWh）</th>
                </tr>
              </thead>
              <tbody>
                {kwhClean.history.map((row) => (
                  <tr key={`ph-${row.timestamp}`}>
                    <td>{row.timestamp.slice(0, 7)}</td>
                    <td>
                      <span className={styles.tagHist}>历史</span>
                    </td>
                    <td>{row.total_kwh != null ? Number(row.total_kwh).toLocaleString("zh-CN") : "—"}</td>
                  </tr>
                ))}
                {kwhClean.forecast.map((row) => (
                  <tr key={`pf-${row.timestamp}`} className={styles.rowPred}>
                    <td>{row.timestamp.slice(0, 7)}</td>
                    <td>
                      <span className={styles.tagPred}>预测</span>
                    </td>
                    <td>{row.total_kwh != null ? Number(row.total_kwh).toLocaleString("zh-CN") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={styles.gridPrice} style={{ marginTop: 16 }}>
            <div className={styles.card}>
              <div className={styles.cardLabel}>最新用电量（清洗后）</div>
              <div className={styles.cardVal}>
                {kwhClean.history.length
                  ? kwhClean.history[kwhClean.history.length - 1]?.total_kwh != null
                    ? Number(
                        kwhClean.history[kwhClean.history.length - 1].total_kwh,
                      ).toLocaleString("zh-CN")
                    : "—"
                  : consumption.realtime?.total_kwh != null
                    ? Number(consumption.realtime.total_kwh).toLocaleString("zh-CN")
                    : "-"}{" "}
                kWh
              </div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardLabel}>下期预测用电量（清洗后）</div>
              <div className={styles.cardVal}>
                {kwhClean.forecast[0]?.total_kwh != null
                  ? Number(kwhClean.forecast[0].total_kwh).toLocaleString("zh-CN")
                  : consumption.next_prediction?.total_kwh != null
                    ? Number(consumption.next_prediction.total_kwh).toLocaleString("zh-CN")
                    : "-"}{" "}
                kWh
              </div>
            </div>
            <div className={styles.card}>
              <div className={styles.cardLabel}>状态</div>
              <div className={styles.cardVal} style={{ fontSize: 16 }}>
                {consumption.prediction_status}
              </div>
              {consumption.prediction_error && <div className={styles.tiny}>{consumption.prediction_error}</div>}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

function fmt(n: number | undefined) {
  if (n === undefined || n === null || Number.isNaN(n)) return "—";
  return Number(n).toFixed(4);
}
