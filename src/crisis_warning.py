"""Five-day oil-crisis risk-ranking helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import recall_score

from src.quick_analysis import IMF_CHANNELS, variable_group


WARNING_HORIZON_DAYS = 5
WARNING_RANDOM_SEED = 20260729
FALSE_ALERT_BUDGET_PER_YEAR = 4.0


@dataclass
class CrisisWarningResult:
    latest_date: pd.Timestamp
    risk_score: float
    risk_percentile: float
    alert_threshold: float
    alert: bool
    risk_history: pd.DataFrame
    channel_scores: pd.DataFrame
    event_catalog: pd.DataFrame
    model_note: str


def _rolling_autocorr(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).corr(series.shift(1))


def _expanding_threshold(series: pd.Series, quantile: float, min_history: int) -> pd.Series:
    return series.shift(1).expanding(min_periods=min_history).quantile(quantile)


def _choose_threshold(y: np.ndarray, scores: np.ndarray, years: float) -> float:
    candidates = np.unique(np.quantile(scores, np.linspace(0.50, 0.995, 120)))
    best_recall = -1.0
    best_precision = -1.0
    best_threshold = 0.80
    for threshold in candidates:
        predicted = scores >= threshold
        false_alerts_per_year = float(np.sum(predicted & (y == 0))) / max(years, 1.0)
        if false_alerts_per_year > FALSE_ALERT_BUDGET_PER_YEAR:
            continue
        recall = recall_score(y, predicted, zero_division=0)
        precision = float(np.sum(predicted & (y == 1)) / max(np.sum(predicted), 1))
        if (recall, precision) > (best_recall, best_precision):
            best_recall, best_precision, best_threshold = recall, precision, float(threshold)
    return best_threshold


def _rank_to_unit_interval(values: np.ndarray) -> np.ndarray:
    series = pd.Series(values)
    return series.rank(method="average", pct=True).to_numpy(dtype=float)


def prepare_warning_features(
    data: pd.DataFrame,
    price_column: str = "Brent",
) -> tuple[pd.DataFrame, list[str], pd.DataFrame]:
    """Build leakage-aware fast-clock features and expanding-tail crisis labels."""
    if "Date" not in data.columns or price_column not in data.columns:
        raise ValueError(f"Warning data must contain Date and {price_column}.")
    frame = data.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date", keep="last")
    frame = frame.set_index("Date")
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    price = frame[price_column].where(frame[price_column] > 0)
    if price.notna().sum() < 400:
        raise ValueError("At least 400 positive price observations are required for crisis warning.")
    price = price.interpolate(limit=3).ffill(limit=3)
    log_price = np.log(price)
    r1 = log_price.diff()
    frame["oil_r1"] = r1
    frame["oil_r5"] = log_price.diff(5)
    frame["oil_r20"] = log_price.diff(20)
    frame["oil_r60"] = log_price.diff(60)
    frame["rv5"] = r1.rolling(5).std(ddof=0) * np.sqrt(252)
    frame["rv20"] = r1.rolling(20).std(ddof=0) * np.sqrt(252)
    frame["rv60"] = r1.rolling(60).std(ddof=0) * np.sqrt(252)
    frame["drawdown20"] = price / price.rolling(20).max() - 1
    frame["ac1_20"] = _rolling_autocorr(r1, 20)
    frame["skew20"] = r1.rolling(20).skew()
    frame["kurt60"] = r1.rolling(60).kurt()
    frame["variance_ratio"] = r1.rolling(20).var(ddof=0) / r1.rolling(120).var(ddof=0)

    market_features: list[str] = []
    for variable in [
        "WTI",
        "OVX",
        "VIX",
        "GPRD",
        "EPU",
        "TPU",
        "EMV",
        "Gasoline",
        "HeatingOil",
        "CrudeStocks",
        "ShanghaiSC",
        "NaturalGas",
        "DollarIndex",
        "TNote10Y",
        "Copper",
    ]:
        if variable not in frame.columns or variable == price_column:
            continue
        series = frame[variable].interpolate(limit=5).ffill(limit=5)
        transformed = np.log(series.where(series > 0)).diff(5)
        if transformed.notna().sum() < 100:
            transformed = series.diff(5)
        feature_name = f"{variable}_change5"
        frame[feature_name] = transformed
        rolling_mean = series.rolling(60).mean()
        rolling_std = series.rolling(60).std(ddof=0).replace(0, np.nan)
        z_name = f"{variable}_z60"
        frame[z_name] = (series - rolling_mean) / rolling_std
        market_features.extend([feature_name, z_name])

    min_history = min(1260, max(252, int(price.notna().sum() * 0.30)))
    upper = _expanding_threshold(frame["oil_r20"], 0.975, min_history)
    lower = _expanding_threshold(frame["oil_r20"], 0.025, min_history)
    vol_upper = _expanding_threshold(frame["rv20"], 0.975, min_history)
    crisis_type = np.zeros(len(frame), dtype=np.int8)
    crisis_type[frame["oil_r20"].to_numpy() > upper.to_numpy()] = 1
    crisis_type[frame["oil_r20"].to_numpy() < lower.to_numpy()] = 2
    volatility_mask = (frame["rv20"].to_numpy() > vol_upper.to_numpy()) & (crisis_type == 0)
    crisis_type[volatility_mask] = 3
    crisis_any = pd.Series(crisis_type > 0, index=frame.index)
    prior_crisis = crisis_any.shift(1).rolling(20, min_periods=1).max().fillna(0)
    onset = crisis_any & prior_crisis.eq(0)
    frame["event_onset"] = onset.astype(int)
    frame["event_type"] = np.where(onset, crisis_type, 0)

    onset_positions = np.flatnonzero(frame["event_onset"].to_numpy(dtype=int) == 1)
    target = np.zeros(len(frame), dtype=np.int8)
    for position in range(len(frame)):
        next_event = np.searchsorted(onset_positions, position + 1, side="left")
        if next_event < len(onset_positions) and onset_positions[next_event] - position <= WARNING_HORIZON_DAYS:
            target[position] = 1
    frame["target_h5"] = target

    oil_feature_columns = [
        "oil_r1",
        "oil_r5",
        "oil_r20",
        "oil_r60",
        "rv5",
        "rv20",
        "rv60",
        "drawdown20",
        "ac1_20",
        "skew20",
        "kurt60",
        "variance_ratio",
    ]
    feature_columns = [*oil_feature_columns, *market_features]
    frame = frame.replace([np.inf, -np.inf], np.nan)
    usable_features = [
        column
        for column in feature_columns
        if column in frame.columns and frame[column].notna().sum() >= max(150, int(len(frame) * 0.35))
    ]
    required_oil_features = [
        column for column in oil_feature_columns if column in usable_features
    ]
    optional_market_features = [
        column for column in usable_features if column not in required_oil_features
    ]
    model_frame = frame.dropna(
        subset=required_oil_features + ["target_h5"]
    ).copy()
    if optional_market_features:
        # Market series have different calendars and publication lags. Forward
        # filling uses only information already available at each date; any
        # leading gap is encoded as a neutral transformed signal instead of
        # deleting otherwise valid oil-price observations.
        model_frame[optional_market_features] = (
            model_frame[optional_market_features].ffill(limit=5).fillna(0.0)
        )
    event_names = {1: "Upward spike", 2: "Downward crash", 3: "Volatility dislocation"}
    event_catalog = frame.loc[frame["event_onset"].eq(1), ["event_type", price_column, "oil_r20", "rv20"]].copy()
    event_catalog.insert(0, "Date", event_catalog.index)
    event_catalog["Event"] = event_catalog["event_type"].map(event_names)
    return model_frame, usable_features, event_catalog.reset_index(drop=True)


def run_five_day_warning(
    data: pd.DataFrame,
    price_column: str = "Brent",
) -> CrisisWarningResult:
    """Run expanding-year out-of-sample scoring and a latest-date five-day risk ranking."""
    frame, features, event_catalog = prepare_warning_features(data, price_column=price_column)
    if len(features) < 5 or len(frame) < 500:
        raise ValueError("The aligned data do not contain enough warning features or observations.")
    if frame["target_h5"].nunique() < 2:
        raise ValueError("The expanding-tail labels contain only one class; warning model cannot be trained.")

    records: list[dict[str, Any]] = []
    years = sorted(int(year) for year in frame.index.year.unique())
    for year in years:
        test_mask = frame.index.year == year
        train_mask = frame.index.year < year
        if int(train_mask.sum()) < 500 or int(test_mask.sum()) == 0:
            continue
        y_train = frame.loc[train_mask, "target_h5"].to_numpy(dtype=int)
        if len(np.unique(y_train)) < 2:
            continue
        model = RandomForestClassifier(
            n_estimators=350,
            max_depth=8,
            min_samples_leaf=10,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=WARNING_RANDOM_SEED,
        )
        model.fit(frame.loc[train_mask, features], y_train)
        probabilities = model.predict_proba(frame.loc[test_mask, features])[:, 1]
        ranked = _rank_to_unit_interval(probabilities)
        for date_value, probability, score, actual in zip(
            frame.index[test_mask],
            probabilities,
            ranked,
            frame.loc[test_mask, "target_h5"].to_numpy(dtype=int),
        ):
            records.append(
                {
                    "Date": date_value,
                    "RiskProbabilityUncalibrated": float(probability),
                    "RiskScore": float(score * 100.0),
                    "ActualCrisisWithin5Days": int(actual),
                }
            )
    history = pd.DataFrame(records)
    if not history.empty:
        history["RiskScore"] = (
            history["RiskProbabilityUncalibrated"].rank(method="average", pct=True) * 100.0
        )

    latest_row = frame.iloc[[-1]]
    training = frame.iloc[:-WARNING_HORIZON_DAYS].copy()
    y_training = training["target_h5"].to_numpy(dtype=int)
    latest_model = RandomForestClassifier(
        n_estimators=500,
        max_depth=8,
        min_samples_leaf=10,
        max_features="sqrt",
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=WARNING_RANDOM_SEED,
    )
    latest_model.fit(training[features], y_training)
    latest_probability = float(latest_model.predict_proba(latest_row[features])[:, 1][0])
    reference_probabilities = latest_model.predict_proba(training[features])[:, 1]
    latest_percentile = float((reference_probabilities <= latest_probability).mean() * 100.0)

    if history.empty:
        threshold_score = 90.0
    else:
        history_years = max(
            (history["Date"].max() - history["Date"].min()).days / 365.25,
            1.0,
        )
        threshold_score = _choose_threshold(
            history["ActualCrisisWithin5Days"].to_numpy(dtype=int),
            history["RiskScore"].to_numpy(dtype=float) / 100.0,
            history_years,
        ) * 100.0

    importance = pd.DataFrame(
        {
            "Feature": features,
            "Importance": latest_model.feature_importances_,
        }
    )
    feature_variable = importance["Feature"].str.extract(
        r"^(WTI|OVX|VIX|GPRD|EPU|TPU|EMV|Gasoline|HeatingOil|CrudeStocks|ShanghaiSC|NaturalGas|DollarIndex|TNote10Y|Copper)",
        expand=False,
    )
    fallback = pd.Series("OVX", index=importance.index)
    importance["Variable"] = feature_variable.fillna(fallback)
    importance["IMF"] = importance["Variable"].map(variable_group)
    channel_scores = importance.groupby("IMF", as_index=False)["Importance"].sum()
    channel_scores = pd.DataFrame({"IMF": list(IMF_CHANNELS)}).merge(channel_scores, on="IMF", how="left").fillna(0)
    channel_scores["ImportancePercent"] = (
        channel_scores["Importance"] / max(channel_scores["Importance"].sum(), 1e-12) * 100.0
    )
    channel_scores["ChannelEN"] = channel_scores["IMF"].map(
        {imf: details["channel_en"] for imf, details in IMF_CHANNELS.items()}
    )
    channel_scores["ChannelZH"] = channel_scores["IMF"].map(
        {imf: details["channel_zh"] for imf, details in IMF_CHANNELS.items()}
    )

    return CrisisWarningResult(
        latest_date=pd.Timestamp(latest_row.index[-1]),
        risk_score=latest_percentile,
        risk_percentile=latest_percentile,
        alert=latest_percentile >= threshold_score,
        alert_threshold=float(threshold_score),
        risk_history=history,
        channel_scores=channel_scores,
        event_catalog=event_catalog,
        model_note=(
            "Five-day fast-clock Random Forest with expanding-tail oil stress labels. "
            "The displayed score is a historical risk percentile for ranking, not a calibrated event probability."
        ),
    )
