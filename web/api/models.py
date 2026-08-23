from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import csv, io, json, math
import re
from datetime import date, timedelta
from urllib.parse import urlparse, urlencode
from urllib.request import urlopen
import numpy as np
from scipy.stats import f as f_distribution
from vmdpy import VMD

CHANNELS_ZH = ["投机与短期重定价", "产量政策", "库存调整", "供给扰动", "需求与长期趋势"]
CHANNELS_EN = ["Speculation and short-term repricing", "Production policy", "Inventory adjustment", "Supply disruption", "Demand and long-run trend"]
SERIES = {
    "EIA-BRENT": ("DCOILBRENTEU", "Brent现货价格", "Brent spot price"),
    "FRED-DCOILWTICO": ("DCOILWTICO", "WTI现货价格", "WTI spot price"),
    "FRED-PETINV": ("A24STI", "美国石油与煤炭产品制造业库存", "US petroleum and coal products manufacturing inventories"),
    "FRED-DTWEXBGS": ("DTWEXBGS", "美元广义指数", "Broad US dollar index"),
    "FRED-DGS10": ("DGS10", "美国10年期国债收益率", "US 10-year Treasury yield"),
    "FRED-DGS2": ("DGS2", "美国2年期国债收益率", "US 2-year Treasury yield"),
    "FRED-FEDFUNDS": ("FEDFUNDS", "联邦基金有效利率", "Effective federal funds rate"),
    "FRED-CPIAUCSL": ("CPIAUCSL", "美国消费者价格指数", "US consumer price index"),
    "FRED-INDPRO": ("INDPRO", "美国工业生产指数", "US industrial production index"),
    "FRED-UNRATE": ("UNRATE", "美国失业率", "US unemployment rate"),
    "FRED-T10YIE": ("T10YIE", "美国10年期通胀预期", "US 10-year inflation expectation"),
    "FRED-VIXCLS": ("VIXCLS", "VIX波动率指数", "VIX volatility index"),
    "FRED-SP500": ("SP500", "标普500指数", "S&P 500 index"),
    "FRED-HENRYHUB": ("DHHNGSP", "Henry Hub天然气现货价", "Henry Hub natural gas spot price"),
    "FRED-GASOLINE": ("GASREGW", "美国常规汽油零售价", "US regular gasoline retail price"),
    "FRED-PPI": ("PPIACO", "美国生产者价格指数", "US producer price index"),
    "FRED-PAYEMS": ("PAYEMS", "美国非农就业", "US nonfarm payrolls"),
    "FRED-RSAFS": ("RSAFS", "美国零售销售", "US retail sales"),
    "FRED-HYSPREAD": ("BAMLH0A0HYM2", "美国高收益债利差", "US high-yield credit spread"),
}

def fetch_fred(provider_id, start="2000-01-01"):
    query = urlencode({"id": provider_id, "cosd": start})
    with urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}", timeout=30) as response:
        rows = list(csv.reader(io.StringIO(response.read().decode("utf-8"))))[1:]
    return [(r[0], float(r[1])) for r in rows if len(r) > 1 and r[1] not in ("", ".")]

def load_series(series_id, start="2000-01-01"):
    if series_id in SERIES: provider_id = SERIES[series_id][0]
    elif re.fullmatch(r"FRED-[A-Z0-9_]+", series_id): provider_id = series_id[5:]
    else: raise ValueError(f"Unsupported official series: {series_id}")
    return fetch_fred(provider_id, start)

def series_meta(series_id):
    return SERIES.get(series_id, (series_id[5:], series_id[5:], series_id[5:]))

def monthly(rows):
    result = {}
    for stamp, value in rows:
        result[stamp[:7]] = float(value)
    return result

def prices(target="EIA-BRENT"):
    clean = load_series(target)
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

def walk_forward_metrics(values, lags=12, origins=60):
    start = max(lags + 36, len(values) - origins); predicted, actual = [], []
    for end in range(start, len(values)):
        predicted.append(float(ridge_forecast(values[:end], 1, 0, lags)[0])); actual.append(float(values[end]))
    predicted, actual = np.asarray(predicted), np.asarray(actual); err = actual-predicted
    previous = values[start-1:len(values)-1]
    return float(np.mean(np.abs(err))), float(np.sqrt(np.mean(err**2))), float(np.mean(np.sign(predicted-previous) == np.sign(actual-previous))*100), err

