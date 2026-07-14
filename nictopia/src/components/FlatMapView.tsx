import { useEffect, useMemo, useRef, useState } from 'react';
import { ComposableMap, Geographies, Geography, Marker, Line, ZoomableGroup } from 'react-simple-maps';
import statesTopo from 'us-atlas/states-10m.json';
import type { GridEdge, GridNode } from '../types';
import {
  BA_CENTERS,
  CRITICAL_SITES_BY_REGION,
  DC_LOCATIONS,
  VPP_SWARM,
  type CriticalSite,
} from '../lib/geo';
import type { LayerState } from './GlobeView';

interface Props {
  nodes: GridNode[];
  edges: GridEdge[];
  layers: LayerState;
  /** When true, suppress in-map labels (VPP pill, BA names) so the FlashBanner
   *  isn't competing for visual attention. */
  flashActive?: boolean;
}

const SHORT_LABEL: Record<string, string> = {
  'dc-caiso': 'DC-CAISO',
  'dc-ercot': 'DC-ERCOT',
  'dc-pjm': 'DC-PJM',
};

function nodeLatLng(id: string) {
  if (id === 'dc-caiso' || id === 'dc-ercot' || id === 'dc-pjm') {
    const loc = DC_LOCATIONS[id];
    return { lat: loc.lat, lng: loc.lng };
  }
  return null;
}

