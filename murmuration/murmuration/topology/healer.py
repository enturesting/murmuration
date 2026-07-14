"""Self-healing — runs contingency analysis on ContingencyAlert events.

When a contingency arrives (line trip, substation failure), the healer:
  1. Identifies which transmission edge is affected (via the alert's nodes).
  2. Marks the edge as failed in the topology graph.
  3. Computes K shortest alternate paths around it.
  4. Identifies which assets are downstream of the failed edge.
  5. Publishes a TopologyReconfigure on the bus so compute side can react.
"""
from __future__ import annotations
import logging
from datetime import datetime

from murmuration.protocol import (
    ContingencyAlert, TopologyReconfigure, MurmurationBus,
)
from murmuration.topology.graph import TopologyGraph

log = logging.getLogger(__name__)


class TopologyHealer:
    def __init__(self, bus: MurmurationBus, graph: TopologyGraph,
                 facility_to_node: dict[str, str]):
        self.bus = bus
        self.graph = graph
        self.facility_to_node = facility_to_node    # asset_id -> substation node_id
        self.events: list[dict] = []
        bus.subscribe(ContingencyAlert, self._on_contingency)

    async def _on_contingency(self, alert: ContingencyAlert) -> None:
        """Determine the affected edge (heuristic: pick the most stressed line
        adjacent to alert.affected_nodes, fail it, plan alt paths)."""
        if alert.event_type != "line_trip" and alert.event_type != "ramp_event":
            return
        candidate_lines = []
        for node in alert.affected_nodes:
            for ln in self.graph.line_for_node(node):
                if ln.failed: continue
                candidate_lines.append(ln)
        # Fallback: if no node-level match, fail the most-stressed line in the BA
        if not candidate_lines:
            for ln in self.graph.lines:
                if ln.failed: continue
                a_sub = self.graph.substations.get(ln.a)
                if a_sub and a_sub.ba == alert.ba:
                    candidate_lines.append(ln)
        if not candidate_lines:
            return
        # pick the most stressed line
        candidate_lines.sort(key=lambda l: -l.utilization())
        edge = candidate_lines[0]
        self.graph.fail_edge(edge.edge_key())
        log.warning("HEALER: edge failed %s (was %.0f%% util)",
                    edge.edge_key(), edge.utilization() * 100)

        # identify affected facilities — those routed through endpoints of failed edge
        affected_facilities = []
        for fid, node in self.facility_to_node.items():
            if node == edge.a or node == edge.b:
                affected_facilities.append(fid)

        # alternate paths around the failed edge from edge.a to edge.b (if any)
        alt_paths = self.graph.k_shortest_paths(edge.a, edge.b, k=3,
                                                exclude_edge=edge.edge_key())
        mitigation = (
            f"line {edge.edge_key()} tripped (was {edge.utilization()*100:.0f}% loaded). "
            f"Computed {len(alt_paths)} alternate paths. "
            f"Affected facilities: {len(affected_facilities)}."
        )
        msg = TopologyReconfigure(
            timestamp=datetime.now(alert.timestamp.tzinfo),
            tripped_edge=edge.edge_key(),
            affected_facilities=affected_facilities,
            alternative_paths=alt_paths,
            mitigation=mitigation,
        )
        self.events.append({
            "edge": edge.edge_key(),
            "affected": affected_facilities,
            "alt_paths": alt_paths,
            "mitigation": mitigation,
            "at": datetime.now(alert.timestamp.tzinfo).isoformat(),
        })
        await self.bus.publish(msg)

    def recent_events(self, limit: int = 10) -> list[dict]:
        return self.events[-limit:]
