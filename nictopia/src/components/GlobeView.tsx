import { useEffect, useMemo, useRef, useState } from 'react';
import Globe from 'react-globe.gl';
import type { GridEdge, GridNode } from '../types';
import {
  BA_CENTERS,
  CRITICAL_SITES_BY_REGION,
  DC_LOCATIONS,
  VPP_SWARM,
  type CriticalSite,
} from '../lib/geo';

const COLORS = {
  idle: '#5eead4',
  warning: '#fbbf24',
  overload: '#fb7185',
  active: '#32d5c3',
  stable: '#a7f3d0',
  offline: '#64748b',
  vpp: '#9d6ff0',
  vppActive: '#d8b4fe',
  critical: '#34d399',
  criticalAlert: '#fbbf24',
  trunk: '#7dd3fc',     // compute migration (cross-region, fiber)
  vppArc: '#c084fc',
  protect: '#34d399',
  stress: '#fb7185',
} as const;

export type LayerState = {
  stress: boolean;
  reserves: boolean;
  critical: boolean;
  flows: boolean;
};

interface InnerProps {
  nodes: GridNode[];
  edges: GridEdge[];
  layers: LayerState;
  width: number;
  height: number;
  /** When true, map-overlay labels are suppressed so the FlashBanner can
   *  command attention without smaller labels poking out behind it. */
  flashActive?: boolean;
}

function nodeLatLng(id: string) {
  if (id === 'dc-caiso' || id === 'dc-ercot' || id === 'dc-pjm') {
    const loc = DC_LOCATIONS[id];
    return { lat: loc.lat, lng: loc.lng };
  }
  if (id === 'vpp') return { lat: 37.78, lng: -122.42 };
  if (id === 'critical') return { lat: 29.76, lng: -95.37 };
  return null;
}

// Bearing in CSS-rotation degrees (clockwise from east axis).
// Approximates a flat lat/lng projection — good enough for arrows over a
// North-America-centered globe view.
function arrowBearing(
  src: { lat: number; lng: number },
  dst: { lat: number; lng: number },
): number {
  const dLng = dst.lng - src.lng;
  const dLat = dst.lat - src.lat;
  // -dLat because screen Y is inverted relative to lat (north is "up" on screen)
  return (Math.atan2(-dLat, dLng) * 180) / Math.PI;
}