export function FlatMapView({ nodes, edges, layers, flashActive }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 540 });

  useEffect(() => {
    if (!ref.current) return;
    const measure = () => {
      const r = ref.current!.getBoundingClientRect();
      setSize({ w: Math.max(420, r.width), h: Math.max(320, r.height) });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

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

  const vppTargetDcId = useMemo(() => {
    for (const e of edges) {
      if (e.from === 'vpp' && e.status === 'active') {
        return e.to as keyof typeof DC_LOCATIONS;
      }
    }
    return null;
  }, [edges]);

  const vppTargetBa = vppTargetDcId ? DC_LOCATIONS[vppTargetDcId].ba : null;

  const protectSourceDcId = useMemo(() => {
    for (const e of edges) {
      if (e.to === 'critical' && e.status === 'active') {
        return e.from as keyof typeof DC_LOCATIONS;
      }
    }
    return null;
  }, [edges]);

  const computeArcs = useMemo(() => {
    if (!layers.flows) return [] as Array<{
      from: [number, number];
      to: [number, number];
      mw: number;
      labelFrom: string;
      labelTo: string;
    }>;
    const out: Array<{
      from: [number, number];
      to: [number, number];
      mw: number;
      labelFrom: string;
      labelTo: string;
    }> = [];
    edges.forEach((e) => {
      if (e.status !== 'active' || !e.mw) return;
      if (e.from === 'vpp' || e.to === 'critical') return;
      const start = nodeLatLng(e.from);
      const end = nodeLatLng(e.to);
      if (!start || !end) return;
      out.push({
        from: [start.lng, start.lat],
        to: [end.lng, end.lat],
        mw: e.mw,
        labelFrom: SHORT_LABEL[e.from] ?? e.from,
        labelTo: SHORT_LABEL[e.to] ?? e.to,
      });
    });
    return out;
  }, [edges, layers]);

  const protectLines = useMemo(() => {
    if (!layers.critical || !protectSourceDcId) return [];
    const src = nodeLatLng(protectSourceDcId);
    if (!src) return [];
    return criticalSites.map((c) => ({
      from: [src.lng, src.lat] as [number, number],
      to: [c.lng, c.lat] as [number, number],
      id: c.id,
    }));
  }, [layers.critical, protectSourceDcId, criticalSites]);

  const vppActive = byId.vpp?.status === 'active' && !!vppTargetBa;
  const vppEdge = edges.find((e) => e.from === 'vpp' && e.status === 'active');

  const stressedLoc = stressedDcId ? DC_LOCATIONS[stressedDcId] : null;
  const vppHaloCenter = vppTargetBa ? BA_CENTERS.find((b) => b.ba === vppTargetBa) : null;

  return (
    <div ref={ref} className="flatmap-canvas">
      <ComposableMap
        projection="geoAlbersUsa"
        width={size.w}
        height={size.h}
        projectionConfig={{ scale: Math.min(size.w * 1.2, size.h * 1.9) }}
        style={{ width: '100%', height: '100%' }}
      >
        <ZoomableGroup minZoom={1} maxZoom={6} center={[-98, 38]} zoom={1}>
          {/* State outlines */}
          <Geographies geography={statesTopo as any}>
            {({ geographies }: any) =>
              geographies.map((g: any) => (
                <Geography
                  key={g.rsmKey}
                  geography={g}
                  className="flat-state"
                  style={{
                    default: { outline: 'none' },
                    hover: { outline: 'none' },
                    pressed: { outline: 'none' },
                  }}
                />
              ))
            }
          </Geographies>

          {/* Stress ring (red expanding circle) */}
          {layers.stress && stressedLoc && (
            <Marker coordinates={[stressedLoc.lng, stressedLoc.lat]}>
              <circle r={20} className="flat-stress-ring" />
              <circle r={12} className="flat-stress-ring flat-stress-ring-inner" />
            </Marker>
          )}

          {/* VPP halo (purple expanding ring at BA centroid) — pill text hidden during flash */}
          {layers.reserves && vppActive && vppHaloCenter && (
            <Marker coordinates={[vppHaloCenter.lng, vppHaloCenter.lat]}>
              <circle r={26} className="flat-vpp-halo" />
              {!flashActive && (
                <text className="flat-vpp-pill" y={-32} textAnchor="middle">
                  +{vppEdge?.mw} MW · VPP local injection
                </text>
              )}
            </Marker>
          )}

          {/* VPP swarm dots */}
          {layers.reserves &&
            VPP_SWARM.map((v) => {
              const isActive = vppActive && vppTargetBa !== null && v.ba === vppTargetBa;
              return (
                <Marker key={v.id} coordinates={[v.lng, v.lat]}>
                  <circle
                    r={isActive ? 2.8 : 1.8}
                    className={`flat-vpp-dot ${isActive ? 'on' : ''}`}
                  />
                </Marker>
              );
            })}

          {/* Compute migration arcs (cross-region, dashed light blue).
              Dimmed when VPP is active so the new VPP halo visuals stand out. */}
          {computeArcs.map((a, i) => (
            <Line
              key={`compute-${i}`}
              from={a.from}
              to={a.to}
              className={`flat-arc-compute ${vppActive ? 'dimmed' : ''}`}
            />
          ))}

          {/* Protect lines (DC → critical sites, green) */}
          {protectLines.map((l) => (
            <Line
              key={`protect-${l.id}`}
              from={l.from}
              to={l.to}
              className="flat-arc-protect"
            />
          ))}

          {/* Critical hospital pins */}
          {layers.critical &&
            criticalSites.map((c) => {
              const cAlert = byId.critical?.status === 'warning';
              return (
                <Marker key={c.id} coordinates={[c.lng, c.lat]}>
                  <circle
                    r={4}
                    className={`flat-critical ${cAlert ? 'alert' : ''}`}
                  />
                  <text x={5} y={1} className="flat-critical-label">
                    +
                  </text>
                </Marker>
              );
            })}

          {/* DC markers (large, with labels) */}
          {(['dc-caiso', 'dc-ercot', 'dc-pjm'] as const).map((id) => {
            const node = byId[id];
            if (!node) return null;
            const loc = DC_LOCATIONS[id];
            return (
              <Marker key={id} coordinates={[loc.lng, loc.lat]}>
                <circle r={9} className={`flat-dc flat-dc-${node.status}`} />
                <circle r={4.5} className="flat-dc-core" />
                <text textAnchor="middle" y={-14} className="flat-dc-label">
                  {SHORT_LABEL[id]}
                </text>
              </Marker>
            );
          })}

          {/* Compute migration arc labels at midpoint */}
          {computeArcs.map((a, i) => {
            const midLng = (a.from[0] + a.to[0]) / 2;
            const midLat = (a.from[1] + a.to[1]) / 2;
            return (
              <Marker key={`label-${i}`} coordinates={[midLng, midLat + 1.5]}>
                <foreignObject x={-90} y={-22} width={180} height={44}>
                  <div className="flat-arc-label">
                    <div className="flat-arc-label-primary">{a.mw} MW REROUTED</div>
                    <div className="flat-arc-label-secondary">
                      {a.labelFrom} → {a.labelTo} · scheduler shifts work
                    </div>
                  </div>
                </foreignObject>
              </Marker>
            );
          })}

          {/* BA region labels — hide the one for the BA where VPP is currently
              injecting (the VPP halo + pill occupy that centroid). */}
          {BA_CENTERS
            .filter((b) => !(vppTargetBa && b.ba === vppTargetBa))
            .map((b) => (
              <Marker key={`ba-${b.ba}`} coordinates={[b.lng, b.lat - 2.6]}>
                <text textAnchor="middle" className="flat-ba-label">
                  {b.ba}
                </text>
              </Marker>
            ))}
        </ZoomableGroup>
      </ComposableMap>
    </div>
  );
}
