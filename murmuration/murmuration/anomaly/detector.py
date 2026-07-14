"""Always-on anomaly detector subscribed to GridStateUpdate.

Maintains rolling-window statistics per BA and auto-fires ContingencyAlert
messages when an observable crosses a z-score threshold. Lets the protocol
respond to *unplanned* events, not just scenario triggers.
"""
from __future__ import annotations
from collections import deque
from datetime import datetime
import logging
import math
import uuid

from murmuration.protocol import (
    GridStateUpdate, ContingencyAlert, MurmurationBus,
)

log = logging.getLogger(__name__)


class _RollingZ:
    """Tiny rolling window with online mean/std for z-score thresholding."""
    def __init__(self, n: int = 60):
        self.n = n
        self.values: deque[float] = deque(maxlen=n)

    def push(self, v: float) -> None:
        self.values.append(v)

    def z(self, v: float) -> float:
        if len(self.values) < 8:
            return 0.0
        m = sum(self.values) / len(self.values)
        var = sum((x - m) ** 2 for x in self.values) / len(self.values)
        sd = math.sqrt(var)
        if sd < 1e-6:
            return 0.0
        return (v - m) / sd


# threshold for an observable to count as anomalous
Z_THRESH = 4.0
# minimum interval between two anomaly alerts on the same BA (seconds)
COOLDOWN_SEC = 30.0


class AnomalyDetector:
    def __init__(self, bus: MurmurationBus):
        self.bus = bus
        self._lmp: dict[str, _RollingZ] = {}
        self._load: dict[str, _RollingZ] = {}
        self._carbon: dict[str, _RollingZ] = {}
        self._last_fired_at: dict[str, float] = {}
        self._fire_count = 0
        bus.subscribe(GridStateUpdate, self._on_grid_state)

    @property
    def fire_count(self) -> int:
        return self._fire_count

    async def _on_grid_state(self, m: GridStateUpdate) -> None:
        ba = m.ba
        zlmp = self._lmp.setdefault(ba, _RollingZ()).z(m.lmp_dollars_mwh)
        zload = self._load.setdefault(ba, _RollingZ()).z(m.load_mw)
        zci = self._carbon.setdefault(ba, _RollingZ()).z(m.carbon_g_kwh)

        anomaly_kind: str | None = None
        details = ""
        if abs(zlmp) >= Z_THRESH:
            anomaly_kind = "ramp_event"
            details = f"LMP z={zlmp:+.1f} ({m.lmp_dollars_mwh:.0f} $/MWh)"
        elif abs(zload) >= Z_THRESH:
            anomaly_kind = "ramp_event"
            details = f"load z={zload:+.1f} ({m.load_mw:,.0f} MW)"
        elif abs(zci) >= Z_THRESH * 0.8:
            anomaly_kind = "ramp_event"
            details = f"carbon z={zci:+.1f} ({m.carbon_g_kwh:.0f} g/kWh)"

        # ingest after threshold check so the spiking sample doesn't immediately
        # widen its own baseline
        self._lmp[ba].push(m.lmp_dollars_mwh)
        self._load[ba].push(m.load_mw)
        self._carbon[ba].push(m.carbon_g_kwh)

        if anomaly_kind is None:
            return
        # cooldown
        import time
        now = time.monotonic()
        last = self._last_fired_at.get(ba, 0)
        if now - last < COOLDOWN_SEC:
            return
        self._last_fired_at[ba] = now
        self._fire_count += 1

        alert = ContingencyAlert(
            alert_id=f"auto-{uuid.uuid4().hex[:8]}",
            timestamp=m.timestamp,
            ba=ba,
            event_type=anomaly_kind,
            severity=min(1.0, max(abs(zlmp), abs(zload), abs(zci)) / 6.0),
            affected_nodes=[m.node_id],
            required_response_sec=5,
            expected_duration_min=8,
        )
        log.warning("ANOMALY auto-detected on %s: %s", ba, details)
        await self.bus.publish(alert)
