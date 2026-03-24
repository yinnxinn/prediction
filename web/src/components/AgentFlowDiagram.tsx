import styles from "./AgentFlowDiagram.module.css";

/** 编排拓扑：感知链 A1→A2→A3，聚合后并行预测 A4 / A5 */
export default function AgentFlowDiagram() {
  return (
    <div className={styles.wrap} aria-hidden>
      <svg className={styles.svg} viewBox="0 0 920 230" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="agentFlowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#4f7cff" />
            <stop offset="50%" stopColor="#818cf8" />
            <stop offset="100%" stopColor="#22d3a6" />
          </linearGradient>
          <linearGradient id="agentForkGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#22d3a6" />
            <stop offset="100%" stopColor="#f472b6" />
          </linearGradient>
          <filter id="agentGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* A1(56–168) A2(256–368) A3(456–568) 底边 y=80；中心 x=112,312,512 */}
        <path
          className={styles.flowPath}
          d="M 168 52 L 252 52 M 368 52 L 452 52"
          fill="none"
          stroke="url(#agentFlowGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* A3 中垂线分叉至 A4(328–492, y=156) 与 A5(656–820) */}
        <path
          className={styles.flowPathFork}
          d="M 512 80 L 512 108 L 410 108 L 410 156 M 512 108 L 738 108 L 738 156"
          fill="none"
          stroke="url(#agentForkGrad)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        <polygon points="256,52 248,48 248,56" fill="#93c5fd" className={styles.arrowHead} />
        <polygon points="456,52 448,48 448,56" fill="#a5b4fc" className={styles.arrowHead} />
        <polygon points="410,158 406,150 414,150" fill="#2dd4bf" className={styles.arrowHead} />
        <polygon points="738,158 734,150 742,150" fill="#f472b6" className={styles.arrowHead} />

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
          <rect x="328" y="156" width="164" height="56" rx="12" className={styles.nodeRectParallel} />
          <text x="410" y="180" textAnchor="middle" className={styles.nodeId}>
            A4
          </text>
          <text x="410" y="200" textAnchor="middle" className={styles.nodeSub}>
            用电量预测
          </text>
        </g>
        <g className={styles.node}>
          <rect x="656" y="156" width="164" height="56" rx="12" className={styles.nodeRectParallelAlt} />
          <text x="738" y="180" textAnchor="middle" className={styles.nodeId}>
            A5
          </text>
          <text x="738" y="200" textAnchor="middle" className={styles.nodeSub}>
            示数差预测
          </text>
        </g>

        <text x="512" y="98" textAnchor="middle" className={styles.forkLabel}>
          并行
        </text>
      </svg>
      <p className={styles.caption}>编排器串起感知链；数据就绪后两路预测并行执行</p>
    </div>
  );
}
