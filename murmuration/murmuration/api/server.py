"""FastAPI server: ticks the simulation, broadcasts state over WebSocket, serves UI."""
from __future__ import annotations
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from murmuration.protocol import MurmurationBus
from murmuration.data import ISOClient
from murmuration.data.transmission import TransmissionData
from murmuration.data.substations import SubstationsData
from murmuration.assets import DataCenter, Job, HomeAggregator, make_bay_area_vpp
from murmuration.orchestrator import GridAgent, ComputeAgent, Narrator
from murmuration.simulator import ScenarioManager
from murmuration.metrics import MetricsTracker
from murmuration.anomaly import AnomalyDetector
from murmuration.topology import TopologyGraph, default_us_graph, TopologyHealer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("murmuration.api")

UI_DIR = Path(__file__).resolve().parent.parent.parent / "ui"

ACTIVE_BAS = ("CAISO", "ERCOT", "PJM", "MISO", "NYISO", "ISO-NE", "SPP")
TICK_SEC = 3.0

# Geographic anchors for entities. Used by the globe UI for placement.
# Coordinates are each ISO's actual HQ.
BA_GEO = {
    "CAISO":  {"lat": 38.67, "lon": -121.18, "label": "CAISO",  "city": "Folsom, CA"},
    "ERCOT":  {"lat": 30.57, "lon":  -97.41, "label": "ERCOT",  "city": "Taylor, TX"},
    "PJM":    {"lat": 40.13, "lon":  -75.43, "label": "PJM",    "city": "Audubon, PA"},
    "MISO":   {"lat": 39.97, "lon":  -86.12, "label": "MISO",   "city": "Carmel, IN"},
    "NYISO":  {"lat": 42.66, "lon":  -73.69, "label": "NYISO",  "city": "Rensselaer, NY"},
    "ISO-NE": {"lat": 42.20, "lon":  -72.62, "label": "ISO-NE", "city": "Holyoke, MA"},
    "SPP":    {"lat": 34.79, "lon":  -92.42, "label": "SPP",    "city": "Little Rock, AR"},
}
ASSET_GEO = {
    # CAISO region — 3 AZs across Bay Area substations
    "DC-CA-1a": {"lat": 37.36, "lon": -122.04, "city": "Sunnyvale, CA",     "region": "us-west-1"},
    "DC-CA-1b": {"lat": 37.35, "lon": -121.96, "city": "Santa Clara, CA",   "region": "us-west-1"},
    "DC-CA-1c": {"lat": 37.30, "lon": -121.87, "city": "San Jose, CA",      "region": "us-west-1"},
    # ERCOT region — 3 AZs across Houston metro
    "DC-TX-1a": {"lat": 29.83, "lon":  -95.50, "city": "Houston-NW, TX",    "region": "us-central-1"},
    "DC-TX-1b": {"lat": 29.76, "lon":  -95.37, "city": "Houston-Central, TX","region": "us-central-1"},
    "DC-TX-1c": {"lat": 29.69, "lon":  -95.24, "city": "Houston-SE, TX",    "region": "us-central-1"},
    # PJM region — 3 AZs across Northern Virginia substations
    "DC-VA-1a": {"lat": 39.04, "lon":  -77.49, "city": "Ashburn, VA",       "region": "us-east-1"},
    "DC-VA-1b": {"lat": 38.95, "lon":  -77.45, "city": "Sterling, VA",      "region": "us-east-1"},
    "DC-VA-1c": {"lat": 38.83, "lon":  -77.44, "city": "Manassas, VA",      "region": "us-east-1"},
}

