"""HIFLD US Electric Power Transmission Lines loader.

Loads the 153 MB GeoJSON once at startup, filters to the backbone subset
(>= some voltage threshold), and decimates each line's geometry to keep the
payload web-renderable. Result is cached in memory; downstream API serves
the compact JSON.

Source: HIFLD (Homeland Infrastructure Foundation-Level Data) — public.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import json
import logging
from pathlib import Path
import os
import time

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent

# voltage class -> rendering color (RGB 0-255) and stroke width hint
VOLTAGE_STYLE = {
    "DC":             {"color": [196, 107, 255], "stroke": 1.6, "rank": 6},  # HVDC
    "735 AND ABOVE":  {"color": [255, 158, 64],  "stroke": 1.7, "rank": 5},
    "500":            {"color": [255, 87, 87],   "stroke": 1.4, "rank": 4},
    "345":            {"color": [255, 217, 61],  "stroke": 1.1, "rank": 3},
    "220-287":        {"color": [92, 255, 199],  "stroke": 0.9, "rank": 2},
    "100-161":        {"color": [120, 180, 220], "stroke": 0.55,"rank": 1},
}
DEFAULT_STYLE = {"color": [80, 100, 150], "stroke": 0.4, "rank": 0}


def _decimate(coords: list[list[float]], max_pts: int) -> list[list[float]]:
    """Reduce a polyline to at most max_pts vertices, preserving endpoints."""
    if len(coords) <= max_pts:
        return coords
    if max_pts < 2:
        return [coords[0], coords[-1]]
    step = (len(coords) - 1) / (max_pts - 1)
    return [coords[min(int(round(i * step)), len(coords) - 1)] for i in range(max_pts)]


@dataclass
class TransmissionPath:
    line_id: str
    voltage_class: str
    voltage_kv: float | None
    owner: str
    status: str
    coords: list[list[float]]   # [[lon, lat], ...] decimated
    color: list[int]            # [r, g, b]
    stroke: float
    rank: int                   # 0..6, higher = more important


class TransmissionData:
    def __init__(
        self,
        geojson_path: Path | None = None,
        min_voltage_class_rank: int = 2,    # default: drop everything below 220 kV
        max_points_per_line: int = 8,
    ):
        self.geojson_path = geojson_path or self._find_geojson()
        self.min_rank = min_voltage_class_rank
        self.max_points = max_points_per_line
        self.paths: list[TransmissionPath] = []
        self.loaded = False
        # Note: DON'T load eagerly. Load on first request to keep server startup fast.

    @staticmethod
    def _find_geojson() -> Path | None:
        for p in DATA_DIR.glob("US_Electric_Power_Transmission_Lines*.geojson"):
            return p
        return None

    def load(self) -> None:
        if self.loaded:
            return
        if not self.geojson_path or not self.geojson_path.exists():
            log.warning("transmission GeoJSON not found in %s", DATA_DIR)
            self.loaded = True
            return
        log.info("loading HIFLD transmission GeoJSON: %s", self.geojson_path.name)
        t0 = time.time()
        with open(self.geojson_path) as f:
            g = json.load(f)
        t1 = time.time()
        kept = 0
        for feat in g.get("features", []):
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            volt_class = (props.get("VOLT_CLASS") or "").strip().upper()
            style = VOLTAGE_STYLE.get(volt_class, DEFAULT_STYLE)
            if style["rank"] < self.min_rank:
                continue
            if props.get("STATUS") and "IN SERVICE" not in props["STATUS"].upper():
                continue
            gtype = geom.get("type")
            if gtype == "LineString":
                lines = [geom.get("coordinates") or []]
            elif gtype == "MultiLineString":
                lines = geom.get("coordinates") or []
            else:
                continue
            for coords in lines:
                if len(coords) < 2:
                    continue
                v_kv_raw = props.get("VOLTAGE")
                v_kv = None
                try:
                    f_kv = float(v_kv_raw)
                    if f_kv > 0:
                        v_kv = f_kv
                except (TypeError, ValueError):
                    pass
                self.paths.append(TransmissionPath(
                    line_id=str(props.get("ID") or props.get("OBJECTID_1") or kept),
                    voltage_class=volt_class or "OTHER",
                    voltage_kv=v_kv,
                    owner=props.get("OWNER") or "",
                    status=props.get("STATUS") or "",
                    coords=_decimate(coords, self.max_points),
                    color=style["color"],
                    stroke=style["stroke"],
                    rank=style["rank"],
                ))
                kept += 1
        # sort high-voltage last so they render on top
        self.paths.sort(key=lambda p: p.rank)
        t2 = time.time()
        log.info("HIFLD transmission ready: %d lines after filtering "
                 "(parse %.1fs, filter %.1fs, total %d features)",
                 len(self.paths), t1 - t0, t2 - t1, len(g.get("features", [])))
        self.loaded = True

    def to_payload(self, max_lines: int = 12000, min_rank: int | None = None) -> dict:
        """Serializable payload for the UI."""
        if not self.loaded:
            self.load()
        cutoff = self.min_rank if min_rank is None else min_rank
        # filter at request time so different ranks return different subsets
        paths = [p for p in self.paths if p.rank >= cutoff]
        if len(paths) > max_lines:
            paths = sorted(paths, key=lambda p: -p.rank)[:max_lines]
        return {
            "count": len(paths),
            "lines": [
                {
                    "id": p.line_id,
                    "vc": p.voltage_class,
                    "kv": p.voltage_kv,
                    "owner": p.owner,
                    "coords": p.coords,
                    "color": p.color,
                    "stroke": p.stroke,
                    "rank": p.rank,
                }
                for p in paths
            ],
            "voltage_legend": [
                {"class": k, "color": v["color"], "rank": v["rank"]}
                for k, v in sorted(VOLTAGE_STYLE.items(), key=lambda kv: -kv[1]["rank"])
            ],
        }
