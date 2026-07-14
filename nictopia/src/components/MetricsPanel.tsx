import type { Metrics } from '../types';

interface MetricsPanelProps {
  metrics: Metrics;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

function metricValue(value: number, suffix: string) {
  return value > 0 ? `${value.toLocaleString()} ${suffix}` : '-';
}

export function MetricsPanel({ metrics, collapsed, onToggleCollapse }: MetricsPanelProps) {
  return (
    <section
      className="panel metrics-panel"
      aria-label="Grid metrics"
      data-collapsed={collapsed ? 'true' : undefined}
    >
      <h2
        className={onToggleCollapse ? 'panel-toggle' : ''}
        onClick={onToggleCollapse}
        role={onToggleCollapse ? 'button' : undefined}
      >
        {onToggleCollapse && <span className="chevron">{collapsed ? '▸' : '▾'}</span>}
        Grid Metrics
      </h2>
      <div className="metric">
        <span>Overload Avoided</span>
        <strong>{metricValue(metrics.overloadAvoided, 'MW')}</strong>
      </div>
      <div className="metric">
        <span>Reserve Dispatched</span>
        <strong>{metricValue(metrics.reserveDispatched, 'MW')}</strong>
      </div>
      <div className="metric">
        <span>Critical Load Protected</span>
        <strong>{metrics.criticalLoadProtected > 0 ? `${(metrics.criticalLoadProtected / 1000000).toFixed(1)}M people` : '-'}</strong>
      </div>
      <div className="metric">
        <span>Settlement (real math)</span>
        <strong>{metrics.settlementUsd > 0 ? `$${metrics.settlementUsd.toLocaleString()}` : '-'}</strong>
      </div>
      <div className="metric">
        <span>CO₂ Avoided (vs peakers)</span>
        <strong>{metrics.tonsCo2Avoided > 0 ? `${metrics.tonsCo2Avoided.toLocaleString()} t` : '-'}</strong>
      </div>
    </section>
  );
}