function GlobeInner({ nodes, edges, layers, width, height, flashActive }: InnerProps) {
  const globeRef = useRef<any>(null);
  const byId = useMemo(
    () => Object.fromEntries(nodes.map((n) => [n.id, n])) as Record<string, GridNode>,
    [nodes],
  );

  const stressedDcId = useMemo(() => {
    for (const id of ['dc-caiso', 'dc-ercot', 'dc-pjm'] as const) {
      const n = byId[id];
      if (n?.status === 'overload' || n?.status === 'warning') return id;
    }
    return null;
  }, [byId]);

  const criticalSites: CriticalSite[] = useMemo(() => {
    const ba = stressedDcId ? DC_LOCATIONS[stressedDcId].ba : 'ERCOT';
    return CRITICAL_SITES_BY_REGION[ba] ?? CRITICAL_SITES_BY_REGION.ERCOT;
  }, [stressedDcId]);

  // The DC that VPP injection is supporting (derived from active vpp-* edge).
  const vppTargetDcId = useMemo(() => {
    for (const e of edges) {
      if (e.from === 'vpp' && e.status === 'active') {
        return e.to as keyof typeof DC_LOCATIONS;
      }
    }
    return null;
  }, [edges]);

  // The BA region where VPP injection is happening (= same region as the target DC).
  const vppTargetBa = vppTargetDcId ? DC_LOCATIONS[vppTargetDcId].ba : null;

  const protectSourceDcId = useMemo(() => {
    for (const e of edges) {
      if (e.to === 'critical' && e.status === 'active') {
        return e.from as keyof typeof DC_LOCATIONS;
      }
    }
    return null;
  }, [edges]);

  useEffect(() => {
    const g = globeRef.current;
    if (!g) return;
    g.pointOfView({ lat: 39, lng: -98, altitude: 1.9 }, 0);
    const controls = g.controls();
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.22;
    controls.enableZoom = true;
    controls.minDistance = 90;
    controls.maxDistance = 600;
    const stopRotate = () => {
      controls.autoRotate = false;
    };
    controls.addEventListener('start', stopRotate);
    return () => controls.removeEventListener('start', stopRotate);
  }, []);

  const points = useMemo(() => {
    const result: Array<Record<string, unknown>> = [];

    (['dc-caiso', 'dc-ercot', 'dc-pjm'] as const).forEach((id) => {
      const node = byId[id];
      if (!node) return;
      const loc = DC_LOCATIONS[id];
      result.push({
        kind: 'dc',
        id,
        lat: loc.lat,
        lng: loc.lng,
        color: COLORS[node.status as keyof typeof COLORS] ?? COLORS.idle,
        radius: 0.85,
        altitude: 0.045,
        label: node.label,
        nodeType: node.nodeType,
        ba: loc.ba,
        metro: loc.metro,
        status: node.status,
        load: node.load,
        lmp: node.lmp,
      });
    });

    if (layers.reserves) {
      const vppActive = byId.vpp?.status === 'active';
      VPP_SWARM.forEach((v) => {
        // When VPP is active, the halo + injection pill carry the "engaged" message.
        // Dots stay subtle — slight color brightness boost for the engaged region,
        // no size growth. This avoids the "glob of glowing play signs" effect.
        const dotIsActive = vppActive && vppTargetBa !== null && v.ba === vppTargetBa;
        result.push({
          kind: 'vpp',
          id: v.id,
          lat: v.lat,
          lng: v.lng,
          color: dotIsActive ? COLORS.vppActive : COLORS.vpp,
          radius: dotIsActive ? 0.20 : 0.14,
          altitude: dotIsActive ? 0.01 : 0.005,
          ba: v.ba,
        });
      });
    }

    if (layers.critical) {
      const cAlert = byId.critical?.status === 'warning';
      criticalSites.forEach((c) => {
        result.push({
          kind: 'critical',
          id: c.id,
          lat: c.lat,
          lng: c.lng,
          color: cAlert ? COLORS.criticalAlert : COLORS.critical,
          radius: 0.32,
          altitude: 0.012,
          label: c.label,
        });
      });
    }

    return result;
  }, [byId, layers, criticalSites, vppTargetBa]);

  const arcs = useMemo(() => {
    if (!layers.flows) return [];
    const result: Array<Record<string, unknown>> = [];

    // Cross-region arcs: compute migration over fiber. NOT electricity.
    // Within-region arcs (DC→critical) = local electrical power.
    // When VPP halo is active, dim the compute arc so the new VPP visuals stand out.
    const computeArcDimmed = byId.vpp?.status === 'active';
    edges.forEach((e) => {
      if (e.status !== 'active') return;
      if (e.from === 'vpp') return; // VPP rendered as ring, not arc
      if (e.to === 'critical') return; // protect lines handled below per-site
      const start = nodeLatLng(e.from);
      const end = nodeLatLng(e.to);
      if (!start || !end) return;
      const c = computeArcDimmed ? '#5a8aa8' : COLORS.trunk;
      result.push({
        kind: 'compute',
        startLat: start.lat,
        startLng: start.lng,
        endLat: end.lat,
        endLng: end.lng,
        color: [c, c],
        stroke: computeArcDimmed ? 1.0 : 1.6,
        mw: e.mw,
      });
    });

    if (layers.critical && protectSourceDcId) {
      const source = nodeLatLng(protectSourceDcId);
      if (source) {
        criticalSites.forEach((c) => {
          result.push({
            kind: 'protect',
            startLat: source.lat,
            startLng: source.lng,
            endLat: c.lat,
            endLng: c.lng,
            color: [COLORS.protect, COLORS.protect],
            stroke: 0.55,
          });
        });
      }
    }

    return result;
  }, [edges, layers, criticalSites, protectSourceDcId]);

  const rings = useMemo(() => {
    const result: Array<Record<string, unknown>> = [];

    // Stress ring on the overloaded DC
    if (layers.stress && stressedDcId) {
      const node = byId[stressedDcId];
      const loc = DC_LOCATIONS[stressedDcId];
      result.push({
        lat: loc.lat,
        lng: loc.lng,
        color: COLORS.stress,
        maxR: node?.status === 'overload' ? 9 : 5,
        speed: 2.4,
        repeat: 650,
      });
    }

    // VPP injection ring on the active BA centroid (aggregate halo replacing the 36 individual arcs)
    if (layers.reserves && byId.vpp?.status === 'active' && vppTargetBa) {
      const baCenter = BA_CENTERS.find((b) => b.ba === vppTargetBa);
      if (baCenter) {
        result.push({
          lat: baCenter.lat,
          lng: baCenter.lng,
          color: COLORS.vppArc,
          maxR: 8,
          speed: 1.6,
          repeat: 900,
        });
      }
    }

    return result;
  }, [byId, layers, stressedDcId, vppTargetBa]);

  // BA name labels + active arc midpoint labels
  const htmlOverlays = useMemo(() => {
    // Suppress the BA label for whichever BA currently has VPP injection happening —
    // its centroid is occupied by the VPP pill and the BA name competes for the
    // same spot. (Other BA labels stay visible for orientation.)
    const items: Array<Record<string, unknown>> = BA_CENTERS
      .filter((b) => !(vppTargetBa && b.ba === vppTargetBa))
      .map((b) => ({
        kind: 'ba',
        lat: b.lat,
        lng: b.lng,
        ba: b.ba,
      }));

    // While the FlashBanner is visible, suppress all competing in-map labels
    // (VPP pill, mid-arc labels, direction arrows). They reappear after dismiss.
    if (flashActive) {
      return items;
    }

    // VPP injection text label at the active BA centroid
    if (layers.reserves && byId.vpp?.status === 'active' && vppTargetBa) {
      const baCenter = BA_CENTERS.find((b) => b.ba === vppTargetBa);
      const vppEdge = edges.find((e) => e.from === 'vpp' && e.status === 'active');
      if (baCenter && vppEdge?.mw) {
        items.push({
          kind: 'vpp-label',
          lat: baCenter.lat - 1.3,
          lng: baCenter.lng,
          text: `+${vppEdge.mw} MW · VPP local injection`,
        });
      }
    }

    // Mid-arc labels + ¾-along-arc direction arrows for active compute migration arcs
    if (layers.flows) {
      const NODE_NAME: Record<string, string> = {
        'dc-caiso': 'CAISO',
        'dc-ercot': 'ERCOT',
        'dc-pjm': 'PJM',
      };
      edges.forEach((e) => {
        if (e.status !== 'active' || !e.mw) return;
        if (e.from === 'vpp' || e.to === 'critical') return;
        const start = nodeLatLng(e.from);
        const end = nodeLatLng(e.to);
        if (!start || !end) return;
        items.push({
          kind: 'arc-label',
          arcType: 'compute',
          lat: (start.lat + end.lat) / 2 + 1.5,
          lng: (start.lng + end.lng) / 2,
          primary: `${e.mw} MW REROUTED`,
          secondary: `${NODE_NAME[e.from] ?? e.from} → ${NODE_NAME[e.to] ?? e.to} · scheduler shifts work`,
        });
        // Direction arrow placed 75% along the arc (clearly mid-line, not at endpoint
        // where it could be mistaken for a node marker)
        items.push({
          kind: 'arrow',
          arcType: 'compute',
          lat: start.lat * 0.25 + end.lat * 0.75,
          lng: start.lng * 0.25 + end.lng * 0.75,
          bearing: arrowBearing(start, end),
        });
      });

      // One label + one arrow per critical hospital (so each protect line gets a directional cue)
      if (layers.critical && protectSourceDcId) {
        const source = nodeLatLng(protectSourceDcId);
        if (source) {
          // One overall label at centroid of critical sites
          const meanLat = criticalSites.reduce((s, c) => s + c.lat, 0) / criticalSites.length;
          const meanLng = criticalSites.reduce((s, c) => s + c.lng, 0) / criticalSites.length;
          items.push({
            kind: 'arc-label',
            arcType: 'protect',
            lat: (source.lat + meanLat) / 2 - 0.8,
            lng: (source.lng + meanLng) / 2,
            primary: 'PROTECTED',
            secondary: 'local power held to critical services',
          });
          // (Protect-line arrows removed — the protect lines themselves carry direction
          // via dash flow + the "PROTECTED" label + endpoint hospital pins. 4 extra arrows
          // at the TX hospital cluster were creating a "glob of play signs" effect.)
        }
      }
    }

    return items;
  }, [edges, layers, byId, vppTargetBa, protectSourceDcId, criticalSites, flashActive]);

  function zoom(delta: number) {
    const g = globeRef.current;
    if (!g) return;
    const pov = g.pointOfView();
    const next = Math.min(4.0, Math.max(0.55, pov.altitude * (delta < 0 ? 0.7 : 1.4)));
    g.pointOfView({ ...pov, altitude: next }, 350);
  }

  function recenter() {
    const g = globeRef.current;
    if (!g) return;
    g.pointOfView({ lat: 39, lng: -98, altitude: 1.9 }, 600);
  }

  return (
    <>
      <div className="globe-controls" aria-label="Globe controls">
        <button type="button" onClick={() => zoom(-1)} title="Zoom in">＋</button>
        <button type="button" onClick={() => zoom(1)} title="Zoom out">−</button>
        <button type="button" onClick={recenter} title="Recenter on North America">⌖</button>
      </div>
      <Globe
        ref={globeRef}
        width={width}
        height={height}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl="https://unpkg.com/three-globe/example/img/earth-night.jpg"
        bumpImageUrl="https://unpkg.com/three-globe/example/img/earth-topology.png"
        atmosphereColor="#5eead4"
        atmosphereAltitude={0.18}
        pointsData={points}
        pointLat="lat"
        pointLng="lng"
        pointColor="color"
        pointAltitude="altitude"
        pointRadius="radius"
        pointResolution={14}
        pointLabel={(d: any) => {
          if (d.kind === 'dc') {
            return `<div class="globe-tip"><strong>${d.label}</strong><br/><span class="muted">${d.nodeType}</span><br/><span>Load <b>${d.load}%</b> · LMP <b>$${d.lmp}/MWh</b></span><br/><span class="muted">Status: ${d.status}</span></div>`;
          }
          if (d.kind === 'critical') {
            return `<div class="globe-tip"><strong>${d.label}</strong><br/><span class="muted">Critical infrastructure</span></div>`;
          }
          if (d.kind === 'vpp') {
            return `<div class="globe-tip"><strong>VPP node · ${d.ba}</strong><br/><span class="muted">Home batteries + EVs + smart thermostats</span><br/><span class="muted">Discharges into local grid (${d.ba})</span></div>`;
          }
          return '';
        }}
        arcsData={arcs}
        arcStartLat="startLat"
        arcStartLng="startLng"
        arcEndLat="endLat"
        arcEndLng="endLng"
        arcColor="color"
        arcStroke="stroke"
        arcDashLength={0.18}
        arcDashGap={0.08}
        arcDashAnimateTime={(d: any) => (d.kind === 'compute' ? 650 : 1400)}
        arcAltitudeAutoScale={(d: any) => (d.kind === 'protect' ? 0.15 : 0.55)}
        ringsData={rings}
        ringLat="lat"
        ringLng="lng"
        ringColor={(d: any) => () => d.color}
        ringMaxRadius="maxR"
        ringPropagationSpeed="speed"
        ringRepeatPeriod="repeat"
        htmlElementsData={htmlOverlays}
        htmlLat="lat"
        htmlLng="lng"
        htmlAltitude={0.015}
        htmlElement={(d: any) => {
          const el = document.createElement('div');
          if (d.kind === 'ba') {
            el.className = 'ba-label';
            el.textContent = d.ba;
          } else if (d.kind === 'arc-label') {
            el.className = `arc-label arc-label-${d.arcType}`;
            el.innerHTML = `<div class="arc-label-primary">${d.primary}</div><div class="arc-label-secondary">${d.secondary}</div>`;
          } else if (d.kind === 'vpp-label') {
            el.className = 'vpp-injection-label';
            el.textContent = d.text;
          } else if (d.kind === 'arrow') {
            el.className = `arc-arrow arc-arrow-${d.arcType}`;
            el.style.transform = `translate(-50%, -50%) rotate(${d.bearing}deg)`;
            el.innerHTML = '<span class="arc-arrow-glyph">►</span>';
          }
          return el;
        }}
      />
    </>
  );
}

export function GlobeView({
  nodes,
  edges,
  layers,
  flashActive,
}: {
  nodes: GridNode[];
  edges: GridEdge[];
  layers: LayerState;
  flashActive?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });

  useEffect(() => {
    if (!ref.current) return;
    const measure = () => {
      const r = ref.current!.getBoundingClientRect();
      setSize({ w: Math.max(320, r.width), h: Math.max(320, r.height) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} className="globe-canvas">
      <GlobeInner
        nodes={nodes}
        edges={edges}
        layers={layers}
        width={size.w}
        height={size.h}
        flashActive={flashActive}
      />
    </div>
  );
}
