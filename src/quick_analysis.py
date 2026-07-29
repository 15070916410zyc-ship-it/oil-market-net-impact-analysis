"""Quick-mode helpers for paper-aligned five-channel net-impact analysis."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable

import numpy as np
import pandas as pd


QUICK_ESTIMATION_TRADING_DAYS = 504

IMF_CHANNELS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        (
            "IMF1",
            {
                "channel_en": "Speculation",
                "channel_zh": "投机",
                "explanation_en": "Investor speculation and short-run risk repricing.",
                "explanation_zh": "投资者投机与短期风险重定价。",
            },
        ),
        (
            "IMF2",
            {
                "channel_en": "OPEC+ production announcements",
                "channel_zh": "OPEC+ 产量公告",
                "explanation_en": "OPEC+ production announcements and coordinated output policy.",
                "explanation_zh": "OPEC+ 产量公告与协同产量政策。",
            },
        ),
        (
            "IMF3",
            {
                "channel_en": "Inventories",
                "channel_zh": "库存",
                "explanation_en": "Crude-oil and refined-product inventory adjustment.",
                "explanation_zh": "原油及成品油库存调整。",
            },
        ),
        (
            "IMF4",
            {
                "channel_en": "Supply",
                "channel_zh": "供给",
                "explanation_en": "Physical production, transport, refining, and supply disruption.",
                "explanation_zh": "实物生产、运输、炼化与供给中断。",
            },
        ),
        (
            "IMF5",
            {
                "channel_en": "Demand",
                "channel_zh": "需求",
                "explanation_en": "Global activity, consumption, and oil-demand conditions.",
                "explanation_zh": "全球经济活动、消费与原油需求状况。",
            },
        ),
    ]
)


VARIABLE_ECONOMIC_GROUPS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
    [
        (
            "IMF1",
            (
                "GPRD",
                "OVX",
                "VIX",
                "Gold",
                "Silver",
                "SP500",
                "Nasdaq",
                "EPU",
                "TPU",
                "EMV",
            ),
        ),
        (
            "IMF2",
            (
                "WTI",
                "Brent",
            ),
        ),
        (
            "IMF3",
            (
                "Gasoline",
                "HeatingOil",
                "CrudeStocks",
            ),
        ),
        (
            "IMF4",
            (
                "ShanghaiSC",
                "ShanghaiFU",
                "NaturalGas",
            ),
        ),
        (
            "IMF5",
            (
                "DollarIndex",
                "TNote10Y",
                "US2Y",
                "FedFunds",
                "CNYUSD",
                "Copper",
            ),
        ),
    ]
)


def automatic_estimation_window(
    event_start: Any,
    available_start: Any | None = None,
    trading_days: int = QUICK_ESTIMATION_TRADING_DAYS,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return a contiguous pre-event estimation window ending one business day earlier."""
    start = pd.to_datetime(event_start, errors="raise").normalize()
    end = (start - pd.offsets.BDay(1)).normalize()
    requested = pd.bdate_range(end=end, periods=max(1, int(trading_days)))
    estimation_start = pd.Timestamp(requested.min()).normalize()
    available = pd.to_datetime(available_start, errors="coerce")
    if pd.notna(available):
        estimation_start = max(estimation_start, pd.Timestamp(available).normalize())
    if estimation_start > end:
        estimation_start = end
    return estimation_start, end


def variable_group(variable: str) -> str:
    """Return the primary paper channel for a variable."""
    value = str(variable)
    for imf, variables in VARIABLE_ECONOMIC_GROUPS.items():
        if value in variables:
            return imf
    return "IMF1"


def group_variables(variables: Iterable[str]) -> "OrderedDict[str, list[str]]":
    """Group variables once by their primary paper-aligned economic interpretation."""
    grouped: "OrderedDict[str, list[str]]" = OrderedDict((imf, []) for imf in IMF_CHANNELS)
    for variable in dict.fromkeys(str(item) for item in variables):
        grouped[variable_group(variable)].append(variable)
    return grouped


def imf_channel_table(language: str = "zh") -> pd.DataFrame:
    """Return the fixed five-IMF interpretation table used by quick mode."""
    rows: list[dict[str, str]] = []
    use_chinese = language == "zh"
    for imf, details in IMF_CHANNELS.items():
        rows.append(
            {
                "IMF": imf,
                "Channel": details["channel_zh" if use_chinese else "channel_en"],
                "Explanation": details["explanation_zh" if use_chinese else "explanation_en"],
            }
        )
    return pd.DataFrame(rows)


def build_quick_imf_summary(scale_statistics: pd.DataFrame, language: str = "zh") -> pd.DataFrame:
    """Attach the paper's fixed five economic interpretations to IMF diagnostics."""
    base = scale_statistics.copy() if isinstance(scale_statistics, pd.DataFrame) else pd.DataFrame()
    if base.empty:
        return imf_channel_table(language)
    channel_table = imf_channel_table(language)
    output = base.drop(columns=["EconomicInterpretation"], errors="ignore").merge(
        channel_table,
        on="IMF",
        how="left",
    )
    output["EconomicInterpretation"] = output["Explanation"]
    return output


def build_channel_contribution_summary(
    contribution_weights: pd.DataFrame,
    language: str = "zh",
) -> pd.DataFrame:
    """Aggregate variable FEVD weights into the five paper-aligned economic channels."""
    frame = contribution_weights.copy() if isinstance(contribution_weights, pd.DataFrame) else pd.DataFrame()
    if frame.empty or "ExternalVariable" not in frame.columns:
        return pd.DataFrame(columns=["Target", "IMF", "Channel", "WeightPercent"])
    weight_column = (
        "ExternalRelativeWeightPercent"
        if "ExternalRelativeWeightPercent" in frame.columns
        else "ExternalRelativeWeight"
    )
    frame["IMF"] = frame["ExternalVariable"].astype(str).map(variable_group)
    frame["WeightPercent"] = pd.to_numeric(frame.get(weight_column), errors="coerce").fillna(0.0)
    target_column = "Target" if "Target" in frame.columns else None
    group_columns = [column for column in [target_column, "IMF"] if column]
    summary = frame.groupby(group_columns, as_index=False)["WeightPercent"].sum()
    targets = (
        summary["Target"].dropna().astype(str).unique().tolist()
        if "Target" in summary.columns
        else [""]
    )
    complete_rows: list[dict[str, Any]] = []
    channels = imf_channel_table(language).set_index("IMF")
    for target in targets:
        for imf in IMF_CHANNELS:
            selector = summary["IMF"].eq(imf)
            if "Target" in summary.columns:
                selector &= summary["Target"].astype(str).eq(target)
            values = summary.loc[selector, "WeightPercent"]
            complete_rows.append(
                {
                    "Target": target,
                    "IMF": imf,
                    "Channel": channels.loc[imf, "Channel"],
                    "WeightPercent": float(values.sum()) if not values.empty else 0.0,
                }
            )
    output = pd.DataFrame(complete_rows)
    total = output.groupby("Target")["WeightPercent"].transform("sum")
    output["WeightPercent"] = np.where(
        total > 0,
        output["WeightPercent"] / total * 100.0,
        output["WeightPercent"],
    )
    return output
