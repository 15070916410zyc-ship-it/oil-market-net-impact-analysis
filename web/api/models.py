from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import csv, io, json, math
import re
from datetime import date, timedelta
from urllib.parse import urlparse, urlencode
from urllib.request import urlopen
import numpy as np
import xlrd
from vmdpy import VMD

CHANNELS_ZH = ["投机与短期重定价", "产量政策", "库存调整", "供给扰动", "需求与长期趋势"]
CHANNELS_EN = ["Speculation and short-term repricing", "Production policy", "Inventory adjustment", "Supply disruption", "Demand and long-run trend"]
SERIES = {
    "GPRD": ("GPRD", "地缘政治风险指数（传统日度 GPR）", "Geopolitical Risk Index (traditional daily GPR)"),
    "EIA-BRENT": ("DCOILBRENTEU", "Brent现货价格", "Brent spot price"),
    "FRED-DCOILWTICO": ("DCOILWTICO", "WTI现货价格", "WTI spot price"),
    "FRED-PETINV": ("A24STI", "美国石油与煤炭产品制造业库存", "US petroleum and coal products manufacturing inventories"),
    "FRED-CRUDESTOCKS": ("A24ATI", "美国炼厂库存", "US petroleum refinery inventories"),
    "FRED-CRUDEPROD": ("IPG21112N", "美国原油开采工业生产指数", "US industrial production: crude oil extraction"),
    "FRED-REFINERYUTIL": ("IPG32411S", "美国炼厂工业生产指数", "US industrial production: petroleum refineries"),
    "FRED-DTWEXBGS": ("DTWEXBGS", "美元广义指数", "Broad US dollar index"),
    "FRED-DEXCHUS": ("DEXCHUS", "美元兑人民币即期汇率", "China / U.S. foreign exchange rate"),
    "FRED-DGS10": ("DGS10", "美国10年期国债收益率", "US 10-year Treasury yield"),
    "FRED-DGS2": ("DGS2", "美国2年期国债收益率", "US 2-year Treasury yield"),
    "FRED-FEDFUNDS": ("FEDFUNDS", "联邦基金有效利率", "Effective federal funds rate"),
    "FRED-DFF": ("DFF", "联邦基金有效利率（日度）", "Effective Federal Funds Rate"),
    "FRED-CPIAUCSL": ("CPIAUCSL", "美国消费者价格指数", "US consumer price index"),
    "FRED-INDPRO": ("INDPRO", "美国工业生产指数", "US industrial production index"),
    "FRED-UNRATE": ("UNRATE", "美国失业率", "US unemployment rate"),
    "FRED-T10YIE": ("T10YIE", "美国10年期通胀预期", "US 10-year inflation expectation"),
    "FRED-HYSPREAD": ("BAMLH0A0HYM2", "美国高收益债利差", "US high-yield credit spread"),
    "FRED-STLFSI4": ("STLFSI4", "圣路易斯联储金融压力指数", "St. Louis Fed Financial Stress Index"),
    "FRED-VIXCLS": ("VIXCLS", "VIX波动率指数", "VIX volatility index"),
    "FRED-OVXCLS": ("OVXCLS", "原油ETF隐含波动率指数", "CBOE Crude Oil ETF Volatility Index"),
    "FRED-SP500": ("SP500", "标普500指数", "S&P 500 index"),
    "FRED-HENRYHUB": ("DHHNGSP", "Henry Hub天然气现货价", "Henry Hub natural gas spot price"),
    "FRED-GASOLINE": ("GASREGW", "美国常规汽油零售价", "US regular gasoline retail price"),
    "FRED-COPPER": ("PCOPPUSDM", "全球铜价", "Global copper price"),
    "FRED-USEPUINDXD": ("USEPUINDXD", "美国经济政策不确定性指数", "US Economic Policy Uncertainty Index"),
    "FRED-PPI": ("PPIACO", "美国生产者价格指数", "US producer price index"),
    "FRED-PAYEMS": ("PAYEMS", "美国非农就业", "US nonfarm payrolls"),
    "FRED-RSAFS": ("RSAFS", "美国零售销售", "US retail sales"),
    "FRED-HYSPREAD": ("BAMLH0A0HYM2", "美国高收益债利差", "US high-yield credit spread"),
    "FRED-STLFSI4": ("STLFSI4", "圣路易斯联储金融压力指数", "St. Louis Fed Financial Stress Index"),
    "FRED-NASDAQXAU": ("NASDAQXAU", "PHLX黄金与白银行业指数", "PHLX Gold/Silver Sector Index"),
}

