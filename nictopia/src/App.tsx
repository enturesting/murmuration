import { useEffect, useRef, useState } from 'react';
import { BusTicker } from './components/BusTicker';
import { EventLog } from './components/EventLog';
import { FlashBanner } from './components/FlashBanner';
import { FlatMapView } from './components/FlatMapView';
import { GlobeView, type LayerState } from './components/GlobeView';
import { LegendStrip } from './components/LegendStrip';
import { MetricsPanel } from './components/MetricsPanel';
import { StabilityGauge } from './components/StabilityGauge';
import {
  SCENARIOS,
  initialEdges,
  initialMetrics,
  initialNodes,
  nowTime,
} from './lib/simulation';
import type {
  BusMessage,
  BusMessageType,
  GridEdge,
  GridNode,
  LogEntry,
  Metrics,
  Phase,
  Scenario,
} from './types';

function makeLog(message: string, level: LogEntry['level']): LogEntry {
  return { id: Date.now() + Math.random(), ts: nowTime(), message, level };
}

function makeBus(
  type: BusMessageType,
  direction: BusMessage['direction'],
  summary: string,
  payload: Record<string, unknown>,
): BusMessage {
  return {
    id: Date.now() + Math.random(),
    ts: nowTime(),
    type,
    direction,
    summary,
    payload,
  };
}

const AMBIENT_BAS = ['CAISO', 'ERCOT', 'PJM', 'MISO', 'NYISO'] as const;

function ambientGridState(): BusMessage {
  const ba = AMBIENT_BAS[Math.floor(Math.random() * AMBIENT_BAS.length)];
  const lmp = Math.round(28 + Math.random() * 24);
  const stress = +(0.05 + Math.random() * 0.18).toFixed(2);
  const headroom = Math.round(12 + Math.random() * 18);
  return makeBus(
    'GridStateUpdate',
    'grid->compute',
    `${ba}/HUB · LMP $${lmp} · stress ${stress} · headroom ${headroom}%`,
    {
      ba,
      lmp_dollars_mwh: lmp,
      stress_score: stress,
      headroom_pct: headroom,
      frequency_hz: +(60 + (Math.random() - 0.5) * 0.04).toFixed(3),
    },
  );
}

function ambientEnvelope(): BusMessage {
  const facilities = ['dc-caiso', 'dc-ercot', 'dc-pjm'] as const;
  const f = facilities[Math.floor(Math.random() * facilities.length)];
  const mw = Math.round(110 + Math.random() * 60);
  return makeBus(
    'FlexibilityEnvelope',
    'compute->grid',
    `envelope refresh ← ${f} · ${mw} MW down · 240 min · training class`,
    {
      facility_id: f,
      bands: [{ direction: 'decrease', mw, for_min: 240, workload_class: 'training' }],
    },
  );
}

function applyNodeUpdates(nodes: GridNode[], phase: Phase) {
  return nodes.map((node) => ({ ...node, ...(phase.nodes[node.id] ?? {}) }));
}

function applyEdgeUpdates(edges: GridEdge[], phase: Phase) {
  return edges.map((edge) => ({ ...edge, ...(phase.edges[edge.id] ?? {}) }));
}

const NODE_LABELS: Record<string, string> = {
  'dc-caiso': 'DC-CAISO',
  'dc-ercot': 'DC-ERCOT',
  'dc-pjm': 'DC-PJM',
  vpp: 'Virtual Power Plant',
  critical: 'Critical load',
};

function edgePhrase(e: GridEdge): string {
  const from = NODE_LABELS[e.from] ?? e.from;
  const to = NODE_LABELS[e.to] ?? e.to;
  return `${from} → ${to}`;
}

