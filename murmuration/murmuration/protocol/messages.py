"""Murmuration Bus — the seven message types that constitute the protocol."""
from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

ISO = Literal["CAISO", "ERCOT", "PJM", "MISO", "NYISO", "ISO-NE", "SPP"]
WorkloadClass = Literal[
    "training", "batch_infer", "online_serve", "fine_tune", "embedding"
]
DispatchPriority = Literal["economic", "reliability", "emergency"]
DispatchAction = Literal["throttle", "shift", "discharge", "delay", "hold", "lean_in"]


class _Msg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    msg_type: str = Field(default="", description="set by subclasses")


class GridStateUpdate(_Msg):
    msg_type: Literal["grid_state_update"] = "grid_state_update"
    timestamp: datetime
    ba: ISO
    node_id: str
    lmp_dollars_mwh: float
    load_mw: float
    headroom_mw: float
    carbon_g_kwh: float
    frequency_hz: float | None = None
    stress_score: float = Field(ge=0.0, le=1.0)
    valid_until: datetime
    notes: str = ""


class GridForecast(_Msg):
    msg_type: Literal["grid_forecast"] = "grid_forecast"
    timestamp: datetime
    ba: ISO
    horizon_min: int
    interval_min: int
    lmp_forecast: list[float]
    load_forecast: list[float]
    carbon_forecast: list[float]
    confidence_band: list[float]
    valid_until: datetime


class DispatchRequest(_Msg):
    msg_type: Literal["dispatch_request"] = "dispatch_request"
    request_id: str
    timestamp: datetime
    ba: ISO
    facility_id: str
    needed_mw: float
    duration_min: int
    start_within_min: int
    compensation_per_mwh: float
    priority: DispatchPriority
    reason: str
    valid_until: datetime


class ContingencyAlert(_Msg):
    msg_type: Literal["contingency_alert"] = "contingency_alert"
    alert_id: str
    timestamp: datetime
    ba: ISO
    event_type: Literal["frequency_excursion", "line_trip", "ramp_event"]
    severity: float = Field(ge=0.0, le=1.0)
    affected_nodes: list[str]
    required_response_sec: int
    expected_duration_min: int


class FlexibilityBand(BaseModel):
    direction: Literal["decrease", "increase"]
    mw: float
    for_min: int
    workload_class: WorkloadClass
    cost_per_mwh: float
    constraint_notes: str = ""


class FlexibilityEnvelope(_Msg):
    msg_type: Literal["flexibility_envelope"] = "flexibility_envelope"
    facility_id: str
    timestamp: datetime
    ba: ISO
    node_id: str
    baseline_mw: float
    bands: list[FlexibilityBand]
    cannot_go_below_mw: float
    data_locality_constraints: list[str] = Field(default_factory=list)
    valid_until: datetime


class LoadForecast(_Msg):
    msg_type: Literal["load_forecast"] = "load_forecast"
    facility_id: str
    timestamp: datetime
    ba: ISO
    horizon_min: int
    interval_min: int
    expected_mw: list[float]
    confidence_band: list[float]
    firmness: Literal["firm", "soft", "tentative"]
    valid_until: datetime


class CounterOffer(BaseModel):
    """Optional alternative the compute side proposes when partially declining."""
    proposed_mw: float                  # negative for shed
    proposed_duration_min: int
    proposed_compensation_per_mwh: float | None = None
    reason: str


class DispatchAck(_Msg):
    msg_type: Literal["dispatch_ack"] = "dispatch_ack"
    request_id: str
    timestamp: datetime
    facility_id: str
    accepted_mw: float
    declined_mw: float
    decline_reason: str = ""
    effective_at: datetime
    expected_until: datetime
    actions_taken: list[str] = Field(default_factory=list)
    counter_offer: CounterOffer | None = None


class TelemetryFrame(_Msg):
    msg_type: Literal["telemetry_frame"] = "telemetry_frame"
    facility_id: str
    timestamp: datetime
    actual_mw: float
    power_factor: float = 0.98
    queue_depth: int = 0
    active_dispatches: list[str] = Field(default_factory=list)


class WorkloadMigration(_Msg):
    """Compute side notifies the bus that it migrated work between facilities.

    Used by the tiered router. Tier 1 = within same region (sub-ms latency,
    no data migration). Tier 2 = cross-region (10–100 ms, data staging cost).
    """
    msg_type: Literal["workload_migration"] = "workload_migration"
    timestamp: datetime
    job_id: str
    src_facility: str
    dest_facility: str
    tier: Literal["intra_region", "cross_region"]
    workload_class: WorkloadClass
    mw: float
    latency_ms_added: float
    reason: str


class TopologyReconfigure(_Msg):
    """Self-healing: published when a transmission edge fails and the topology
    healer has computed a mitigation plan. Compute side can use this to know
    which facilities need workload moved off."""
    msg_type: Literal["topology_reconfigure"] = "topology_reconfigure"
    timestamp: datetime
    tripped_edge: str                 # "PJM-DOM-LOUDOUN--PJM-DOM-STERLING"
    affected_facilities: list[str]    # facility_ids that lose feed
    alternative_paths: list[list[str]]  # node sequences as alt routes
    mitigation: str                   # human-readable rationale


def expires_at(t: datetime, minutes: int) -> datetime:
    return t + timedelta(minutes=minutes)
