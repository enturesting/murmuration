"""Forecaster: sklearn GradientBoostingRegressor with rolling-history training.

Each BA gets its own three models (load / lmp / carbon). Models are retrained
periodically as more samples accumulate. Until enough samples exist (~24),
falls back to EMA + diurnal sinusoid so demos don't go cold while warming up.

Features used (small but informative):
  - hour-of-day (sin/cos encoding so it wraps cleanly)
  - day-of-week
  - last sample value
  - 5-sample lag value
  - rolling 12-sample mean
"""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
import math
import logging

import numpy as np

try:
    from sklearn.ensemble import GradientBoostingRegressor
    _has_sklearn = True
except ImportError:
    _has_sklearn = False

log = logging.getLogger(__name__)

MIN_SAMPLES_FOR_TRAIN = 24
RETRAIN_EVERY_N_SAMPLES = 12


class _Series:
    def __init__(self, history_size: int = 256):
        self.t: deque[datetime] = deque(maxlen=history_size)
        self.v: deque[float] = deque(maxlen=history_size)
        self._model = None
        self._last_train_n = 0

    def push(self, t: datetime, v: float) -> None:
        self.t.append(t)
        self.v.append(v)

    def _features(self, t: datetime, last: float, lag5: float, mean12: float) -> list[float]:
        h = t.hour + t.minute / 60.0
        return [
            math.sin(h * 2 * math.pi / 24),
            math.cos(h * 2 * math.pi / 24),
            float(t.weekday()),
            last,
            lag5,
            mean12,
        ]

    def _maybe_train(self) -> None:
        if not _has_sklearn or len(self.v) < MIN_SAMPLES_FOR_TRAIN:
            return
        if (len(self.v) - self._last_train_n) < RETRAIN_EVERY_N_SAMPLES and self._model is not None:
            return
        # Build (X, y) where y = v[i+1] given features at i
        X, y = [], []
        vals = list(self.v)
        ts = list(self.t)
        for i in range(5, len(vals) - 1):
            last = vals[i]
            lag5 = vals[i - 5]
            mean12 = float(np.mean(vals[max(0, i - 11):i + 1]))
            X.append(self._features(ts[i], last, lag5, mean12))
            y.append(vals[i + 1])
        if len(X) < 8:
            return
        model = GradientBoostingRegressor(
            n_estimators=60, max_depth=3, learning_rate=0.08, random_state=42,
        )
        model.fit(X, y)
        self._model = model
        self._last_train_n = len(self.v)

    def predict(self, t: datetime, n_steps: int, interval_min: int) -> list[float]:
        self._maybe_train()
        if not self.v:
            return [0.0] * n_steps
        # always start from the most recent observation
        last = self.v[-1]
        lag5 = self.v[-5] if len(self.v) >= 5 else self.v[0]
        if self._model is None:
            # fallback: gentle diurnal modulation around the running mean
            ema = last
            recent = list(self.v)[-12:]
            for x in recent:
                ema = 0.7 * ema + 0.3 * x
            out = []
            for i in range(n_steps):
                future_t_h = ((t.timestamp() + i * interval_min * 60) / 3600.0) % 24
                mod = 1.0 + 0.05 * math.cos((future_t_h - 18.0) / 24.0 * 2 * math.pi)
                out.append(ema * mod)
            return out
        # iterative one-step-ahead forecast feeding predictions back as features
        out = []
        cur_last = last
        cur_lag5 = lag5
        recent_window = list(self.v)[-12:]
        for i in range(n_steps):
            future_t = datetime.fromtimestamp(t.timestamp() + i * interval_min * 60, tz=timezone.utc)
            x = self._features(future_t, cur_last, cur_lag5, float(np.mean(recent_window)))
            try:
                yhat = float(self._model.predict([x])[0])
            except Exception:
                yhat = cur_last
            out.append(yhat)
            recent_window = recent_window[1:] + [yhat]
            cur_lag5 = recent_window[-6] if len(recent_window) >= 6 else cur_last
            cur_last = yhat
        return out


class Forecaster:
    """One forecaster per BA. Stateful: ingests samples over time."""

    def __init__(self, history_size: int = 256):
        self.load = _Series(history_size)
        self.lmp = _Series(history_size)
        self.carbon = _Series(history_size)

    def ingest(self, t: datetime, load_mw: float, lmp: float, carbon: float) -> None:
        self.load.push(t, load_mw)
        self.lmp.push(t, lmp)
        self.carbon.push(t, carbon)

    def forecast(
        self, t: datetime, horizon_min: int = 60, interval_min: int = 5,
    ) -> dict:
        n = horizon_min // interval_min
        load = self.load.predict(t, n, interval_min)
        lmp = self.lmp.predict(t, n, interval_min)
        carbon = self.carbon.predict(t, n, interval_min)
        n_samples = len(self.load.v)
        is_trained = self.load._model is not None
        # confidence widens with horizon AND drops if we're not yet trained
        base_conf = 0.92 if is_trained else 0.7
        conf = [max(0.5, base_conf - 0.005 * i) for i in range(n)]
        return {
            "load": load, "lmp": lmp, "carbon": carbon, "confidence": conf,
            "horizon_min": horizon_min, "interval_min": interval_min,
            "n_samples": n_samples, "trained": is_trained,
        }