def forecast(payload):
    horizon = min(max(int(payload.get("horizon", 20)), 1), 60); target = payload.get("target", "EIA-BRENT"); frequency = payload.get("frequency", "daily")
    source_rows = load_series(target)
    if frequency == "monthly":
        grouped = monthly(source_rows); dates = [f"{stamp}-01" for stamp in sorted(grouped)]; raw = np.asarray([grouped[stamp] for stamp in sorted(grouped)], dtype=float)
    else:
        dates = [row[0] for row in source_rows]; raw = np.asarray([row[1] for row in source_rows], dtype=float)
    training = min(max(int(payload.get("training", 120)), 60), len(raw)); values = raw[-training:]; dates = dates[-training:]; count = min(max(int(payload.get("imf", 5)), 3), 8)
    modes, freq = decompose(values, count); pieces = np.column_stack([ridge_forecast(modes[i], horizon, i) for i in range(count)])
    point = pieces.sum(1) + (values[-1] - modes[:, -1].sum()); mae, rmse, directional, residuals = walk_forward_metrics(values)
    q50, q80, q95 = [float(np.quantile(np.abs(residuals), q)) for q in (.50, .80, .95)]
    future = []; last = date.fromisoformat(dates[-1])
    for i, value in enumerate(point, 1):
        if frequency == "monthly":
            month_index = last.year*12 + last.month-1+i; future_date = date(month_index//12, month_index%12+1, 1)
        else: future_date = last+timedelta(days=i)
        w = math.sqrt(i); future.append({"Date": str(future_date), "PointForecast": float(value), "Lower50": float(value-q50*w), "Upper50": float(value+q50*w), "Lower80": float(value-q80*w), "Upper80": float(value+q80*w), "Lower95": float(value-q95*w), "Upper95": float(value+q95*w)})
    history = [{"Date": d, "Actual": float(v)} for d, v in zip(dates[-240:], raw[-240:])]
    metrics = {"AsOfDate": dates[-1], "LatestPrice": float(values[-1]), "ValidationMAE": mae, "ValidationRMSE": rmse, "DirectionalAccuracyPercent": directional, "IntervalCoveragePercent": float(np.mean(np.abs(residuals) <= q80)*100), "ValidationOrigins": len(residuals)}
    return {"mode": "verified-live", "method": f"VMD-{count} + component AR-Ridge + rolling-origin residual intervals", "frequency": frequency, "asOf": dates[-1], "latestPrice": float(values[-1]), "history": history, "metrics": metrics, "forecast": future, "components": [{"imf": f"IMF{i+1}", "channelZh": CHANNELS_ZH[i] if i < 5 else "长期趋势", "channelEn": CHANNELS_EN[i] if i < 5 else "Long-run trend", "centerFrequency": float(freq[i]), "latestForecast": float(pieces[-1, i])} for i in range(count)]}

def risk(payload=None):
    payload = payload or {}; forward = min(max(int(payload.get("forward", 20)), 5), 60); dates, v = prices(payload.get("target", "EIA-BRENT")); safe_denominator = np.maximum(np.abs(v[:-1]), 1.0); returns = np.diff(v)/safe_denominator
    rv = np.asarray([np.std(returns[max(0, i-forward+1):i+1])*np.sqrt(252) for i in range(len(returns))])
    move = np.abs((v[forward:]-v[:-forward])/np.maximum(np.abs(v[:-forward]), 1.0)); running_peak = np.maximum.accumulate(v); draw = (running_peak[forward:]-v[forward:])/np.maximum(np.abs(running_peak[forward:]), 1.0)
    raw = .5*rv[forward-1:] + .3*move + .2*draw
    percentiles = np.asarray([float((raw[:i+1] <= raw[i]).mean()*100) for i in range(len(raw))])
    threshold = float(np.quantile(percentiles[:-1], .9)); aligned_dates = dates[forward:]; latest = float(percentiles[-1])
    history = [{"date": d, "score": float(s)} for d, s in zip(aligned_dates[-500:], percentiles[-500:])]
    return {"mode": "verified-live", "method": f"{forward}-day realized volatility, absolute move and drawdown historical percentile", "latestDate": dates[-1], "riskScore": latest, "riskPercentile": latest, "alertThreshold": threshold, "alert": latest >= threshold, "history": history}

def decomposition(payload):
    count = min(max(int(payload.get("imf", 5)), 3), 8); dates, values = prices(payload.get("target", "EIA-BRENT")); sample = values[-1500:]; sample_dates = dates[-1500:]
    modes, freq = decompose(sample, count); components = []
    for i in range(count):
        components.append({"imf": f"IMF{i+1}", "channelZh": CHANNELS_ZH[i] if i < 5 else "长期趋势", "channelEn": CHANNELS_EN[i] if i < 5 else "Long-run trend", "centerFrequency": float(freq[i]), "volatilityShare": float(np.var(modes[i])/max(np.var(sample), 1e-12)*100), "latestValue": float(modes[i, -1]), "points": [{"date": d, "value": float(v)} for d, v in zip(sample_dates[-240:], modes[i, -240:])]})
    return {"mode": "verified-live", "method": "VMD alpha=1000 on the latest official target series", "asOf": dates[-1], "components": components}

def lag_matrix(y, x, lag):
    n = len(y); dependent = y[lag:]
    ylags = np.column_stack([y[lag-k:n-k] for k in range(1, lag+1)]); xlags = np.column_stack([x[lag-k:n-k] for k in range(1, lag+1)])
    return dependent, np.column_stack([np.ones(len(dependent)), ylags]), np.column_stack([np.ones(len(dependent)), ylags, xlags])

def ols_sse(design, dependent):
    beta = np.linalg.lstsq(design, dependent, rcond=None)[0]; residual = dependent-design@beta
    return float(residual@residual)

def granger_test(y, x, max_lag):
    best = None
    for lag in range(1, max_lag+1):
        dep, restricted, unrestricted = lag_matrix(y, x, lag); sse_r, sse_u = ols_sse(restricted, dep), ols_sse(unrestricted, dep); df2 = len(dep)-unrestricted.shape[1]
        if df2 <= 2 or sse_u <= 0: continue
        statistic = max(0.0, ((sse_r-sse_u)/lag)/(sse_u/df2)); p_value = float(f_distribution.sf(statistic, lag, df2)); bic = len(dep)*math.log(max(sse_u/len(dep), 1e-12))+unrestricted.shape[1]*math.log(len(dep)); row = (bic, lag, statistic, p_value)
        if best is None or row[0] < best[0]: best = row
    return best or (float("nan"), 1, 0.0, 1.0)

def fit_var(data, lag):
    """Fit a reduced-form VAR with an intercept and return coefficients/covariance."""
    n, variables = data.shape
    dependent = data[lag:]
    design = np.column_stack([np.ones(n-lag)] + [data[lag-k:n-k] for k in range(1, lag+1)])
    coefficients = np.linalg.lstsq(design, dependent, rcond=None)[0]
    residuals = dependent-design@coefficients
    degrees = max(len(residuals)-design.shape[1], 1)
    covariance = residuals.T@residuals/degrees
    return coefficients, covariance, residuals

def select_var_lag(data, max_lag):
    best = None
    variables = data.shape[1]
    for lag in range(1, max_lag+1):
        if len(data)-lag <= variables*lag+2: continue
        coefficients, covariance, residuals = fit_var(data, lag)
        sign, logdet = np.linalg.slogdet(covariance + np.eye(variables)*1e-10)
        if sign <= 0: continue
        bic = logdet + math.log(len(residuals))*(variables*variables*lag+variables)/len(residuals)
        if best is None or bic < best[0]: best = (bic, lag, coefficients, covariance)
    if best is None: raise ValueError("Insufficient observations for VAR estimation")
    return best[1], best[2], best[3]

def generalized_fevd(data, horizon, max_lag):
    """Pesaran-Shin generalized FEVD, row-normalized for correlated innovations."""
    lag, coefficients, covariance = select_var_lag(data, max_lag)
    variables = data.shape[1]
    ar = [coefficients[1+i*variables:1+(i+1)*variables].T for i in range(lag)]
    phi = [np.eye(variables)]
    for step in range(1, horizon):
        value = np.zeros((variables, variables))
        for offset in range(1, min(lag, step)+1): value += phi[step-offset]@ar[offset-1]
        phi.append(value)
    theta = np.zeros((variables, variables))
    diagonal = np.maximum(np.diag(covariance), 1e-12)
    for i in range(variables):
        denominator = sum(float((matrix@covariance@matrix.T)[i, i]) for matrix in phi)
        for j in range(variables):
            numerator = sum(float((matrix@covariance)[i, j])**2 for matrix in phi)/diagonal[j]
            theta[i, j] = numerator/max(denominator, 1e-12)
    theta /= np.maximum(theta.sum(axis=1, keepdims=True), 1e-12)
    return lag, theta

def segmented_break_test(values, dates):
    """Search interior break dates by comparing pooled and two-segment OLS RSS."""
    y = np.asarray(values, dtype=float); t = np.arange(len(y), dtype=float)
    pooled = ols_sse(np.column_stack([np.ones(len(y)), t]), y)
    minimum = max(18, len(y)//8); profile = []; best = None
    for split in range(minimum, len(y)-minimum, max(1, len(y)//80)):
        left_x = np.column_stack([np.ones(split), t[:split]])
        right_x = np.column_stack([np.ones(len(y)-split), t[split:]-t[split]])
        rss = ols_sse(left_x, y[:split])+ols_sse(right_x, y[split:])
        improvement = max(0.0, 1-rss/max(pooled, 1e-12))*100
        row = {"date": dates[split], "rss": float(rss), "improvementPercent": float(improvement)}
        profile.append(row)
        if best is None or rss < best[0]: best = (rss, row)
    return {"candidateCount": len(profile), "bestDate": best[1]["date"], "rssImprovementPercent": best[1]["improvementPercent"], "profile": profile}

def net_impact(payload):
    target = payload.get("target", "EIA-BRENT"); selected = [x for x in payload.get("factors", []) if (x in SERIES or re.fullmatch(r"FRED-[A-Z0-9_]+", x)) and x != target]
    if not selected: selected = ["FRED-PETINV", "FRED-DTWEXBGS", "FRED-DGS10", "FRED-INDPRO", "FRED-T10YIE", "FRED-VIXCLS", "FRED-HENRYHUB"]
    selected = selected[:12]; start = payload.get("start", "2005-01-01"); max_lag = min(max(int(payload.get("maxLag", 3)), 1), 6); count = min(max(int(payload.get("imf", 5)), 3), 8)
    with ThreadPoolExecutor(max_workers=min(8, len(selected)+1)) as pool: loaded = list(pool.map(lambda sid: (sid, monthly(load_series(sid, start))), [target]+selected))
    maps = dict(loaded); end = str(payload.get("end", "9999-12-31"))[:7]; common = [stamp for stamp in sorted(set.intersection(*(set(maps[sid]) for sid in [target]+selected))) if stamp <= end]
    if len(common) < 72: raise ValueError(f"Only {len(common)} aligned monthly observations; at least 72 are required")
    levels = {sid: np.asarray([maps[sid][d] for d in common], dtype=float) for sid in [target]+selected}; y_level = levels[target]; y = np.diff(y_level); factor_changes = []
    for sid in selected:
        arr = levels[sid]; factor_changes.append(np.diff(np.log(arr)) if np.all(arr > 0) else np.diff(arr))
    x_raw = np.column_stack(factor_changes); means, scales = x_raw.mean(0), x_raw.std(0); scales[scales == 0] = 1; x = (x_raw-means)/scales
    design = np.column_stack([np.ones(len(y)), x]); beta = np.linalg.lstsq(design, y, rcond=None)[0]; contributions = beta[1:]*x[-1]; fitted = design@beta; r2 = float(1-np.sum((y-fitted)**2)/max(np.sum((y-y.mean())**2), 1e-12))
    alpha = float(payload.get("alpha", .05)); granger = []
    for index, sid in enumerate(selected):
        meta = series_meta(sid); _, lag, statistic, p_value = granger_test(y, x[:, index], max_lag); granger.append({"id": sid, "nameZh": meta[1], "nameEn": meta[2], "lag": lag, "fStatistic": statistic, "pValue": p_value, "significant": p_value < alpha})
    modes, freq = decompose(y_level[-min(600, len(y_level)):], count); component_dates = common[-modes.shape[1]:]
    components = [{"imf": f"IMF{i+1}", "channelZh": CHANNELS_ZH[i] if i < 5 else "长期趋势", "channelEn": CHANNELS_EN[i] if i < 5 else "Long-run trend", "centerFrequency": float(freq[i]), "volatilityShare": float(np.var(modes[i])/max(np.var(y_level), 1e-12)*100), "points": [{"date": d, "value": float(v)} for d, v in zip(component_dates[-180:], modes[i, -180:])]} for i in range(count)]
    # Multi-resolution Granger tests use decompositions of the same aligned monthly sample.
    y_modes, _ = decompose(y, count); factor_modes = [decompose(x[:, index], count)[0] for index in range(len(selected))]
    scale_granger = []
    for factor_index, sid in enumerate(selected):
        meta = series_meta(sid)
        for scale_index in range(count):
            _, lag, statistic, p_value = granger_test(y_modes[scale_index], factor_modes[factor_index][scale_index], max_lag)
            scale_granger.append({"id": sid, "nameZh": meta[1], "nameEn": meta[2], "imf": f"IMF{scale_index+1}", "lag": lag, "fStatistic": statistic, "pValue": p_value, "significant": p_value < alpha})
    selected_scales = []
    for sid in selected:
        candidates = [row for row in scale_granger if row["id"] == sid]
        chosen = min(candidates, key=lambda row: row["pValue"])
        selected_scales.append({"id": sid, "nameZh": chosen["nameZh"], "nameEn": chosen["nameEn"], "imf": chosen["imf"], "pValue": chosen["pValue"]})
    horizon = min(max(int(payload.get("fevdHorizon", 12)), 2), 36)
    var_data = np.column_stack([y, x])
    var_lag, fevd_matrix = generalized_fevd(var_data, horizon, max_lag)
    fevd = [{"id": sid, "nameZh": series_meta(sid)[1], "nameEn": series_meta(sid)[2], "share": float(fevd_matrix[0, index+1]*100)} for index, sid in enumerate(selected)]
    own_share = float(fevd_matrix[0, 0]*100)
    window = min(max(int(payload.get("window", 60)), 24), len(y)); rolling = []; rolling_fevd = []
    for end in range(window, len(y)+1):
        local_x, local_y = x[end-window:end], y[end-window:end]; local_design = np.column_stack([np.ones(window), local_x]); local_beta = np.linalg.lstsq(local_design, local_y, rcond=None)[0]
        rolling.append({"date": common[end], "observed": float(local_y[-1]), "fitted": float(local_design[-1]@local_beta)})
        if (end-window) % 3 == 0 or end == len(y):
            local_lag, local_fevd = generalized_fevd(np.column_stack([local_y, local_x]), horizon, min(max_lag, 3))
            rolling_fevd.append({"date": common[end], "externalShare": float((1-local_fevd[0,0])*100), "ownShare": float(local_fevd[0,0]*100), "lag": local_lag})
    drivers = [{"id": sid, "nameZh": series_meta(sid)[1], "nameEn": series_meta(sid)[2], "impact": float(contributions[i]), "coefficient": float(beta[i+1])} for i, sid in enumerate(selected)]; drivers.sort(key=lambda row: abs(row["impact"]), reverse=True)
    break_test = segmented_break_test(y, common[1:])
    return {"mode": "verified-live", "method": "Monthly aligned official series; VMD; multi-resolution Granger tests; generalized FEVD; rolling OLS and FEVD; segmented RSS break search", "asOf": common[-1], "target": target, "observations": len(common), "rSquared": r2, "drivers": drivers, "granger": granger, "scaleGranger": scale_granger, "selectedScales": selected_scales, "components": components, "fevd": fevd, "fevdOwnShare": own_share, "fevdHorizon": horizon, "varLag": var_lag, "rolling": rolling[-180:], "rollingFevd": rolling_fevd[-120:], "breakTest": break_test, "sources": [{"id": sid, "providerId": series_meta(sid)[0], "nameZh": series_meta(sid)[1], "nameEn": series_meta(sid)[2]} for sid in [target]+selected]}

class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.send_json(200, {"ok": True, "service": "oil-research-models", "mode": "verified-live"})
    def do_POST(self):
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"); path = urlparse(self.path).path.rstrip("/"); action = payload.get("action") or path.rsplit("/", 1)[-1]; actions = {"forecast": forecast, "risk": risk, "decomposition": decomposition, "net-impact": net_impact}; result = actions[action](payload) if action in actions else None
            self.send_json(200, result) if result else self.send_json(404, {"error": "Unknown model endpoint"})
        except Exception as exc: self.send_json(500, {"error": "Model execution failed", "detail": str(exc)[:500]})
