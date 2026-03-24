import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import AgentFlowDiagram from "../components/AgentFlowDiagram";
import {
  IconLayers,
  IconPrice,
  IconRender,
  IconVision,
  IconWave,
} from "../components/AgentRoleIcons";
import styles from "./Landing.module.css";

const agents = [
  {
    id: "A1",
    name: "渲染 Agent",
    role: "PDF → 图像",
    detail: "将电费核查联 PDF 按页渲染为高分辨率栅格图，供视觉模型消费。",
    accent: "var(--agent-a1)",
    Icon: IconRender,
  },
  {
    id: "A2",
    name: "视觉抽取 Agent",
    role: "图像 → 结构化示数差",
    detail: "调用多模态大模型，从表格中按「尖峰 / 峰 / 平 / 谷 / 深谷」行读取有功示数差，并校验账单周期与合计金额。",
    accent: "var(--agent-a2)",
    Icon: IconVision,
  },
  {
    id: "A3",
    name: "聚合 Agent",
    role: "多页 → 月度序列",
    detail: "按 billing_month 合并多页、多计量点记录，输出月度 CSV，并派生用电量等结构化数据集。",
    accent: "var(--agent-a3)",
    Icon: IconLayers,
  },
  {
    id: "A4",
    name: "用电量预测 Agent",
    role: "历史用电量 → 未来用电量",
    detail: "时序特征 + 回归模型，预测未来若干月用电量（kWh）。",
    accent: "var(--agent-a4)",
    Icon: IconWave,
  },
  {
    id: "A5",
    name: "示数差预测 Agent",
    role: "历史示数差 → 分项预测",
    detail: "对五个时段的示数差分别建模，输出可解释的滞后与季节特征权重。",
    accent: "var(--agent-a5)",
    Icon: IconPrice,
  },
] as const;

const flow = [
  { step: 1, label: "文档接入", text: "上传或指定本地 PDF（江苏电费核查联）" },
  { step: 2, label: "多 Agent 编排", text: "A1→A2→A3 串行；A4、A5 在数据就绪后并行训练/推理" },
  { step: 3, label: "结果服务", text: "REST API + 功能页展示用电量与示数差预测曲线" },
];

export default function Landing() {
  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <div className={styles.badge}>Multi-Agent System</div>
        <h1 className={styles.title}>
          电费核查联
          <span className={styles.hl}> 智能分析流水线</span>
        </h1>
        <p className={styles.lead}>
          将「解析 PDF → 提取有功示数差 → 聚合建模 → 用电量与分项预测」抽象为
          <strong> 多智能体协作（MAS）</strong>
          ：每个 Agent 专注单一职责，通过编排层串联成可观测、可复用的工作流。
        </p>
        <div className={styles.cta}>
          <Link to="/studio">
            <button type="button" className="btn-primary">
              进入功能页 · 有功示数差
            </button>
          </Link>
          <a href="http://127.0.0.1:8001/docs" target="_blank" rel="noreferrer">
            <button type="button" className="btn-ghost">
              OpenAPI 文档
            </button>
          </a>
        </div>
      </header>

      <section className={styles.section}>
        <h2 className={styles.h2}>MAS 计算流程</h2>
        <p className={styles.p}>
          系统<strong>不是</strong>单一黑盒模型，而是由<strong>编排器</strong>（Pipeline / FastAPI）调度多个
          <strong>领域 Agent</strong>：前段侧重感知与结构化，后段侧重时序预测与解释。
        </p>
        <div className={styles.flow}>
          {flow.map((f) => (
            <div key={f.step} className={styles.flowItem}>
              <span className={styles.flowNum}>{f.step}</span>
              <div>
                <div className={styles.flowLabel}>{f.label}</div>
                <div className={styles.flowText}>{f.text}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.agentHeader}>
          <h2 className={styles.h2}>Agent 分工</h2>
          <p className={styles.agentTagline}>感知链 · 聚合枢纽 · 双路预测</p>
        </div>
        <p className={styles.p}>
          下图是编排拓扑：<strong>串行抽取</strong>与<strong>并行预测</strong>一目了然；下方卡片带职责图标与数据流标签。
        </p>

        <AgentFlowDiagram />

        <div className={styles.agentGrid}>
          {agents.map((a, i) => (
            <article
              key={a.id}
              className={styles.roleCard}
              style={
                {
                  "--agent-accent": a.accent,
                  animationDelay: `${i * 55}ms`,
                } as CSSProperties
              }
            >
              <div className={styles.roleCardInner}>
                <div className={styles.roleCardTop}>
                  <div className={styles.iconOrb} aria-hidden>
                    <a.Icon className={styles.iconSvg} />
                  </div>
                  <div className={styles.roleTitles}>
                    <span className={styles.roleId}>{a.id}</span>
                    <h3 className={styles.roleName}>{a.name}</h3>
                  </div>
                </div>
                <div className={styles.rolePipe}>{a.role}</div>
                <p className={styles.roleDetail}>{a.detail}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h2 className={styles.h2}>与后端的关系</h2>
        <p className={styles.p}>
          编排逻辑在 <code>app/pipeline.py</code>、<code>scripts/parse_active_readings.py</code> 中实现；
          预测在 <code>app/modeling.py</code>（<code>ReadingDiffPredictor</code> 等）。前端通过 REST 调用同一 FastAPI 服务，功能页实时拉取{" "}
          <code>/ui/reading-diff-overview</code> 等接口。
        </p>
      </section>

      <footer className={styles.footer}>
        <span>Electricity Bill Intelligence · MAS View</span>
        <Link to="/studio">进入 Studio →</Link>
      </footer>
    </div>
  );
}
