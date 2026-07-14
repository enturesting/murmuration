"""FlexibleAsset — the modularity seam between #1 (DCs) and #2 (homes/EVs)."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from murmuration.protocol import (
    FlexibilityEnvelope, DispatchRequest, DispatchAck, TelemetryFrame,
)


@dataclass
class Job:
    job_id: str
    workload_class: str        # WorkloadClass literal
    mw: float
    deadline: datetime | None
    paused: bool = False


@dataclass
class AssetState:
    asset_id: str
    asset_type: str
    location_ba: str
    node_id: str
    current_mw: float
    nominal_max_mw: float
    constraints: dict = field(default_factory=dict)


class FlexibleAsset(ABC):
    asset_id: str
    asset_type: str
    location_ba: str
    node_id: str

    @abstractmethod
    def get_state(self, t: datetime) -> AssetState:
        ...

    @abstractmethod
    def get_envelope(self, t: datetime, horizon_min: int) -> FlexibilityEnvelope:
        ...

    @abstractmethod
    def dispatch(self, req: DispatchRequest, t: datetime) -> DispatchAck:
        ...

    @abstractmethod
    def telemetry(self, t: datetime) -> TelemetryFrame:
        ...