export default function App() {
  const [scenario, setScenario] = useState<Scenario>(SCENARIOS[0]);
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const [metrics, setMetrics] = useState<Metrics>(initialMetrics);
  const [log, setLog] = useState<LogEntry[]>([
    makeLog('Bus online. Grid + compute agents nominal across CAISO, ERCOT, PJM.', 'info'),
  ]);
  const [bus, setBus] = useState<BusMessage[]>(() => [
    makeBus('GridStateUpdate', 'grid->compute', 'CAISO/SP15 · LMP $34 · stress 0.11 · headroom 26%', {
      ba: 'CAISO',
      lmp_dollars_mwh: 34,
      stress_score: 0.11,
    }),
    makeBus('FlexibilityEnvelope', 'compute->grid', 'envelope ← dc-caiso · 130 MW down · 240 min · training', {
      facility_id: 'dc-caiso',
      bands: [{ direction: 'decrease', mw: 130, for_min: 240 }],
    }),
    makeBus('GridStateUpdate', 'grid->compute', 'ERCOT/HOU_HUB · LMP $32 · stress 0.14 · headroom 19%', {
      ba: 'ERCOT',
      lmp_dollars_mwh: 32,
      stress_score: 0.14,
    }),
  ]);
  const [phaseLabel, setPhaseLabel] = useState('Ready');
  const [headline, setHeadline] = useState(
    'Ready: Murmuration Bus is watching LMP, headroom, envelopes across BAs.',
  );
  const [subhead, setSubhead] = useState(
    'Pick a scenario above to see the FlexibilityEnvelope protocol negotiate dispatch in operator-grade language.',
  );
  const [activeStory, setActiveStory] = useState<'need' | 'source' | 'route' | 'protect'>('need');
  const [decision, setDecision] = useState([
    'Grid agent: monitoring LMP and headroom across BAs.',
    'Compute agent: holding standing envelopes from DC-CAISO, DC-ERCOT, DC-PJM.',
  ]);
  const [running, setRunning] = useState(false);
  const [complete, setComplete] = useState(false);
  const [pendingGate, setPendingGate] = useState<{
    label: string;
    sublabel: string;
    nextIndex: number;
  } | null>(null);
  const [layers, setLayers] = useState<LayerState>({
    stress: true,
    reserves: true,
    critical: true,
    flows: true,
  });
  const [view, setView] = useState<'globe' | 'flat'>('globe');
  const [panelCollapsed, setPanelCollapsed] = useState<Record<string, boolean>>({});
  const [flashTrigger, setFlashTrigger] = useState(0);
  const [flashPhase, setFlashPhase] = useState<Phase | null>(null);
  // When a phase with a flash fires, we pause auto-advance until the user dismisses
  // the banner. pendingFlashAdvance holds the next index to fire on dismiss.
  const [pendingFlashAdvance, setPendingFlashAdvance] = useState<{
    target: Scenario;
    nextIndex: number;
  } | null>(null);
  const togglePanel = (key: string) =>
    setPanelCollapsed((c) => ({ ...c, [key]: !c[key] }));
  const timers = useRef<number[]>([]);

  const activeDispatches = edges.filter((e) => e.status === 'active' && e.mw && e.mw > 0);

  // Derived: which flow types are currently visible on the globe
  const stressedNode = nodes.find(
    (n) => (n.id === 'dc-caiso' || n.id === 'dc-ercot' || n.id === 'dc-pjm') &&
      (n.status === 'overload' || n.status === 'warning'),
  );
  const computeEdges = edges.filter(
    (e) => e.status === 'active' && e.from.startsWith('dc-') && e.to.startsWith('dc-') && e.mw,
  );
  const vppEdge = edges.find((e) => e.status === 'active' && e.from === 'vpp');
  const vppActive = nodes.find((n) => n.id === 'vpp')?.status === 'active' && !!vppEdge;
  const protectActive = edges.some((e) => e.status === 'active' && e.to === 'critical');

  const activeFlows = {
    stress: !!stressedNode,
    compute: computeEdges.length > 0,
    vpp: vppActive,
    protect: protectActive,
  };

  // Build the stack of "now playing" event entries
  const nowPlaying: Array<{ type: 'stress' | 'compute' | 'vpp' | 'protect'; label: string; detail: string }> = [];
  if (activeFlows.stress && stressedNode) {
    nowPlaying.push({
      type: 'stress',
      label: 'GRID STRESS',
      detail: `${NODE_LABELS[stressedNode.id] ?? stressedNode.id} · ${stressedNode.status === 'overload' ? 'overload' : 'warning'}${stressedNode.lmp ? ` · LMP $${stressedNode.lmp}/MWh` : ''}`,
    });
  }
  if (activeFlows.compute) {
    computeEdges.forEach((e) => {
      nowPlaying.push({
        type: 'compute',
        label: 'COMPUTE MIGRATION (fiber)',
        detail: `${e.mw} MW · ${NODE_LABELS[e.from] ?? e.from} → ${NODE_LABELS[e.to] ?? e.to} · jobs over fiber, no electrons cross`,
      });
    });
  }
  if (activeFlows.vpp && vppEdge) {
    nowPlaying.push({
      type: 'vpp',
      label: 'VPP LOCAL INJECTION',
      detail: `${vppEdge.mw} MW · home batteries + EVs discharge into local grid`,
    });
  }
  if (activeFlows.protect) {
    nowPlaying.push({
      type: 'protect',
      label: 'PROTECTING CRITICAL SERVICES',
      detail: `Power held to hospitals + water + emergency`,
    });
  }
  const marketRequest = complete
    ? `Settled: ${activeDispatches.reduce((sum, e) => sum + (e.mw ?? 0), 0).toLocaleString()} MW relief delivered`
    : phaseLabel === 'Ready'
      ? 'No active DispatchRequest'
      : `${scenario.name}`;

  function reset(nextScenario?: Scenario) {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    setNodes(initialNodes);
    setEdges(initialEdges);
    setMetrics(initialMetrics);
    setLog([
      makeLog(
        nextScenario ? `Loaded scenario: ${nextScenario.name}` : 'System reset.',
        'info',
      ),
    ]);
    setPhaseLabel('Ready');
    setHeadline('Ready: Murmuration Bus is watching LMP, headroom, envelopes across BAs.');
    setSubhead(
      nextScenario
        ? nextScenario.description
        : 'Pick a scenario above to see the FlexibilityEnvelope protocol negotiate dispatch in operator-grade language.',
    );
    setActiveStory('need');
    setDecision([
      'Grid agent: monitoring LMP and headroom across BAs.',
      'Compute agent: holding standing envelopes from DC-CAISO, DC-ERCOT, DC-PJM.',
    ]);
    setRunning(false);
    setComplete(false);
    setPendingGate(null);
    setPendingFlashAdvance(null);
    setFlashPhase(null);
  }

  function applyPhase(phase: Phase) {
    setPhaseLabel(phase.label);
    setHeadline(phase.headline);
    setSubhead(phase.subhead);
    setActiveStory(phase.story);
    setDecision(phase.decision);
    setNodes((current) => applyNodeUpdates(current, phase));
    setEdges((current) => applyEdgeUpdates(current, phase));
    setMetrics((current) => ({ ...current, ...phase.metrics }));
    setLog((current) => [
      ...current,
      ...phase.logs.map((entry) => makeLog(entry.message, entry.level)),
    ]);
    if (phase.bus?.length) {
      setBus((current) => [
        ...current,
        ...phase.bus.map((m, i) =>
          makeBus(m.type, m.direction, m.summary, { ...m.payload, _seq: current.length + i }),
        ),
      ]);
    }
    // Each phase: replace any existing flash with the new one (or clear if this phase has none).
    if (phase.flash) {
      setFlashPhase(phase);
      setFlashTrigger((t) => t + 1);
    } else {
      setFlashPhase(null);
    }
  }

  useEffect(() => {
    if (running) return;
    const tick = window.setInterval(() => {
      setBus((current) => {
        const next = Math.random() < 0.3 ? ambientEnvelope() : ambientGridState();
        return [...current, next];
      });
    }, 3500);
    return () => window.clearInterval(tick);
  }, [running]);

  function selectScenario(s: Scenario) {
    if (s.id === scenario.id) return;
    setScenario(s);
    reset(s);
  }

  // Apply one phase, then decide what to do next:
  //   - last phase  → mark complete
  //   - has gate    → pause; surface the gate-overlay button
  //   - has flash   → pause; the next phase will fire when user dismisses the flash
  //   - plain phase → auto-advance after the delta to the next phase
  function applyAndAdvance(target: Scenario, idx: number) {
    const phase = target.phases[idx];
    applyPhase(phase);
    const isLast = idx === target.phases.length - 1;

    if (isLast) {
      setRunning(false);
      setComplete(true);
      return;
    }

    if (phase.gated) {
      setRunning(false);
      setPendingGate({
        label: phase.gateLabel ?? 'Continue →',
        sublabel: phase.gateSublabel ?? '',
        nextIndex: idx + 1,
      });
      return;
    }

    if (phase.flash) {
      // Pause auto-advance — the user must dismiss the flash to continue.
      setPendingFlashAdvance({ target, nextIndex: idx + 1 });
      return;
    }

    // Plain auto-advance
    const next = target.phases[idx + 1];
    const delta = Math.max(0, next.delayMs - phase.delayMs);
    const timer = window.setTimeout(() => applyAndAdvance(target, idx + 1), delta);
    timers.current.push(timer);
  }

  function triggerScenario(s?: Scenario) {
    const target = s ?? scenario;
    if (running || pendingGate || pendingFlashAdvance) return;
    if (s && s.id !== scenario.id) setScenario(s);
    reset(target);
    setRunning(true);
    applyAndAdvance(target, 0);
  }

  function resumeFromGate() {
    if (!pendingGate) return;
    const target = scenario;
    const startIdx = pendingGate.nextIndex;
    setPendingGate(null);
    setRunning(true);
    applyAndAdvance(target, startIdx);
  }

  // Called by the FlashBanner when the user dismisses it. Advances to the next
  // phase if the engine was paused waiting on the flash.
  function onFlashDismissed() {
    setFlashPhase(null);
    if (pendingFlashAdvance) {
      const { target, nextIndex } = pendingFlashAdvance;
      setPendingFlashAdvance(null);
      applyAndAdvance(target, nextIndex);
    }
  }

  function toggleLayer(key: keyof LayerState) {
    setLayers((l) => ({ ...l, [key]: !l[key] }));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Murmuration · Grid-Aware AI Agents</p>
          <h1>FlexibilityEnvelope Protocol — Live Demo</h1>
        </div>
        <div className="phase-pill">{complete ? 'Demo Complete' : phaseLabel}</div>
      </header>

      <section className="scenario-strip">
        <div className="scenario-info">
          <strong>
            {scenario.name}
            {scenario.anchor && <span className="real-data-badge" title={scenario.anchor.realFact}>REAL DATA</span>}
          </strong>
          <span>{scenario.description}</span>
          {scenario.anchor && (
            <a
              className="anchor-line"
              href={scenario.anchor.sourceUrl}
              target="_blank"
              rel="noreferrer"
              title={scenario.anchor.realFact}
            >
              ▸ Anchored to: {scenario.anchor.incident}
            </a>
          )}
        </div>
        <div className="scenario-menu">
          {SCENARIOS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`scenario-chip ${s.id === scenario.id ? 'selected' : ''}`}
              onClick={() => selectScenario(s)}
              disabled={running || !!pendingGate}
              title={s.description}
            >
              {s.name}
            </button>
          ))}
        </div>
        <div className="actions">
          <button onClick={() => triggerScenario()} disabled={running || !!pendingGate}>
            {running ? 'Running…' : pendingGate ? 'Paused — see globe' : 'Run Scenario'}
          </button>
          <button className="secondary" onClick={() => reset(scenario)}>
            Reset
          </button>
        </div>
      </section>

      <section className="story-band" aria-label="Scenario phases">
        {scenario.phases.map((p, i) => (
          <article
            key={p.label}
            className={`story-step ${activeStory === p.story ? 'active' : ''}`}
          >
            <span>
              {i + 1}. {p.story === 'need' ? 'Detect' : p.story === 'source' ? 'Source' : p.story === 'route' ? 'Route' : 'Settle'}
            </span>
            <strong>{p.label}</strong>
          </article>
        ))}
      </section>

      <div className="workspace">
        <section className="globe-area">
          <div className="globe-title">
            <strong>{headline}</strong>
            <span>{subhead}</span>
            {scenario.anchor && (running || complete) && (
              <a
                className="real-data-banner"
                href={scenario.anchor.sourceUrl}
                target="_blank"
                rel="noreferrer"
                title={scenario.anchor.realFact}
              >
                <span className="rdb-tag">REPLAYING REAL DATA</span>
                <span className="rdb-text">
                  {scenario.anchor.incident}
                </span>
                <span className="rdb-source">↗ source</span>
              </a>
            )}
          </div>
          <div className="view-tabs">
            <button
              type="button"
              className={view === 'globe' ? 'active' : ''}
              onClick={() => setView('globe')}
            >
              ● 3D Globe
            </button>
            <button
              type="button"
              className={view === 'flat' ? 'active' : ''}
              onClick={() => setView('flat')}
            >
              ■ Flat map
            </button>
          </div>

          <div className="map-frame">
            {view === 'globe' ? (
              <GlobeView
                nodes={nodes}
                edges={edges}
                layers={layers}
                flashActive={!!flashPhase}
              />
            ) : (
              <FlatMapView
                nodes={nodes}
                edges={edges}
                layers={layers}
                flashActive={!!flashPhase}
              />
            )}
            <StabilityGauge nodes={nodes} />

            <LegendStrip activeFlows={activeFlows} />

            {nowPlaying.length > 0 && (
              <div className="now-playing" aria-label="Now playing">
                <div className="np-header">▶ Now happening</div>
                {nowPlaying.map((ev, i) => (
                  <div key={`${ev.type}-${i}`} className={`np-row np-${ev.type}`}>
                    <span className="np-label">{ev.label}</span>
                    <span className="np-detail">{ev.detail}</span>
                  </div>
                ))}
              </div>
            )}

            <FlashBanner
              trigger={flashTrigger}
              phase={flashPhase}
              onDismiss={onFlashDismissed}
            />
          </div>

          {pendingGate && (
            <div className="gate-overlay" role="dialog" aria-label="Scenario paused">
              <button
                type="button"
                className="gate-button"
                onClick={resumeFromGate}
                autoFocus
              >
                {pendingGate.label} →
              </button>
              {pendingGate.sublabel && (
                <p className="gate-sublabel">{pendingGate.sublabel}</p>
              )}
            </div>
          )}

          <div className="layer-toggles" aria-label="Map layers">
            <button
              type="button"
              className={layers.stress ? 'on' : ''}
              onClick={() => toggleLayer('stress')}
            >
              <span className="dot stress" /> Grid stress
            </button>
            <button
              type="button"
              className={layers.flows ? 'on' : ''}
              onClick={() => toggleLayer('flows')}
            >
              <span className="dot flows" /> Dispatch flows
            </button>
            <button
              type="button"
              className={layers.reserves ? 'on' : ''}
              onClick={() => toggleLayer('reserves')}
              title="Virtual Power Plant — aggregated home batteries + EVs + smart thermostats acting as one dispatchable resource"
            >
              <span className="dot reserve" /> Virtual Power Plant
            </button>
            <button
              type="button"
              className={layers.critical ? 'on' : ''}
              onClick={() => toggleLayer('critical')}
            >
              <span className="dot critical" /> Critical infrastructure
            </button>
          </div>

          {/* Bottom-left legend removed — replaced by always-visible LegendStrip
              at top-center of the map (see <LegendStrip /> above). */}
        </section>

        <aside className="side-panel">
          <section
            className="panel decision-card"
            data-collapsed={panelCollapsed.marketplace ? 'true' : undefined}
          >
            <h2 className="panel-toggle" onClick={() => togglePanel('marketplace')} role="button">
              <span className="chevron">{panelCollapsed.marketplace ? '▸' : '▾'}</span>
              Flex Marketplace · {scenario.name.split('·')[0].trim()}
            </h2>
            <strong>
              {complete
                ? 'Settled · telemetry-confirmed'
                : phaseLabel === 'Ready'
                  ? 'Awaiting GridStateUpdate stress'
                  : 'Negotiating envelopes'}
            </strong>
            <p>{decision.join(' ')}</p>
            <div className="market-request">
              <span>DispatchRequest</span>
              <strong>{marketRequest}</strong>
            </div>
            <div className="source-list">
              {activeDispatches.length === 0 && (
                <article className="source-row">
                  <div>
                    <b>No active dispatches</b>
                    <small>Standing envelopes held across all facilities</small>
                  </div>
                  <strong>—</strong>
                </article>
              )}
              {activeDispatches.map((e) => (
                <article key={e.id} className="source-row accepted">
                  <div>
                    <b>{edgePhrase(e)}</b>
                    <small>{e.label}</small>
                  </div>
                  <strong>{e.mw} MW</strong>
                </article>
              ))}
            </div>
          </section>
          <BusTicker
            messages={bus}
            collapsed={panelCollapsed.bus}
            onToggleCollapse={() => togglePanel('bus')}
          />
          <MetricsPanel
            metrics={metrics}
            collapsed={panelCollapsed.metrics}
            onToggleCollapse={() => togglePanel('metrics')}
          />
          <EventLog
            entries={log}
            collapsed={panelCollapsed.log}
            onToggleCollapse={() => togglePanel('log')}
          />
        </aside>
      </div>
    </main>
  );
}