# Region anchors — used by UI to draw the "region container" outline around AZ siblings
REGION_GEO = {
    "us-west-1":    {"lat": 37.34, "lon": -121.97, "label": "us-west-1",    "ba": "CAISO"},
    "us-central-1": {"lat": 29.76, "lon":  -95.37, "label": "us-central-1", "ba": "ERCOT"},
    "us-east-1":    {"lat": 38.94, "lon":  -77.46, "label": "us-east-1",    "ba": "PJM"},
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_assets() -> list:
    """9 DCs (3 AZs × 3 regions, the #1 flagship) + 1 VPP of 100 homes (#2). Same protocol surface."""
    def jobs(prefix: str, training: int, batch: int, online: int, fine_tune: int = 1) -> list[Job]:
        out: list[Job] = []
        for i in range(training):
            out.append(Job(f"{prefix}-train-{i}", "training", 18.0, None))
        for i in range(fine_tune):
            out.append(Job(f"{prefix}-ft-{i}", "fine_tune", 8.0, None))
        for i in range(batch):
            out.append(Job(f"{prefix}-batch-{i}", "batch_infer", 6.0, None))
        for i in range(online):
            out.append(Job(f"{prefix}-serve-{i}", "online_serve", 8.0, None))
        return out

    # Per-AZ profile: ~85 MW nominal, ~22 MW serving floor. 3 AZs ≈ old monolithic DC.
    az_specs = [
        # CAISO region — us-west-1
        ("DC-CA-1a", "CAISO", "CAISO-SUBSTATION-NP15-A", "ca-1a", 85.0, 22.0,
         dict(training=2, fine_tune=1, batch=2, online=1), ["CAISO", "ERCOT", "PJM"]),
        ("DC-CA-1b", "CAISO", "CAISO-SUBSTATION-NP15-B", "ca-1b", 85.0, 22.0,
         dict(training=2, fine_tune=0, batch=1, online=2), ["CAISO", "ERCOT", "PJM"]),
        ("DC-CA-1c", "CAISO", "CAISO-SUBSTATION-NP15-C", "ca-1c", 85.0, 22.0,
         dict(training=1, fine_tune=1, batch=2, online=2), ["CAISO", "ERCOT", "PJM"]),
        # ERCOT region — us-central-1
        ("DC-TX-1a", "ERCOT", "ERCOT-HOUSTON-A", "tx-1a", 80.0, 20.0,
         dict(training=2, fine_tune=1, batch=1, online=1), ["ERCOT", "CAISO"]),
        ("DC-TX-1b", "ERCOT", "ERCOT-HOUSTON-B", "tx-1b", 80.0, 20.0,
         dict(training=2, fine_tune=0, batch=1, online=2), ["ERCOT", "CAISO"]),
        ("DC-TX-1c", "ERCOT", "ERCOT-HOUSTON-C", "tx-1c", 80.0, 20.0,
         dict(training=1, fine_tune=1, batch=1, online=1), ["ERCOT", "CAISO"]),
        # PJM region — us-east-1 (the DMV one — Loudoun, Sterling, Manassas)
        ("DC-VA-1a", "PJM", "PJM-DOM-LOUDOUN",  "va-1a", 90.0, 24.0,
         dict(training=2, fine_tune=1, batch=2, online=2), ["PJM", "CAISO"]),
        ("DC-VA-1b", "PJM", "PJM-DOM-STERLING", "va-1b", 90.0, 24.0,
         dict(training=2, fine_tune=1, batch=1, online=2), ["PJM", "CAISO"]),
        ("DC-VA-1c", "PJM", "PJM-DOM-MANASSAS", "va-1c", 90.0, 24.0,
         dict(training=1, fine_tune=0, batch=2, online=1), ["PJM", "CAISO"]),
    ]
    out = []
    for asset_id, ba, node_id, prefix, mw_max, floor, mix, eligible in az_specs:
        out.append(DataCenter(
            asset_id=asset_id,
            location_ba=ba,
            node_id=node_id,
            nominal_max_mw=mw_max,
            serving_floor_mw=floor,
            jobs=jobs(prefix, **mix),
            eligible_regions=eligible,
        ))
    out.append(make_bay_area_vpp(seed=7))
    return out


class AppState:
    def __init__(self):
        self.bus = MurmurationBus()
        self.iso = ISOClient()
        self.narrator = Narrator()
        self.assets = make_assets()
        # NB: metrics must subscribe BEFORE compute_agent so that DispatchAcks
        # produced re-entrantly by compute_agent find their pending DispatchRequest.
        self.metrics = MetricsTracker(self.bus)
        self.compute_agent = ComputeAgent(self.bus, self.narrator, self.assets)
        self.grid_agent = GridAgent(
            self.bus, self.iso, self.narrator, list(ACTIVE_BAS),
            stress_threshold=0.55,
        )
        self.scenarios = ScenarioManager(self.iso, bus=self.bus, assets=self.assets,
                                         grid_agent=self.grid_agent)
        # Hand region map to the router so it can distinguish intra/cross-region migrations
        self.compute_agent.router.attach_regions(
            {asset_id: geo.get("region") for asset_id, geo in ASSET_GEO.items()}
        )
        # Anomaly detector — always-on watchdog over the live grid stream
        self.anomaly = AnomalyDetector(self.bus)
        # Topology graph + self-healing healer
        self.topology: TopologyGraph = default_us_graph()
        self.healer = TopologyHealer(
            self.bus, self.topology,
            facility_to_node={
                a.asset_id: a.node_id for a in self.assets
                if isinstance(a, DataCenter)
            },
        )
        # HIFLD transmission lines — lazy-loaded on first /api/transmission hit
        self.transmission = TransmissionData()
        # HIFLD substations — lazy-loaded on first /api/substations hit
        self.substations = SubstationsData()
        self.ws_clients: set[WebSocket] = set()
        self.event_log: list[dict] = []
        self._loop_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        # tag every bus message into the WS broadcast stream
        self.bus.subscribe_all(self._on_bus_message)

    async def _on_bus_message(self, msg: BaseModel) -> None:
        env = {
            "type": "bus",
            "kind": getattr(msg, "msg_type", type(msg).__name__),
            "payload": json.loads(msg.model_dump_json()),
        }
        self.event_log.append(env)
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-1000:]
        await self._broadcast(env)

    async def _broadcast(self, payload: dict) -> None:
        if not self.ws_clients:
            return
        msg = json.dumps(payload, default=str)
        dead = []
        for ws in list(self.ws_clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.ws_clients.discard(ws)

    async def loop(self):
        log.info("simulation loop starting; tick=%.1fs; bas=%s", TICK_SEC, ACTIVE_BAS)
        while not self._stop.is_set():
            t = utcnow()
            try:
                self.scenarios.step(t)
                # publish envelopes first so the grid agent can see them
                await self.compute_agent.tick(t)
                await self.grid_agent.tick(t)
                # narrate any new dispatches
                # (handled async; narrator is rule-based or Claude)
                await self._broadcast({
                    "type": "tick",
                    "t": t.isoformat(),
                    "metrics": self.metrics.snapshot(),
                    "scenarios": [
                        {"name": s.name, "bas": s.bas, "kind": s.kind,
                         "started_at": s.started_at.isoformat() if s.started_at else None}
                        for s in self.scenarios.active()
                    ],
                    "claude_enabled": self.narrator.claude_enabled,
                    "contingency_response_ms": self.compute_agent.last_contingency_response_ms,
                })
            except Exception:
                log.exception("tick error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=TICK_SEC)
            except asyncio.TimeoutError:
                pass

    async def start(self):
        self._loop_task = asyncio.create_task(self.loop())

    async def stop(self):
        self._stop.set()
        if self._loop_task:
            await self._loop_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.svc = AppState()
    await app.state.svc.start()
    yield
    await app.state.svc.stop()


app = FastAPI(lifespan=lifespan, title="Murmuration")


@app.get("/")
async def index():
    return FileResponse(
        UI_DIR / "index.html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.get("/api/state")
async def state():
    s: AppState = app.state.svc
    assets = []
    t = utcnow()
    for a in s.assets:
        st = a.get_state(t)
        # geo: DC lookup, or fall back to asset's own .lat/.lon (HomeAggregator)
        geo = ASSET_GEO.get(st.asset_id, {})
        lat = geo.get("lat", getattr(a, "lat", None))
        lon = geo.get("lon", getattr(a, "lon", None))
        city = geo.get("city")
        region = geo.get("region")
        assets.append({
            "asset_id": st.asset_id,
            "asset_type": st.asset_type,
            "location_ba": st.location_ba,
            "node_id": st.node_id,
            "current_mw": st.current_mw,
            "nominal_max_mw": st.nominal_max_mw,
            "constraints": st.constraints,
            "lat": lat,
            "lon": lon,
            "city": city,
            "region": region,
        })
    grid = []
    for ba in ACTIVE_BAS:
        snap = s.iso.snapshot(ba)
        geo = BA_GEO.get(ba, {})
        grid.append({
            "ba": snap.ba,
            "load_mw": snap.load_mw,
            "headroom_mw": snap.headroom_mw,
            "lmp_dollars_mwh": snap.lmp_dollars_mwh,
            "carbon_g_kwh": snap.carbon_g_kwh,
            "stress_score": snap.stress_score,
            "notes": snap.notes,
            "lat": geo.get("lat"),
            "lon": geo.get("lon"),
            "city": geo.get("city"),
        })
    return {
        "assets": assets,
        "grid": grid,
        "metrics": s.metrics.snapshot(),
        "scenarios_available": s.scenarios.list_available(),
        "scenarios_active": [
            {"name": sc.name, "bas": sc.bas, "kind": sc.kind} for sc in s.scenarios.active()
        ],
        "claude_enabled": s.narrator.claude_enabled,
    }


@app.get("/api/substations")
async def substations(min_kv: float = 100.0, max_points: int = 25000):
    """HIFLD US substations (>= 100 kV by default).

    Query params:
      min_kv: minimum MAX_VOLT (kV) to include (default 100)
      max_points: cap rendered count (default 25000)
    """
    s: AppState = app.state.svc
    return s.substations.to_payload(min_voltage_kv=min_kv, max_points=max_points)


@app.get("/api/transmission")
async def transmission(min_rank: int = 2, max_lines: int = 12000):
    """HIFLD US transmission backbone (>= 220 kV by default).

    Query params:
      min_rank: 2=220kV+, 3=345kV+, 4=500kV+, 5=735kV+ (default 2)
      max_lines: cap rendered count (default 12000)
    """
    s: AppState = app.state.svc
    return s.transmission.to_payload(max_lines=max_lines, min_rank=min_rank)


@app.get("/api/topology")
async def topology():
    """Substations + lines for the planning UI."""
    s: AppState = app.state.svc
    g = s.topology
    return {
        "substations": [
            {"id": n.node_id, "lat": n.lat, "lon": n.lon, "ba": n.ba, "label": n.label}
            for n in g.substations.values()
        ],
        "lines": [
            {
                "edge": ln.edge_key(), "a": ln.a, "b": ln.b,
                "voltage_kv": ln.voltage_kv,
                "capacity_mw": ln.capacity_mw, "flow_mw": round(ln.flow_mw, 1),
                "utilization": round(ln.utilization(), 3),
                "failed": ln.failed,
            }
            for ln in g.lines
        ],
    }


@app.get("/api/bottlenecks")
async def bottlenecks(threshold: float = 0.75, top_n: int = 12):
    """Top-N most-loaded transmission lines + alternate paths around each."""
    s: AppState = app.state.svc
    rows = s.topology.bottlenecks(threshold=threshold, top_n=top_n)
    # for each bottleneck, compute up-to-3 alt paths around it (excluding the line)
    for r in rows:
        alt = s.topology.k_shortest_paths(r["from"], r["to"], k=3, exclude_edge=r["edge"])
        r["alternative_paths"] = alt
    return {"bottlenecks": rows, "threshold": threshold}


@app.get("/api/healer-events")
async def healer_events(limit: int = 10):
    s: AppState = app.state.svc
    return {"events": s.healer.recent_events(limit=limit)}


@app.get("/api/anomaly-status")
async def anomaly_status():
    s: AppState = app.state.svc
    return {"fire_count": s.anomaly.fire_count}


@app.get("/api/homes")
async def homes():
    """Per-home detail for VPP visualizations on the globe."""
    s: AppState = app.state.svc
    out = []
    for a in s.assets:
        if not isinstance(a, HomeAggregator):
            continue
        for h in a.homes:
            out.append({
                "home_id": h.home_id,
                "facility_id": a.asset_id,
                "lat": h.lat, "lon": h.lon,
                "soc": h.soc,
                "ev": h.ev_charging_kw > 0,
                "responding": h.discharging or h.paused_charging,
                "opted_in": h.opted_in,
                "discharging": h.discharging,
                "paused_charging": h.paused_charging,
            })
    return {"homes": out}


@app.post("/api/scenario/{name}")
async def trigger_scenario(name: str):
    s: AppState = app.state.svc
    sc = await s.scenarios.trigger(name, utcnow())
    if sc is None:
        return JSONResponse({"error": "unknown scenario"}, status_code=404)
    return {"triggered": sc.name, "bas": sc.bas, "kind": sc.kind}


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    s: AppState = app.state.svc
    s.ws_clients.add(ws)
    try:
        # send recent backlog
        for ev in s.event_log[-50:]:
            await ws.send_text(json.dumps(ev, default=str))
        while True:
            await ws.receive_text()    # keep-alive
    except WebSocketDisconnect:
        pass
    finally:
        s.ws_clients.discard(ws)


def main():
    import uvicorn
    port = int(os.getenv("PORT", "8765"))
    uvicorn.run(
        "murmuration.api.server:app",
        host="127.0.0.1", port=port, reload=False, log_level="info",
    )


if __name__ == "__main__":
    main()
