import styles from "./AgentFlowDiagram.module.css";

/** 编排拓扑：感知链 A1→A2→A3，聚合后进入统一时序预测 A4（用电量 + 示数差） */
export default function AgentFlowDiagram() {
  return (
    <div className={styles.wrap} aria-hidden>
      <svg className={styles.svg} viewBox="0 0 920 220" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="agentFlowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#4f7cff" />
            <stop offset="50%" stopColor="#818cf8" />
            <stop offset="100%" stopColor="#22d3a6" />
          </linearGradient>
          <filter id="agentGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <path
          className={styles.flowPath}
          d="M 168 52 L 252 52 M 368 52 L 452 52 M 512 80 L 512 138"
          fill="none"
          stroke="url(#agentFlowGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        <polygon points="256,52 248,48 248,56" fill="#93c5fd" className={styles.arrowHead} />
        <polygon points="456,52 448,48 448,56" fill="#a5b4fc" className={styles.arrowHead} />
        <polygon points="512,138 508,130 516,130" fill="#22d3a6" className={styles.arrowHead} />

        <g className={styles.node} filter="url(#agentGlow)">
          <rect x="56" y="24" width="112" height="56" rx="12" className={styles.nodeRect} />
          <text x="112" y="48" textAnchor="middle" className={styles.nodeId}>
            A1
          </text>
          <text x="112" y="68" textAnchor="middle" className={styles.nodeSub}>
            渲染
          </text>
        </g>
        <g className={styles.node}>
          <rect x="256" y="24" width="112" height="56" rx="12" className={styles.nodeRect} />
          <text x="312" y="48" textAnchor="middle" className={styles.nodeId}>
            A2
          </text>
          <text x="312" y="68" textAnchor="middle" className={styles.nodeSub}>
            视觉抽取
          </text>
        </g>
        <g className={styles.node}>
          <rect x="456" y="24" width="112" height="56" rx="12" className={styles.nodeRectAccent} />
          <text x="512" y="48" textAnchor="middle" className={styles.nodeId}>
            A3
          </text>
          <text x="512" y="68" textAnchor="middle" className={styles.nodeSub}>
            聚合
          </text>
        </g>
        <g className={styles.node}>
          <rect x="298" y="140" width="428" height="64" rx="14" className={styles.nodeRectMerged} />
          <text x="512" y="168" textAnchor="middle" className={styles.nodeId}>
            A4
          </text>
          <text x="512" y="190" textAnchor="middle" className={styles.nodeSubWide}>
            多任务时序 · 用电量 · 分项示数差
          </text>
        </g>
      </svg>
      <p className={styles.caption}>编排器串起感知链；数据就绪后汇入统一多任务时序预测模块</p>
    </div>
  );
}
