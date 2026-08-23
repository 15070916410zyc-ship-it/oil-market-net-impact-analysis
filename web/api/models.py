from __future__ import annotations

from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import requests


for candidate in (Path(__file__).resolve().parents[2], Path.cwd(), Path.cwd().parent):
    if (candidate / "src").is_dir():
        sys.path.insert(0, str(candidate))
        break

from src.crisis_warning import run_five_day_warning
from src.price_forecast import run_oil_price_forecast
from src.quick_analysis import IMF_CHANNELS
from src.vmd_module import estimate_center_frequency, run_vmd


def _fred_series(series_id: str, start: str = "2000-01-01") -> pd.DataFrame:
    key = os.getenv("FRED_API_KEY", "").strip()
    if key:
        response = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": key, "file_type": "json", "observation_start": start},
            timeout=30,
        )
        response.raise_for_status()
        rows = response.json().get("observations", [])
        frame = pd.DataFrame({"Date": [row.get("date") for row in rows], series_id: [row.get("value") for row in rows]})
    else:
        response = requests.get(
            "https://fred.stlouisfed.org/graph/fredgraph.csv",
            params={"id": series_id, "cosd": start},
            timeout=30,
        )
        response.raise_for_status()
        from io import StringIO
        frame = pd.read_csv(StringIO(response.text))
        frame.columns = ["Date", series_id]
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
    return frame.dropna().drop_duplicates("Date").sort_values("Date")


def _records(frame: pd.DataFrame) -> list[dict]:
    copy = frame.copy()
    for column in copy.columns:
        if pd.api.types.is_datetime64_any_dtype(copy[column]):
            copy[column] = copy[column].dt.strftime("%Y-%m-%d")
    return json.loads(copy.replace({np.nan: None}).to_json(orient="records"))


def _forecast(payload: dict) -> dict:
    horizon = min(max(int(payload.get("horizon", 20)), 1), 60)
    prices = _fred_series("DCOILBRENTEU").rename(columns={"DCOILBRENTEU": "Brent"})
    result = run_oil_price_forecast(prices, price_column="Brent", horizon=horizon)
    return {
        "method": "five-IMF VMD with BPNN/AR-Ridge and chronological split-conformal intervals",
        "metrics": result.metrics,
        "history": _records(result.history),
        "forecast": _records(result.forecast),
        "components": _records(result.components),
        "modelSummary": _records(result.model_summary),
    }


def _risk() -> dict:
    prices = _fred_series("DCOILBRENTEU").rename(columns={"DCOILBRENTEU": "Brent"})
    result = run_five_day_warning(prices, price_column="Brent")
    return {
        "method": result.model_note,
        "latestDate": result.latest_date.strftime("%Y-%m-%d"),
        "riskScore": result.risk_score,
        "riskPercentile": result.risk_percentile,
        "alertThreshold": result.alert_threshold,
        "alert": bool(result.alert),
        "history": _records(result.risk_history.tail(500)),
        "channels": _records(result.channel_scores),
    }


def _decomposition(payload: dict) -> dict:
    count = min(max(int(payload.get("imf", 5)), 3), 8)
    prices = _fred_series("DCOILBRENTEU").tail(1500)
    values = prices["DCOILBRENTEU"].to_numpy(dtype=float)
    imfs = run_vmd(values, K=count, alpha=1000)
    summaries = []
    for index in range(count):
        frequency, _ = estimate_center_frequency(imfs[:, index])
        key = f"IMF{index + 1}"
        channel = IMF_CHANNELS.get(key, {"channel_zh": "长期趋势", "channel_en": "Long-run trend"})
        summaries.append({
            "imf": key,
            "channelZh": channel["channel_zh"],
            "channelEn": channel["channel_en"],
            "centerFrequency": float(frequency),
            "volatilityShare": float(np.var(imfs[:, index]) / max(np.var(values), 1e-12) * 100),
            "latestValue": float(imfs[-1, index]),
        })
    return {"method": "VMD alpha=1000 on the latest official Brent sample", "asOf": prices["Date"].iloc[-1].strftime("%Y-%m-%d"), "components": summaries}


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        self._send(200, {"ok": True, "service": "oil-research-models", "methods": ["forecast", "risk", "decomposition"]})

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            path = urlparse(self.path).path.rstrip("/")
            if path.endswith("/forecast"):
                result = _forecast(payload)
            elif path.endswith("/risk"):
                result = _risk()
            elif path.endswith("/decomposition"):
                result = _decomposition(payload)
            else:
                return self._send(404, {"error": "Unknown model endpoint"})
            self._send(200, result)
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:
            self._send(500, {"error": "Model execution failed", "detail": str(exc)[:300]})
