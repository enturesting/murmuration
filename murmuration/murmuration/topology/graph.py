"""Synthetic transmission-grid topology used for infrastructure planning + healing.

Nodes are substations (with lat/lon and which BA they belong to). Edges are
transmission lines with a capacity and a current_flow. The graph supports:

  - bottleneck listing (lines near or above their capacity)
  - K-shortest alternate paths between two nodes excluding a given edge
  - mark/unmark edges as failed (for self-healing)

Topology hand-rolled to be plausible: NoVA / Loudoun / Sterling / Manassas /
Audubon (PJM); Sunnyvale / Santa Clara / San Jose / NP15 hub (CAISO);
Houston-NW / Central / SE / Hub (ERCOT).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterable
import heapq


@dataclass
class Substation:
    node_id: str
    lat: float
    lon: float
    ba: str
    label: str = ""


@dataclass
class TransmissionLine:
    a: str
    b: str
    capacity_mw: float
    flow_mw: float = 0.0
    failed: bool = False
    voltage_kv: int = 230

    def utilization(self) -> float:
        return abs(self.flow_mw) / self.capacity_mw if self.capacity_mw else 0.0

    def edge_key(self) -> str:
        return f"{self.a}--{self.b}"


@dataclass
class TopologyGraph:
    substations: dict[str, Substation] = field(default_factory=dict)
    lines: list[TransmissionLine] = field(default_factory=list)

    def add_substation(self, s: Substation) -> None:
        self.substations[s.node_id] = s

    def add_line(self, a: str, b: str, capacity_mw: float, flow_mw: float = 0.0,
                 voltage_kv: int = 230) -> None:
        self.lines.append(TransmissionLine(a=a, b=b, capacity_mw=capacity_mw,
                                           flow_mw=flow_mw, voltage_kv=voltage_kv))

    def neighbors(self, node_id: str) -> list[tuple[str, TransmissionLine]]:
        out = []
        for ln in self.lines:
            if ln.failed: continue
            if ln.a == node_id: out.append((ln.b, ln))
            elif ln.b == node_id: out.append((ln.a, ln))
        return out

    def bottlenecks(self, threshold: float = 0.75, top_n: int = 12) -> list[dict]:
        ranked = sorted(self.lines, key=lambda l: -l.utilization())
        out = []
        for ln in ranked:
            u = ln.utilization()
            if u < threshold and len(out) >= top_n: break
            out.append({
                "edge": ln.edge_key(),
                "from": ln.a, "to": ln.b,
                "voltage_kv": ln.voltage_kv,
                "capacity_mw": ln.capacity_mw,
                "flow_mw": round(ln.flow_mw, 1),
                "utilization": round(u, 3),
                "ba": self.substations[ln.a].ba if ln.a in self.substations else "",
                "failed": ln.failed,
                "severity": (
                    "critical" if u >= 0.95
                    else "warn" if u >= 0.85
                    else "watch" if u >= 0.75
                    else "nominal"
                ),
            })
            if len(out) >= top_n: break
        return out

    def shortest_path(self, src: str, dst: str, exclude_edge: str | None = None) -> list[str] | None:
        """Dijkstra by inverse-of-headroom so paths prefer slack lines."""
        if src not in self.substations or dst not in self.substations:
            return None
        dist: dict[str, float] = {src: 0.0}
        prev: dict[str, str] = {}
        pq: list[tuple[float, str]] = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == dst:
                # reconstruct path
                path = [u]
                while u in prev:
                    u = prev[u]
                    path.append(u)
                return list(reversed(path))
            if d > dist.get(u, float("inf")):
                continue
            for v, ln in self.neighbors(u):
                if exclude_edge and ln.edge_key() == exclude_edge:
                    continue
                # cost = 1 / (1 - utilization) so saturated lines cost a lot
                cost = 1.0 / max(0.05, 1.0 - ln.utilization())
                alt = d + cost
                if alt < dist.get(v, float("inf")):
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(pq, (alt, v))
        return None

    def k_shortest_paths(self, src: str, dst: str, k: int = 3,
                         exclude_edge: str | None = None) -> list[list[str]]:
        """Yen-lite: greedily exclude one edge of each found path to find next."""
        paths: list[list[str]] = []
        excluded: set[str] = set()
        if exclude_edge: excluded.add(exclude_edge)

        def find(excl: set[str]) -> list[str] | None:
            # crude: exclude all edges in 'excl' for this Dijkstra run
            saved = []
            for ln in self.lines:
                if ln.edge_key() in excl and not ln.failed:
                    saved.append((ln, ln.failed))
                    ln.failed = True
            try:
                return self.shortest_path(src, dst)
            finally:
                for ln, was in saved:
                    ln.failed = was

        first = find(excluded)
        if first is None: return []
        paths.append(first)
        for _ in range(k - 1):
            # exclude one edge from the most recent path that isn't already excluded
            new_excl = set(excluded)
            edges_in_last = set()
            last = paths[-1]
            for i in range(len(last) - 1):
                a, b = last[i], last[i + 1]
                for ln in self.lines:
                    if {ln.a, ln.b} == {a, b}:
                        edges_in_last.add(ln.edge_key())
            # add one new edge to exclusion set; if all already excluded, stop
            added = False
            for e in edges_in_last:
                if e not in new_excl:
                    new_excl.add(e); added = True; break
            if not added: break
            nxt = find(new_excl)
            if nxt and nxt not in paths:
                paths.append(nxt)
                excluded = new_excl
            else:
                break
        return paths

    def fail_edge(self, edge_key: str) -> bool:
        for ln in self.lines:
            if ln.edge_key() == edge_key:
                ln.failed = True
                return True
        return False

    def heal_edge(self, edge_key: str) -> bool:
        for ln in self.lines:
            if ln.edge_key() == edge_key:
                ln.failed = False
                return True
        return False

    def line_for_node(self, node_id: str) -> list[TransmissionLine]:
        return [ln for ln in self.lines if ln.a == node_id or ln.b == node_id]


def default_us_graph() -> TopologyGraph:
    """Hand-rolled topology covering the three flagship regions plus regional hubs."""
    g = TopologyGraph()
    # PJM (NoVA) ----------
    g.add_substation(Substation("PJM-DOM-LOUDOUN",  39.04, -77.49, "PJM", "Loudoun 500kV"))
    g.add_substation(Substation("PJM-DOM-STERLING", 38.95, -77.45, "PJM", "Sterling 230kV"))
    g.add_substation(Substation("PJM-DOM-MANASSAS", 38.83, -77.44, "PJM", "Manassas 230kV"))
    g.add_substation(Substation("PJM-DOM-HUB",      39.10, -77.35, "PJM", "DOM Zone Hub"))
    g.add_substation(Substation("PJM-AUDUBON",      40.13, -75.43, "PJM", "Audubon HQ"))
    g.add_line("PJM-DOM-LOUDOUN",  "PJM-DOM-HUB",      capacity_mw=2200, flow_mw=2050, voltage_kv=500)
    g.add_line("PJM-DOM-STERLING", "PJM-DOM-HUB",      capacity_mw=1500, flow_mw=900,  voltage_kv=230)
    g.add_line("PJM-DOM-MANASSAS", "PJM-DOM-HUB",      capacity_mw=1500, flow_mw=620,  voltage_kv=230)
    g.add_line("PJM-DOM-LOUDOUN",  "PJM-DOM-STERLING", capacity_mw=900,  flow_mw=540,  voltage_kv=230)
    g.add_line("PJM-DOM-STERLING", "PJM-DOM-MANASSAS", capacity_mw=900,  flow_mw=380,  voltage_kv=230)
    g.add_line("PJM-DOM-HUB",      "PJM-AUDUBON",      capacity_mw=4000, flow_mw=2800, voltage_kv=500)

    # CAISO (Bay Area) ----------
    g.add_substation(Substation("CAISO-NP15-A", 37.36, -122.04, "CAISO", "Sunnyvale Sub"))
    g.add_substation(Substation("CAISO-NP15-B", 37.35, -121.96, "CAISO", "Santa Clara Sub"))
    g.add_substation(Substation("CAISO-NP15-C", 37.30, -121.87, "CAISO", "San Jose Sub"))
    g.add_substation(Substation("CAISO-NP15-HUB", 37.34, -121.97, "CAISO", "NP15 Hub"))
    g.add_substation(Substation("CAISO-FOLSOM",   38.67, -121.18, "CAISO", "Folsom HQ"))
    g.add_line("CAISO-NP15-A",  "CAISO-NP15-HUB",  capacity_mw=1200, flow_mw=600, voltage_kv=230)
    g.add_line("CAISO-NP15-B",  "CAISO-NP15-HUB",  capacity_mw=1200, flow_mw=540, voltage_kv=230)
    g.add_line("CAISO-NP15-C",  "CAISO-NP15-HUB",  capacity_mw=1200, flow_mw=480, voltage_kv=230)
    g.add_line("CAISO-NP15-A",  "CAISO-NP15-B",    capacity_mw=600,  flow_mw=240, voltage_kv=115)
    g.add_line("CAISO-NP15-B",  "CAISO-NP15-C",    capacity_mw=600,  flow_mw=210, voltage_kv=115)
    g.add_line("CAISO-NP15-HUB","CAISO-FOLSOM",    capacity_mw=3500, flow_mw=2050, voltage_kv=500)

    # ERCOT (Houston) ----------
    g.add_substation(Substation("ERCOT-HOUSTON-A", 29.83, -95.50, "ERCOT", "Houston-NW Sub"))
    g.add_substation(Substation("ERCOT-HOUSTON-B", 29.76, -95.37, "ERCOT", "Houston-Central Sub"))
    g.add_substation(Substation("ERCOT-HOUSTON-C", 29.69, -95.24, "ERCOT", "Houston-SE Sub"))
    g.add_substation(Substation("ERCOT-HOUSTON-HUB", 29.76, -95.37, "ERCOT", "Houston Hub"))
    g.add_substation(Substation("ERCOT-TAYLOR",     30.57, -97.41, "ERCOT", "Taylor HQ"))
    g.add_line("ERCOT-HOUSTON-A",   "ERCOT-HOUSTON-HUB", capacity_mw=1100, flow_mw=720, voltage_kv=230)
    g.add_line("ERCOT-HOUSTON-B",   "ERCOT-HOUSTON-HUB", capacity_mw=1100, flow_mw=560, voltage_kv=230)
    g.add_line("ERCOT-HOUSTON-C",   "ERCOT-HOUSTON-HUB", capacity_mw=1100, flow_mw=420, voltage_kv=230)
    g.add_line("ERCOT-HOUSTON-A",   "ERCOT-HOUSTON-B",   capacity_mw=600,  flow_mw=200, voltage_kv=138)
    g.add_line("ERCOT-HOUSTON-B",   "ERCOT-HOUSTON-C",   capacity_mw=600,  flow_mw=170, voltage_kv=138)
    g.add_line("ERCOT-HOUSTON-HUB", "ERCOT-TAYLOR",      capacity_mw=3200, flow_mw=1900,voltage_kv=345)
    return g
