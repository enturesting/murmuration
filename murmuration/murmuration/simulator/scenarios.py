"""Scenario triggers — narrative grid events that drive dispatch.

Each scenario can override LMP, carbon intensity, and/or stress score on one
or more BAs. Surplus scenarios use very low LMP + low carbon to invite the
compute side to lean in. Cascade scenarios hit multiple BAs at once.
Contingency scenarios additionally publish a ContingencyAlert on the bus.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from murmuration.data import ISOClient
from murmuration.protocol import ContingencyAlert, MurmurationBus

log = logging.getLogger(__name__)

ScenarioKind = str   # "stress" | "surplus" | "cascade" | "contingency" | "carbon"


@dataclass
class Scenario:
    name: str
    bas: list[str]
    kind: ScenarioKind = "stress"
    lmp_overrides: dict[str, float] = field(default_factory=dict)
    carbon_overrides: dict[str, float] = field(default_factory=dict)
    stress_overrides: dict[str, float] = field(default_factory=dict)
    unavailable_assets: list[str] = field(default_factory=list)   # AZs to mark down
    duration_min: int = 12
    description: str = ""
    icon: str = "alert"
    started_at: datetime | None = None


SCENARIOS: list[Scenario] = [
    Scenario(
        name="Texas heat wave",
        bas=["ERCOT"],
        kind="stress",
        lmp_overrides={"ERCOT": 410.0},
        carbon_overrides={"ERCOT": 580.0},
        duration_min=15,
        description="ERCOT-Houston-Hub LMP spikes to $410/MWh; system load forecasted +18% over next 2h.",
        icon="flame",
    ),
    Scenario(
        name="CAISO evening ramp",
        bas=["CAISO"],
        kind="stress",
        lmp_overrides={"CAISO": 195.0},
        carbon_overrides={"CAISO": 360.0},
        stress_overrides={"CAISO": 0.7},
        duration_min=10,
        description="CAISO net load ramping +13 MW/min after sunset; gas peakers ramping.",
        icon="ramp",
    ),
    Scenario(
        name="PJM-DOM congestion",
        bas=["PJM"],
        kind="stress",
        lmp_overrides={"PJM": 240.0},
        duration_min=12,
        description="PJM-DOM zone constrained; 500kV transmission line near limits.",
        icon="alert",
    ),
    Scenario(
        name="CAISO surplus solar",
        bas=["CAISO"],
        kind="surplus",
        lmp_overrides={"CAISO": 4.0},
        carbon_overrides={"CAISO": 18.0},
        stress_overrides={"CAISO": 0.0},
        duration_min=20,
        description="Midday solar surplus; ISO would otherwise curtail. Lean-in opportunity for any flexible compute.",
        icon="sun",
    ),
    Scenario(
        name="Polar vortex cascade",
        bas=["ERCOT", "PJM"],
        kind="cascade",
        lmp_overrides={"ERCOT": 320.0, "PJM": 285.0},
        carbon_overrides={"ERCOT": 620.0, "PJM": 540.0},
        duration_min=18,
        description="Arctic blast across central US; gas + heating load surge across multiple ISOs.",
        icon="snow",
    ),
    Scenario(
        name="PJM line trip · contingency",
        bas=["PJM"],
        kind="contingency",
        lmp_overrides={"PJM": 380.0},
        stress_overrides={"PJM": 0.92},
        duration_min=4,
        description="500kV line trip in PJM-DOM. Frequency 59.92 Hz; sub-second response required.",
        icon="bolt",
    ),
    Scenario(
        name="Carbon arbitrage · CAISO clean / PJM dirty",
        bas=["CAISO", "PJM"],
        kind="carbon",
        carbon_overrides={"CAISO": 22.0, "PJM": 540.0},
        lmp_overrides={"CAISO": 12.0, "PJM": 95.0},
        stress_overrides={"CAISO": 0.0, "PJM": 0.4},
        duration_min=15,
        description="CAISO at 22 g/kWh (solar-rich), PJM at 540 g/kWh (coal-fired). Voluntary workload migration.",
        icon="leaf",
    ),
    Scenario(
        name="ERCOT solar eclipse",
        bas=["ERCOT"],
        kind="stress",
        lmp_overrides={"ERCOT": 165.0},
        carbon_overrides={"ERCOT": 510.0},
        stress_overrides={"ERCOT": 0.62},
        duration_min=8,
        description="Annular eclipse path; ~6 GW of solar generation drops in 12 minutes.",
        icon="eclipse",
    ),
    Scenario(
        name="PJM Loudoun substation overload",
        bas=["PJM"],
        kind="stress",
        lmp_overrides={"PJM": 220.0},
        stress_overrides={"PJM": 0.58},
        unavailable_assets=["DC-VA-1a"],   # Loudoun AZ goes dark
        duration_min=8,
        description="Loudoun substation supplying DC-VA-1a saturates; that AZ drops out. Sibling AZs (DC-VA-1b Sterling, DC-VA-1c Manassas) absorb the load — intra-region failover, no SLA hit.",
        icon="bolt",
    ),
]

REGISTRY = {s.name: s for s in SCENARIOS}


class ScenarioManager:
    def __init__(self, iso: ISOClient, bus: MurmurationBus | None = None,
                 assets: list | None = None, grid_agent=None):
        self.iso = iso
        self.bus = bus
        self.assets = assets or []     # so we can flip per-AZ unavailability
        self.grid_agent = grid_agent   # so trigger() can clear dispatch cooldown
        self._active: dict[str, Scenario] = {}    # keyed by scenario name

    def _set_asset_unavailable(self, asset_id: str, value: bool) -> None:
        for a in self.assets:
            if getattr(a, "asset_id", None) == asset_id and hasattr(a, "unavailable"):
                a.unavailable = value
                log.info("asset %s unavailable=%s", asset_id, value)
                return

    def list_available(self) -> list[dict]:
        return [
            {
                "name": s.name,
                "bas": s.bas,
                "kind": s.kind,
                "description": s.description,
                "icon": s.icon,
                "duration_min": s.duration_min,
            }
            for s in SCENARIOS
        ]

    async def trigger(self, name: str, t: datetime) -> Scenario | None:
        template = REGISTRY.get(name)
        if template is None:
            return None
        scenario = Scenario(**{**template.__dict__, "started_at": t})
        self._active[scenario.name] = scenario
        for ba, lmp in scenario.lmp_overrides.items():
            self.iso.set_lmp_override(ba, lmp)
        for ba, c in scenario.carbon_overrides.items():
            self.iso.set_carbon_override(ba, c)
        for ba, s in scenario.stress_overrides.items():
            self.iso.set_stress_override(ba, s)
        for asset_id in scenario.unavailable_assets:
            self._set_asset_unavailable(asset_id, True)
        # Clear per-BA dispatch cooldown so the first dispatch fires immediately
        # rather than waiting on a recent prior scenario's debounce window.
        if self.grid_agent is not None:
            for ba in scenario.bas:
                self.grid_agent._last_dispatch_at.pop(ba, None)
        log.info("scenario triggered: %s on %s", scenario.name, scenario.bas)

        # Contingency scenarios additionally publish a sub-second alert.
        if scenario.kind == "contingency" and self.bus is not None:
            # canonical topology nodes for each BA — keep healer + scenario in sync
            topology_node_for_ba = {
                "PJM": "PJM-DOM-LOUDOUN",
                "ERCOT": "ERCOT-HOUSTON-HUB",
                "CAISO": "CAISO-NP15-HUB",
            }
            for ba in scenario.bas:
                alert = ContingencyAlert(
                    alert_id=f"alert-{uuid.uuid4().hex[:8]}",
                    timestamp=t,
                    ba=ba,
                    event_type="line_trip",
                    severity=0.9,
                    affected_nodes=[topology_node_for_ba.get(ba, f"{ba}-MAIN")],
                    required_response_sec=2,
                    expected_duration_min=scenario.duration_min,
                )
                await self.bus.publish(alert)
        return scenario

    def step(self, t: datetime) -> list[str]:
        expired = []
        for name, sc in list(self._active.items()):
            if sc.started_at and t - sc.started_at >= timedelta(minutes=sc.duration_min):
                for ba in sc.lmp_overrides:
                    self.iso.set_lmp_override(ba, None)
                for ba in sc.carbon_overrides:
                    self.iso.set_carbon_override(ba, None)
                for ba in sc.stress_overrides:
                    self.iso.set_stress_override(ba, None)
                for asset_id in sc.unavailable_assets:
                    self._set_asset_unavailable(asset_id, False)
                del self._active[name]
                expired.append(name)
                log.info("scenario expired: %s", name)
        return expired

    def active(self) -> list[Scenario]:
        return list(self._active.values())