GPRD_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
_GPRD_CACHE = None
SELECTED_SCALE_SCORE_RATIO = 0.50

def _beta_continued_fraction(a, b, x, iterations=200, tolerance=3e-14):
    """Numerically stable continued fraction used by regularized beta."""
    floor = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / max(abs(d), floor) * (1 if d >= 0 else -1)
    result = d
    for index in range(1, iterations + 1):
        twice = 2 * index
        coefficient = index * (b - index) * x / ((qam + twice) * (a + twice))
        d = 1.0 + coefficient * d
        d = 1.0 / max(abs(d), floor) * (1 if d >= 0 else -1)
        c = 1.0 + coefficient / c
        c = max(abs(c), floor) * (1 if c >= 0 else -1)
        result *= d * c
        coefficient = -(a + index) * (qab + index) * x / ((a + twice) * (qap + twice))
        d = 1.0 + coefficient * d
        d = 1.0 / max(abs(d), floor) * (1 if d >= 0 else -1)
        c = 1.0 + coefficient / c
        c = max(abs(c), floor) * (1 if c >= 0 else -1)
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < tolerance:
            break
    return result

def regularized_beta(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b

def f_survival(statistic, numerator_df, denominator_df):
    if statistic <= 0: return 1.0
    if numerator_df <= 0 or denominator_df <= 0: return float("nan")
    x = denominator_df / (denominator_df + numerator_df * statistic)
    return min(1.0, max(0.0, regularized_beta(denominator_df / 2.0, numerator_df / 2.0, x)))

def analytic_signal(values):
    """FFT Hilbert transform equivalent to scipy.signal.hilbert for real input."""
    values = np.asarray(values, dtype=float)
    count = len(values)
    spectrum_filter = np.zeros(count)
    if count % 2 == 0:
        spectrum_filter[0] = spectrum_filter[count // 2] = 1.0
        spectrum_filter[1:count // 2] = 2.0
    else:
        spectrum_filter[0] = 1.0
        spectrum_filter[1:(count + 1) // 2] = 2.0
    return np.fft.ifft(np.fft.fft(values) * spectrum_filter)

def fetch_gprd(start="1985-01-01"):
    global _GPRD_CACHE
    if _GPRD_CACHE is None:
        with urlopen(GPRD_URL, timeout=35) as response:
            workbook = xlrd.open_workbook(file_contents=response.read())
        sheet = workbook.sheet_by_index(0)
        headers = [str(sheet.cell_value(0, column)).strip() for column in range(sheet.ncols)]
        day_column, value_column = headers.index("DAY"), headers.index("GPRD")
        loaded = []
        for index in range(1, sheet.nrows):
            try:
                digits = str(int(sheet.cell_value(index, day_column)))
                stamp = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
                value = float(sheet.cell_value(index, value_column))
            except (TypeError, ValueError):
                continue
            loaded.append((stamp, value))
        _GPRD_CACHE = loaded
    rows = [row for row in _GPRD_CACHE if row[0] >= start]
    if not rows: raise ValueError("Official GPRD workbook contained no usable observations")
    return rows

def fetch_fred(provider_id, start="2000-01-01"):
    query = urlencode({"id": provider_id, "cosd": start})
    with urlopen(f"https://fred.stlouisfed.org/graph/fredgraph.csv?{query}", timeout=30) as response:
        rows = list(csv.reader(io.StringIO(response.read().decode("utf-8"))))[1:]
    return [(r[0], float(r[1])) for r in rows if len(r) > 1 and r[1] not in ("", ".")]

def load_series(series_id, start="2000-01-01"):
    if series_id == "GPRD": return fetch_gprd(start)
    if series_id in SERIES: provider_id = SERIES[series_id][0]
    elif re.fullmatch(r"FRED-[A-Z0-9_]+", series_id): provider_id = series_id[5:]
    else: raise ValueError(f"Unsupported official series: {series_id}")
    return fetch_fred(provider_id, start)

def series_meta(series_id):
    return SERIES.get(series_id, (series_id[5:] if series_id.startswith("FRED-") else series_id, series_id, series_id))

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
    modes = modes[order]
    if modes.shape[1] < len(values):
        missing = len(values)-modes.shape[1]
        modes = np.pad(modes, ((0,0),(missing,0)), mode="edge")
    elif modes.shape[1] > len(values):
        modes = modes[:,-len(values):]
    return modes, np.abs(omega[-1][order])

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
        statistic = max(0.0, ((sse_r-sse_u)/lag)/(sse_u/df2)); p_value = f_survival(statistic, lag, df2); bic = len(dep)*math.log(max(sse_u/len(dep), 1e-12))+unrestricted.shape[1]*math.log(len(dep)); row = (bic, lag, statistic, p_value)
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

def orthogonal_fevd(data, horizon, max_lag):
    """Cholesky-orthogonal FEVD used by the original professional workflow."""
    lag, coefficients, covariance = select_var_lag(data, max_lag)
    variables = data.shape[1]
    ar = [coefficients[1+i*variables:1+(i+1)*variables].T for i in range(lag)]
    phi = [np.eye(variables)]
    for step in range(1, horizon):
        value = np.zeros((variables, variables))
        for offset in range(1, min(lag, step)+1):
            value += phi[step-offset] @ ar[offset-1]
        phi.append(value)
    jitter = 1e-10
    while True:
        try:
            impact = np.linalg.cholesky(covariance + np.eye(variables)*jitter)
            break
        except np.linalg.LinAlgError:
            jitter *= 10
            if jitter > 1e-2:
                raise ValueError("VAR innovation covariance is not positive definite")
    contributions = np.zeros((variables, variables))
    for matrix in phi:
        response = matrix @ impact
        contributions += response**2
    contributions /= np.maximum(contributions.sum(axis=1, keepdims=True), 1e-12)
    return lag, contributions

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

def fixed_break_test(values, dates, break_date):
    y = np.asarray(values, dtype=float); t = np.arange(1, len(y)+1, dtype=float)
    matches = [index for index, stamp in enumerate(dates) if stamp >= break_date]
    if not matches: raise ValueError("Event start is outside the aligned data window")
    split = matches[0]+1; indicator = (t >= split).astype(float); post = indicator*(t-split+1)
    restricted = np.column_stack([np.ones(len(y)), t]); unrestricted = np.column_stack([np.ones(len(y)), t, indicator, post])
    beta_r = np.linalg.lstsq(restricted, y, rcond=None)[0]; beta_u = np.linalg.lstsq(unrestricted, y, rcond=None)[0]
    rss_r = ols_sse(restricted, y); rss_u = ols_sse(unrestricted, y); df1 = 2; df2 = len(y)-4
    statistic = max(0.0, ((rss_r-rss_u)/df1)/max(rss_u/max(df2,1),1e-12)); p_value = f_survival(statistic,df1,max(df2,1))
    return {"breakDate": dates[matches[0]], "fStatistic": statistic, "pValue": p_value, "preSlope": float(beta_u[1]), "postSlope": float(beta_u[1]+beta_u[3]), "slopeChange": float(beta_u[3]), "levelShift": float(beta_u[2]), "significant": p_value < .1}

def retained_scale_rows(scale_granger, selected_imf):
    """Return only selected-scale factors that pass the Granger gate."""
    return [row for row in scale_granger if row["imf"] == selected_imf and bool(row["significant"])]

def select_main_scale_indices(scores, scale_granger, ratio=SELECTED_SCALE_SCORE_RATIO, limit=2):
    """Select one or two dominant IMFs, prioritising scales with GPRD evidence."""
    numeric = np.asarray(scores, dtype=float)
    finite = np.where(np.isfinite(numeric), numeric, -np.inf)
    if finite.size == 0 or not np.isfinite(finite).any():
        raise ValueError("No finite main-scale selection score was available")
    gprd_scales = {
        int(str(row["imf"])[3:]) - 1
        for row in scale_granger
        if row.get("id") == "GPRD"
        and bool(row.get("significant"))
        and re.fullmatch(r"IMF\d+", str(row.get("imf", "")))
    }
    pool = sorted(index for index in gprd_scales if 0 <= index < len(finite)) or list(range(len(finite)))
    ranked = sorted(pool, key=lambda index: finite[index], reverse=True)
    strongest = ranked[0]
    top_score = finite[strongest]
    retained = [
        index for index in ranked
        if (top_score <= 0 and index == strongest) or (top_score > 0 and finite[index] >= top_score * ratio)
    ]
    return sorted((retained or [strongest])[:max(1, int(limit))])

def align_on_target_dates(target_rows, factor_rows, start, end):
    dates = [stamp for stamp, _ in target_rows if start <= stamp <= end]
    target_map = dict(target_rows); arrays = []
    for rows in factor_rows:
        stamps = np.asarray([stamp for stamp, _ in rows]); values = np.asarray([value for _, value in rows], dtype=float)
        positions = np.searchsorted(stamps, np.asarray(dates), side="right")-1
        arrays.append(np.asarray([values[position] if position >= 0 else np.nan for position in positions]))
    keep = np.ones(len(dates), dtype=bool)
    for values in arrays: keep &= np.isfinite(values)
    clean_dates = [stamp for stamp, good in zip(dates, keep) if good]
    target = np.asarray([target_map[stamp] for stamp in clean_dates], dtype=float)
    factors = [values[keep] for values in arrays]
    return clean_dates, target, factors

def net_impact(payload):
    target = payload.get("target", "EIA-BRENT"); custom_rows = {str(item.get("id")): [(str(point["date"]),float(point["value"])) for point in item.get("points",[]) if point.get("date") and np.isfinite(float(point.get("value",np.nan)))] for item in payload.get("customSeries",[]) if item.get("id")}
    custom_meta = {str(item.get("id")): (str(item.get("id")),str(item.get("nameZh") or item.get("name") or item.get("id")),str(item.get("nameEn") or item.get("name") or item.get("id"))) for item in payload.get("customSeries",[]) if item.get("id")}
    valid = lambda sid: sid in SERIES or re.fullmatch(r"FRED-[A-Z0-9_]+",sid) or sid in custom_rows
    meta = lambda sid: custom_meta.get(sid,series_meta(sid))
    selected = [x for x in payload.get("factors", []) if valid(x) and x != target]
    if not selected: selected = ["GPRD", "FRED-PETINV", "FRED-DTWEXBGS", "FRED-DGS10", "FRED-INDPRO", "FRED-T10YIE", "FRED-VIXCLS", "FRED-HENRYHUB"]
    selected = selected[:24]; estimation_start = str(payload.get("estimationStart") or payload.get("start") or "2018-11-07"); event_start = str(payload.get("eventStart") or "2020-01-01"); event_end = str(payload.get("eventEnd") or payload.get("end") or date.today()); max_lag = min(max(int(payload.get("maxLag", 3)), 1), 6); count = min(max(int(payload.get("imf", 5)), 3), 8)
    ids = [target]+selected
    def fetch(sid): return custom_rows[sid] if sid in custom_rows else load_series(sid,estimation_start)
    with ThreadPoolExecutor(max_workers=min(8,len(ids))) as pool: loaded = list(pool.map(fetch,ids))
    common,y_level,factor_levels = align_on_target_dates(loaded[0],loaded[1:],estimation_start,event_end)
    if len(common) < 120: raise ValueError(f"Only {len(common)} aligned trading-day observations; at least 120 are required")
    event_positions = [index for index,stamp in enumerate(common) if event_start <= stamp <= event_end]
    if len(event_positions) < 5: raise ValueError("Event window has fewer than five aligned trading-day observations")
    y = np.diff(y_level); factor_changes = []
    for arr in factor_levels: factor_changes.append(np.diff(np.log(arr)) if np.all(arr > 0) else np.diff(arr))
    x_raw = np.column_stack(factor_changes); means, scales = x_raw.mean(0), x_raw.std(0); scales[scales == 0] = 1; x = (x_raw-means)/scales
    design = np.column_stack([np.ones(len(y)), x]); beta = np.linalg.lstsq(design, y, rcond=None)[0]; contributions = beta[1:]*x[-1]; fitted = design@beta; r2 = float(1-np.sum((y-fitted)**2)/max(np.sum((y-y.mean())**2), 1e-12))
    alpha = float(payload.get("alpha", .05)); granger = []
    for index, sid in enumerate(selected):
        item_meta = meta(sid); _, lag, statistic, p_value = granger_test(y, x[:, index], max_lag); granger.append({"id": sid, "nameZh": item_meta[1], "nameEn": item_meta[2], "lag": lag, "fStatistic": statistic, "pValue": p_value, "significant": p_value < alpha})
    modes, freq = decompose(y_level,count); component_dates = common
    components = [{"imf": f"IMF{i+1}", "channelZh": CHANNELS_ZH[i] if i < 5 else "长期趋势", "channelEn": CHANNELS_EN[i] if i < 5 else "Long-run trend", "centerFrequency": float(freq[i]), "volatilityShare": float(np.var(modes[i])/max(np.var(y_level), 1e-12)*100), "points": [{"date": d, "value": float(v)} for d, v in zip(component_dates[-180:], modes[i, -180:])]} for i in range(count)]
    factor_standardized = [(arr-arr.mean())/max(arr.std(),1e-12) for arr in factor_levels]
    factor_modes = [decompose(arr,count)[0] for arr in factor_standardized]
    event_ranges = np.asarray([np.ptp(mode[event_positions]) for mode in modes]); variances = np.asarray([np.var(mode,ddof=1) for mode in modes]); correlations = np.asarray([abs(np.corrcoef(y_level,mode)[0,1]) for mode in modes]); scores = variances/max(variances.sum(),1e-12)*100+event_ranges/max(event_ranges.sum(),1e-12)*100+correlations*100
    scale_granger = []
    for factor_index, sid in enumerate(selected):
        item_meta = meta(sid)
        for scale_index in range(count):
            _, lag, statistic, p_value = granger_test(modes[scale_index],factor_modes[factor_index][scale_index],max_lag)
            scale_granger.append({"id": sid, "nameZh": item_meta[1], "nameEn": item_meta[2], "imf": f"IMF{scale_index+1}", "lag": lag, "fStatistic": statistic, "pValue": p_value, "significant": p_value < alpha})
    selected_indices = select_main_scale_indices(scores, scale_granger)
    selected_imf = "+".join(f"IMF{index+1}" for index in selected_indices)
    selected_scale = modes[selected_indices].sum(axis=0)
    selected_scale_granger = []
    for factor_index, sid in enumerate(selected):
        item_meta = meta(sid)
        factor_scale = factor_modes[factor_index][selected_indices].sum(axis=0)
        _, lag, statistic, p_value = granger_test(selected_scale, factor_scale, max_lag)
        selected_scale_granger.append({"id": sid, "nameZh": item_meta[1], "nameEn": item_meta[2], "imf": selected_imf, "lag": lag, "fStatistic": statistic, "pValue": p_value, "significant": p_value < alpha})
    retained_rows = retained_scale_rows(selected_scale_granger, selected_imf)
    retained_ids = [row["id"] for row in retained_rows]
    if not retained_ids:
        raise ValueError(f"No explanatory variable passed the selected-scale Granger gate at alpha={alpha:.3f}; FEVD was not run")
    retained_indices = [selected.index(sid) for sid in retained_ids]
    selected_scales = [{"id": row["id"], "nameZh": row["nameZh"], "nameEn": row["nameEn"], "imf": row["imf"], "pValue": row["pValue"]} for row in retained_rows]
    event_scale = selected_scale[event_positions]; minimum_local = int(np.argmin(event_scale)); maximum_local = int(np.argmax(event_scale)); minimum_index = event_positions[minimum_local]; maximum_index = event_positions[maximum_local]; horizon = abs(maximum_index-minimum_index)
    if horizon < 1: raise ValueError("Selected-scale extrema occur on the same trading day; FEVD h cannot be determined")
    net_effect = float(event_scale[maximum_local]-event_scale[minimum_local]); original_event = y_level[event_positions]; original_response = float(original_event.max()-original_event.min()); response_share = net_effect/original_response*100 if abs(original_response)>1e-12 else float("nan")
    selected_factor_modes = [factor_modes[index][selected_indices].sum(axis=0) for index in retained_indices]
    var_data = np.column_stack([np.diff(selected_scale)]+[np.diff(values) for values in selected_factor_modes])
    var_lag, fevd_matrix = orthogonal_fevd(var_data, horizon, max_lag)
    external_total = max(float(fevd_matrix[0,1:].sum()),1e-12)
    fevd = [{"id": sid, "nameZh": meta(sid)[1], "nameEn": meta(sid)[2], "share": float(fevd_matrix[0,index+1]*100), "externalWeight": float(fevd_matrix[0,index+1]/external_total*100), "absoluteImpact": float(net_effect*fevd_matrix[0,index+1]/external_total)} for index,sid in enumerate(retained_ids)]
    own_share = float(fevd_matrix[0, 0]*100)
    window = min(max(int(payload.get("window", 120)), 48),len(y)); rolling = []; rolling_fevd = []; first_event_end = max(window,event_positions[0])
    for end in range(first_event_end,len(y)+1):
        local_x, local_y = x[end-window:end,retained_indices], y[end-window:end]; local_design = np.column_stack([np.ones(window), local_x]); local_beta = np.linalg.lstsq(local_design, local_y, rcond=None)[0]
        rolling.append({"date": common[end], "observed": float(local_y[-1]), "fitted": float(local_design[-1]@local_beta)})
        if (end-first_event_end) % 5 == 0 or end == len(y):
            local_lag, local_fevd = orthogonal_fevd(np.column_stack([local_y, local_x]),horizon,min(max_lag,3))
            rolling_fevd.append({"date": common[end], "externalShare": float((1-local_fevd[0,0])*100), "ownShare": float(local_fevd[0,0]*100), "lag": local_lag})
    drivers = [{"id":sid,"nameZh":meta(sid)[1],"nameEn":meta(sid)[2],"impact":float(contributions[index]),"coefficient":float(beta[index+1])} for sid,index in zip(retained_ids,retained_indices)]; drivers.sort(key=lambda row: abs(row["impact"]),reverse=True)
    optimal_break = segmented_break_test(selected_scale,common); fixed_break = fixed_break_test(selected_scale,common,event_start)
    analytic = analytic_signal(selected_scale); phase = np.unwrap(np.angle(analytic)); instantaneous_frequency = np.abs(np.diff(phase))/(2*np.pi)
    hht = [{"date": common[index+1], "frequency": float(value), "period": float(1/max(value,1e-9))} for index,value in enumerate(instantaneous_frequency) if np.isfinite(value)][-360:]
    scale_effect = {"selectedScale":selected_imf,"minimumDate":common[minimum_index],"minimumValue":float(selected_scale[minimum_index]),"maximumDate":common[maximum_index],"maximumValue":float(selected_scale[maximum_index]),"tradingDayInterval":horizon,"calendarDayInterval":abs((date.fromisoformat(common[maximum_index])-date.fromisoformat(common[minimum_index])).days),"netEffect":net_effect,"originalResponse":original_response,"shareInOriginalResponse":response_share}
    estimation_candidates = [stamp for stamp in common if stamp < event_start]
    if not estimation_candidates: raise ValueError("Estimation window must end before the event window begins")
    return {"mode":"verified-live","method":"Target-calendar alignment; VMD and HHT; one-or-two main-scale selection; selected-scale Granger significance gate; extrema-selected h; Cholesky-orthogonal rolling VAR-FEVD using retained factors only; fixed and optimal structural-break diagnostics","asOf":common[-1],"target":target,"observations":len(common),"estimationWindow":{"start":estimation_start,"end":max(estimation_candidates)},"eventWindow":{"start":event_start,"end":event_end},"rSquared":r2,"drivers":drivers,"granger":granger,"scaleGranger":scale_granger,"selectedScaleGranger":selected_scale_granger,"selectedScales":selected_scales,"components":components,"hht":hht,"scaleEffect":scale_effect,"fevd":fevd,"fevdOwnShare":own_share,"fevdHorizon":horizon,"varLag":var_lag,"rolling":rolling[-180:],"rollingFevd":rolling_fevd[-120:],"breakTest":{"fixed":fixed_break,"optimal":optimal_break},"sources":[{"id":sid,"providerId":meta(sid)[0],"nameZh":meta(sid)[1],"nameEn":meta(sid)[2]} for sid in ids]}

class handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self): self.send_json(200, {"ok": True, "service": "oil-research-models", "mode": "verified-live"})
    def do_POST(self):
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}"); path = urlparse(self.path).path.rstrip("/"); action = payload.get("action") or path.rsplit("/", 1)[-1]; actions = {"forecast": forecast, "risk": risk, "decomposition": decomposition, "net-impact": net_impact}; result = actions[action](payload) if action in actions else None
            self.send_json(200, result) if result else self.send_json(404, {"error": "Unknown model endpoint"})
        except Exception as exc: self.send_json(500, {"error": "Model execution failed", "detail": str(exc)[:500]})
