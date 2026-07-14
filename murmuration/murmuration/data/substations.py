"""HIFLD US Electric Substations loader.

Reads the Substations.csv (~80K rows), filters to in-service substations at
or above a configurable voltage threshold (default 100 kV — drops local
distribution noise), caches a compact in-memory payload.

Source: HIFLD (Homeland Infrastructure Foundation-Level Data) — public.
"""
from __future__ import annotations
from dataclasses import dataclass
import csv
import logging
from pathlib import Path
import time

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent


@dataclass
class Substation:
    sub_id: str
    name: str
    lat: float
    lon: float
    state: str
    city: str
    max_volt_kv: float
    lines: int


class SubstationsData:
    def __init__(self, csv_path: Path | None = None, min_voltage_kv: float = 100.0):
        self.csv_path = csv_path or self._find_csv()
        self.min_voltage_kv = min_voltage_kv
        self.points: list[Substation] = []
        self.loaded = False

    @staticmethod
    def _find_csv() -> Path | None:
        p = DATA_DIR / "Substations.csv"
        return p if p.exists() else None

    def load(self) -> None:
        if self.loaded:
            return
        if not self.csv_path or not self.csv_path.exists():
            log.warning("Substations CSV not found in %s", DATA_DIR)
            self.loaded = True
            return
        log.info("loading HIFLD Substations CSV: %s", self.csv_path.name)
        t0 = time.time()
        rows_read = 0
        kept = 0
        with open(self.csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows_read += 1
                status = (row.get("STATUS") or "").upper()
                if "IN SERVICE" not in status:
                    continue
                try:
                    lat = float(row.get("LATITUDE") or 0)
                    lon = float(row.get("LONGITUDE") or 0)
                except ValueError:
                    continue
                if not lat or not lon:
                    continue
                # MAX_VOLT can be -999999 for unknown; treat as 0 then filter
                try:
                    mv = float(row.get("MAX_VOLT") or 0)
                except ValueError:
                    mv = 0.0
                if mv <= 0 or mv < self.min_voltage_kv:
                    continue
                try:
                    nlines = int(row.get("LINES") or 0)
                except ValueError:
                    nlines = 0
                self.points.append(Substation(
                    sub_id=str(row.get("ID") or rows_read),
                    name=row.get("NAME") or "",
                    lat=lat, lon=lon,
                    state=row.get("STATE") or "",
                    city=row.get("CITY") or "",
                    max_volt_kv=mv,
                    lines=nlines,
                ))
                kept += 1
        # sort by voltage so highest-voltage rows render last (on top)
        self.points.sort(key=lambda p: p.max_volt_kv)
        t1 = time.time()
        log.info("HIFLD substations ready: %d / %d in service ≥%g kV (%.1fs)",
                 kept, rows_read, self.min_voltage_kv, t1 - t0)
        self.loaded = True

    def to_payload(self, min_voltage_kv: float | None = None,
                   max_points: int = 25000) -> dict:
        if not self.loaded:
            self.load()
        cutoff = self.min_voltage_kv if min_voltage_kv is None else min_voltage_kv
        pts = [p for p in self.points if p.max_volt_kv >= cutoff]
        if len(pts) > max_points:
            # keep highest-voltage subset
            pts = sorted(pts, key=lambda p: -p.max_volt_kv)[:max_points]
        return {
            "count": len(pts),
            "subs": [
                {
                    "id": p.sub_id, "name": p.name,
                    "lat": p.lat, "lon": p.lon,
                    "state": p.state, "city": p.city,
                    "kv": p.max_volt_kv, "lines": p.lines,
                }
                for p in pts
            ],
        }
