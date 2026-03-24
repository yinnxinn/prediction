type IconProps = { className?: string };

const common = { width: 28, height: 28, viewBox: "0 0 24 24" as const, fill: "none", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function IconRender({ className }: IconProps) {
  return (
    <svg {...common} className={className} aria-hidden>
      <path d="M7 3h8a2 2 0 012 2v14l-5-3-5 3V5a2 2 0 012-2z" stroke="currentColor" />
      <path d="M9 8h6M9 12h4" stroke="currentColor" opacity={0.85} />
    </svg>
  );
}

export function IconVision({ className }: IconProps) {
  return (
    <svg {...common} className={className} aria-hidden>
      <path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12z" stroke="currentColor" />
      <circle cx="12" cy="12" r="2.5" stroke="currentColor" />
    </svg>
  );
}

export function IconLayers({ className }: IconProps) {
  return (
    <svg {...common} className={className} aria-hidden>
      <path d="M12 3l9 5-9 5-9-5 9-5z" stroke="currentColor" />
      <path d="M3 12l9 5 9-5M3 17l9 5 9-5" stroke="currentColor" opacity={0.85} />
    </svg>
  );
}

export function IconPrice({ className }: IconProps) {
  return (
    <svg {...common} className={className} aria-hidden>
      <path d="M4 18V6M4 18h4M4 14h3" stroke="currentColor" />
      <path d="M12 16l3-8 3 8M13.2 14h3.6" stroke="currentColor" />
    </svg>
  );
}

export function IconWave({ className }: IconProps) {
  return (
    <svg {...common} className={className} aria-hidden>
      <path d="M3 12c2.5-4 5.5-4 8 0s5.5 4 8 0M3 17c2.5-4 5.5-4 8 0s5.5 4 8 0" stroke="currentColor" />
      <path d="M3 7c2.5-4 5.5-4 8 0s5.5 4 8 0" stroke="currentColor" opacity={0.65} />
    </svg>
  );
}
