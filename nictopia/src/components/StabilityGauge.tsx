import type { GridNode, NodeId } from '../types';

interface Props {
  nodes: GridNode[];
}

type StabilityLevel = {
  pips: number;          // 1-5, how many pips lit
  className: string;     // styling hook
  label: string;         // human-readable
};

const LEVELS: Record<string, StabilityLevel> = {
  healthy:    { pips: 1, className: 'sg-healthy',    label: 'healthy' },
  recovering: { pips: 2, className: 'sg-recovering', label: 'absorbing' },
  stable:     { pips: 1, className: 'sg-stable',     label: 'stable' },
  warning:    { pips: 4, className: 'sg-warning',    label: 'WARNING' },
  critical:   { pips: 5, className: 'sg-critical',   label: 'CRITICAL' },
};

function levelForStatus(status: GridNode['status']): StabilityLevel {
  switch (status) {
    case 'overload': return LEVELS.critical;
    case 'warning':  return LEVELS.warning;
    case 'active':   return LEVELS.recovering;  // active = absorbing migrated load
    case 'stable':   return LEVELS.stable;
    case 'idle':
    case 'offline':
    default:         return LEVELS.healthy;
  }
}

const BA_ROWS: { id: NodeId; ba: string }[] = [
  { id: 'dc-caiso', ba: 'CAISO' },
  { id: 'dc-ercot', ba: 'ERCOT' },
  { id: 'dc-pjm',   ba: 'PJM' },
];

function Pips({ filled, total = 5 }: { filled: number; total?: number }) {
  return (
    <span className="sg-pips" aria-hidden="true">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`sg-pip ${i < filled ? 'on' : 'off'}`} />
      ))}
    </span>
  );
}

export function StabilityGauge({ nodes }: Props) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n])) as Record<string, GridNode>;
  const rows = BA_ROWS.map(({ id, ba }) => {
    const node = byId[id];
    const level = levelForStatus(node?.status ?? 'idle');
    return { id, ba, level, lmp: node?.lmp };
  });

  return (
    <section className="stability-gauge" aria-label="Grid stability per balancing authority">
      <header>
        <span className="sg-title">Grid Stability</span>
        <span className="sg-sub">per BA</span>
      </header>
      <div className="sg-rows">
        {rows.map((r) => (
          <div key={r.id} className={`sg-row ${r.level.className}`}>
            <span className="sg-ba">{r.ba}</span>
            <Pips filled={r.level.pips} />
            <span className="sg-status">{r.level.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
