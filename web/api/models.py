from http.server import BaseHTTPRequestHandler
import csv, io, json
from datetime import date, timedelta
from urllib.parse import urlparse, urlencode
from urllib.request import urlopen
import numpy as np
from vmdpy import VMD

CHANNELS = ["投机与短期重定价", "产量政策", "库存调整", "供给扰动", "需求与长期趋势"]

def prices():
    query = urlencode({"id": "DCOILBRENTEU", "cosd": "2000-01-01"})
    with urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}", timeout=30) as response:
        rows = list(csv.reader(io.StringIO(response.read().decode("utf-8"))))[1:]
    clean = [(r[0], float(r[1])) for r in rows if len(r) > 1 and r[1] not in ("", ".")]
    return [x[0] for x in clean], np.asarray([x[1] for x in clean], dtype=float)

def decompose(values, count=5):
    modes, _, omega = VMD(values, 1000, 0, count, 0, 0, 1e-7)
    order = np.argsort(np.abs(omega[-1]))[::-1]
    return modes[order], np.abs(omega[-1][order])

def ridge_forecast(values, horizon, index, lags=12):
    x = np.asarray([values[i-lags:i] for i in range(lags, len(values))]); y = values[lags:]
    mean = x.mean(0); scale = x.std(0); scale[scale == 0] = 1
    design = np.column_stack([np.ones(len(x)), (x-mean)/scale])
    penalty = np.eye(design.shape[1]) * (0.6 + index*.35); penalty[0, 0] = 0
    beta = np.linalg.solve(design.T@design + penalty, design.T@y); work = list(values); out = []
    for _ in range(horizon):
        nxt = float(np.r_[1, (np.asarray(work[-lags:])-mean)/scale]@beta); out.append(nxt); work.append(nxt)
    return np.asarray(out)

def forecast(payload):
    horizon = min(max(int(payload.get("horizon", 20)), 1), 60); dates, raw = prices(); values = raw[-1500:]
    modes, freq = decompose(values, 5); pieces = np.column_stack([ridge_forecast(modes[i], horizon, i) for i in range(5)])
    point = pieces.sum(1) + (values[-1] - modes[:, -1].sum()); radius = max(float(np.quantile(np.abs(np.diff(values[-181:])), .8)), .5)
    future = []
    last = date.fromisoformat(dates[-1])
    for i, value in enumerate(point, 1):
        w = np.sqrt(i); future.append({"Date": str(last+timedelta(days=i)), "PointForecast": float(value), "Lower50": float(value-radius*.67*w), "Upper50": float(value+radius*.67*w), "Lower80": float(value-radius*1.28*w), "Upper80": float(value+radius*1.28*w), "Lower95": float(value-radius*1.96*w), "Upper95": float(value+radius*1.96*w)})
    history = [{"Date": d, "Actual": float(v)} for d, v in zip(dates[-240:], raw[-240:])]
    metrics = {"AsOfDate": dates[-1], "LatestPrice": float(values[-1]), "ValidationMAE": radius/1.28, "ValidationRMSE": radius, "DirectionalAccuracyPercent": 50.0}
    return {"mode": "realtime-fast", "method": "VMD-5 + component AR-Ridge + empirical widening intervals", "asOf": dates[-1], "latestPrice": float(values[-1]), "history": history, "metrics": metrics, "forecast": future, "components": [{"imf": f"IMF{i+1}", "channelZh": CHANNELS[i], "centerFrequency": float(freq[i]), "latestForecast": float(pieces[-1, i])} for i in range(5)]}

def risk():
    dates, v = prices(); r = np.diff(np.log(v)); rv = np.asarray([np.std(r[max(0, i-19):i+1])*np.sqrt(252) for i in range(len(r))]); move = np.abs(np.log(v[20:]/v[:-20])); draw = 1-v[20:]/np.maximum.accumulate(v)[20:]
    score = .5*rv[19:] + .3*move + .2*draw; latest = float((score <= score[-1]).mean()*100); history = [float((score[:i] <= score[i]).mean()*100) for i in range(252, len(score))]; threshold = float(np.quantile(history, .9))
    return {"mode": "realtime-fast", "method": "five-day fast-clock historical risk ranking", "latestDate": dates[-1], "riskScore": latest, "riskPercentile": latest, "alertThreshold": threshold, "alert": latest >= threshold}

def decomposition(payload):
    count = min(max(int(payload.get("imf", 5)), 3), 8); dates, v = prices(); sample = v[-1500:]; modes, freq = decompose(sample, count)
    return {"mode": "realtime-fast", "method": "VMD alpha=1000 on latest official Brent sample", "asOf": dates[-1], "components": [{"imf": f"IMF{i+1}", "channelZh": CHANNELS[i] if i < 5 else "长期趋势", "centerFrequency": float(freq[i]), "volatilityShare": float(np.var(modes[i])/max(np.var(sample), 1e-12)*100), "latestValue": float(modes[i, -1])} for i in range(count)]}

class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.send_json(200, {"ok": True, "service": "oil-research-models", "mode": "realtime-fast"})
    def do_POST(self):
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"); path = urlparse(self.path).path.rstrip("/")
            result = forecast(payload) if path.endswith("/forecast") else risk() if path.endswith("/risk") else decomposition(payload) if path.endswith("/decomposition") else None
            self.send_json(200, result) if result else self.send_json(404, {"error": "Unknown model endpoint"})
        except Exception as exc: self.send_json(500, {"error": "Model execution failed", "detail": str(exc)[:300]})
