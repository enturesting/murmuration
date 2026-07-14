interface ActiveFlows {
  stress: boolean;
  compute: boolean;
  vpp: boolean;
  protect: boolean;
}

interface Props {
  activeFlows: ActiveFlows;
}

interface LegendItem {
  key: keyof ActiveFlows;
  className: string;
  label: string;
  detail: string;
}

const ITEMS: LegendItem[] = [
  {
    key: 'stress',
    className: 'lg2-stress',
    label: 'Stress event',
    detail: 'pulsing red ring on the data center whose grid is overloaded',
  },
  {
    key: 'compute',
    className: 'lg2-compute',
    label: 'Compute migration',
    detail: 'cross-region: jobs rerouted over fiber. Electricity stays local within each grid.',
  },
  {
    key: 'vpp',
    className: 'lg2-vpp',
    label: 'VPP local injection',
    detail: 'Virtual Power Plant — home batteries + EVs discharging into the SAME-region grid',
  },
  {
    key: 'protect',
    className: 'lg2-protect',
    label: 'Protected critical load',
    detail: 'local power flow from the data center grid to hospitals + water + emergency services',
  },
];

export function LegendStrip({ activeFlows }: Props) {
  return (
    <nav className="legend-strip" aria-label="Map flow-type legend">
      {ITEMS.map((it) => {
        const active = activeFlows[it.key];
        return (
          <div
            key={it.key}
            className={`lg2-item ${it.className} ${active ? 'on' : 'off'}`}
            title={it.detail}
          >
            <span className="lg2-dot" aria-hidden="true" />
            <span className="lg2-label">{it.label}</span>
          </div>
        );
      })}
    </nav>
  );
}
