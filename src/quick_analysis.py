"""Quick-mode helpers for IMF interpretation and independent variable taxonomy."""

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


VARIABLE_PAPER_IMF_GROUPS: "OrderedDict[str, tuple[str, ...]]" = OrderedDict(
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


VARIABLE_ECONOMIC_CATEGORIES: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            "geopolitical_policy_risk",
            {
                "label_en": "Geopolitical & policy risk",
                "label_zh": "地缘政治与政策风险",
                "explanation_en": "Conflict, sanctions, trade policy and policy uncertainty.",
                "explanation_zh": "冲突、制裁、贸易政策及政策不确定性。",
                "variables": ("GPRD", "EPU", "TPU", "EMV", "SanctionsRisk", "OilPolicyUncertainty"),
                "keywords": (
                    "geopolit", "conflict", "war", "sanction", "policy uncertainty",
                    "trade policy", "embargo", "shipping disruption", "opec policy",
                ),
            },
        ),
        (
            "market_risk_sentiment",
            {
                "label_en": "Market risk sentiment",
                "label_zh": "市场风险偏好",
                "explanation_en": "Volatility, stress and rapid changes in risk appetite.",
                "explanation_zh": "波动率、市场压力与风险偏好的快速变化。",
                "variables": ("OVX", "VIX", "MOVE", "STLFSI", "HighYieldSpread"),
                "keywords": (
                    "volatility", "fear", "stress", "risk premium", "uncertainty index",
                    "financial stress", "credit spread", "option implied volatility",
                ),
            },
        ),
        (
            "financial_assets_hedging",
            {
                "label_en": "Financial assets & hedging",
                "label_zh": "金融资产与避险",
                "explanation_en": "Equity pricing, safe-haven demand and cross-asset allocation.",
                "explanation_zh": "股票定价、避险需求与跨资产配置。",
                "variables": ("Gold", "Silver", "SP500", "Nasdaq", "MSCIWorld", "CommodityIndex"),
                "keywords": (
                    "stock market", "equity", "gold", "silver", "safe haven",
                    "s&p 500", "nasdaq", "asset allocation", "commodity index",
                ),
            },
        ),
        (
            "crude_benchmarks_expectations",
            {
                "label_en": "Crude benchmarks & expectations",
                "label_zh": "原油基准与价格预期",
                "explanation_en": "Spot and futures benchmarks that transmit price discovery.",
                "explanation_zh": "承担价格发现功能的原油现货与期货基准。",
                "variables": ("WTI", "Brent", "ShanghaiSC", "DubaiCrude", "OPECBasket", "CrudeCurveSlope"),
                "keywords": (
                    "crude oil price", "crude oil future", "brent", "west texas", "wti",
                    "dubai crude", "opec basket", "term structure", "crack spread", "calendar spread",
                ),
            },
        ),
        (
            "physical_supply",
            {
                "label_en": "Physical supply & production",
                "label_zh": "实物供给与生产",
                "explanation_en": "Extraction, output capacity, imports, exports and transport flows.",
                "explanation_zh": "开采、产能、进出口及运输流量。",
                "variables": (
                    "USCrudeProduction", "OPECProduction", "RigCount", "CrudeImports",
                    "CrudeExports", "FreightRates", "PipelineFlows", "SpareCapacity",
                ),
                "keywords": (
                    "production", "supply", "output", "rig", "import", "export", "pipeline",
                    "field production", "spare capacity", "tanker", "freight", "oil supply",
                ),
            },
        ),
        (
            "inventories_refining",
            {
                "label_en": "Inventories, refining & products",
                "label_zh": "库存、炼化与成品油",
                "explanation_en": "Stock buffers, refinery activity and refined-product markets.",
                "explanation_zh": "库存缓冲、炼厂活动与成品油市场。",
                "variables": (
                    "CrudeStocks", "SPRStocks", "GasolineStocks", "DistillateStocks",
                    "RefineryUtilization", "RefineryInputs", "Gasoline", "HeatingOil", "ShanghaiFU",
                ),
                "keywords": (
                    "stock", "storage", "inventory", "refin", "gasoline", "distillate",
                    "heating oil", "strategic petroleum reserve", "refinery utilization", "product supplied",
                ),
            },
        ),
        (
            "real_economy_demand",
            {
                "label_en": "Real economy & energy demand",
                "label_zh": "实体经济与能源需求",
                "explanation_en": "Industrial activity, consumption, mobility and end-use demand.",
                "explanation_zh": "工业活动、消费、出行与终端能源需求。",
                "variables": (
                    "Copper", "INDPRO", "GlobalPMI", "RetailSales", "VehicleMiles",
                    "AirTraffic", "PetroleumDemand", "ChinaIndustrialProduction",
                ),
                "keywords": (
                    "consumption", "demand", "industrial production", "gdp", "sales", "freight",
                    "copper", "pmi", "vehicle miles", "air traffic", "product supplied", "mobility",
                ),
            },
        ),
        (
            "monetary_financial_conditions",
            {
                "label_en": "Monetary & financial conditions",
                "label_zh": "货币与金融条件",
                "explanation_en": "Policy rates, yields, liquidity and financing conditions.",
                "explanation_zh": "政策利率、国债收益率、流动性与融资条件。",
                "variables": (
                    "TNote10Y", "US2Y", "FedFunds", "RealYield10Y", "InflationExpectation",
                    "CreditSpread", "MoneySupply", "FinancialConditions",
                ),
                "keywords": (
                    "interest rate", "yield", "treasury", "federal funds", "liquidity", "credit",
                    "real yield", "inflation expectation", "money supply", "financial conditions",
                ),
            },
        ),
        (
            "currency_pricing",
            {
                "label_en": "Currency & cross-border pricing",
                "label_zh": "汇率与跨境定价",
                "explanation_en": "Dollar valuation and exchange-rate transmission into commodity prices.",
                "explanation_zh": "美元估值及汇率向大宗商品价格的传导。",
                "variables": ("DollarIndex", "CNYUSD", "EURUSD", "EmergingMarketFX", "TradeWeightedDollar"),
                "keywords": (
                    "exchange rate", "currency", "dollar", "foreign exchange", "broad dollar",
                    "trade weighted", "renminbi", "euro", "emerging market currency",
                ),
            },
        ),
        (
            "substitute_energy",
            {
                "label_en": "Substitute energy & relative costs",
                "label_zh": "替代能源与相对成本",
                "explanation_en": "Natural gas, coal and power prices that alter fuel substitution.",
                "explanation_zh": "影响燃料替代的天然气、煤炭与电力价格。",
                "variables": ("NaturalGas", "CoalPrice", "PowerPrice", "LNGPrice", "CarbonPrice"),
                "keywords": (
                    "natural gas", "coal", "electricity", "power price", "renewable",
                    "fuel switching", "lng", "carbon allowance", "alternative fuel",
                ),
            },
        ),
        (
            "other_indicators",
            {
                "label_en": "Other indicators",
                "label_zh": "其他指标",
                "explanation_en": "User-added indicators not yet assigned to a primary economic category.",
                "explanation_zh": "尚未归入主要经济类别的用户新增指标。",
                "variables": (),
                "keywords": (),
            },
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
    """Return the legacy paper IMF channel used only by the warning model."""
    value = str(variable)
    for imf, variables in VARIABLE_PAPER_IMF_GROUPS.items():
        if value in variables:
            return imf
    return "IMF1"


def variable_economic_category(variable: str, metadata: dict[str, Any] | None = None) -> str:
    """Classify a variable independently from the five post-decomposition IMFs."""
    value = str(variable)
    metadata = metadata or {}
    explicit = str(metadata.get("economic_category", "")).strip()
    if explicit in VARIABLE_ECONOMIC_CATEGORIES:
        return explicit
    for category, details in VARIABLE_ECONOMIC_CATEGORIES.items():
        if value in details.get("variables", ()):
            return category
    searchable = " ".join(
        str(metadata.get(field, "")) for field in ("title", "description", "FullName", "Note")
    ).lower()
    searchable = f"{value.lower()} {searchable}"
    if any(term in searchable for term in ("industrial production", "retail sales", "real gross domestic")):
        return "real_economy_demand"
    if any(term in searchable for term in ("crude oil stock", "petroleum stock", "oil inventory")):
        return "inventories_refining"
    for category, details in VARIABLE_ECONOMIC_CATEGORIES.items():
        if any(keyword in searchable for keyword in details.get("keywords", ())):
            return category
    return "other_indicators"


def group_variables(
    variables: Iterable[str],
    metadata: dict[str, dict[str, Any]] | None = None,
) -> "OrderedDict[str, list[str]]":
    """Group variables by economic meaning, separately from IMF interpretation."""
    grouped: "OrderedDict[str, list[str]]" = OrderedDict(
        (category, []) for category in VARIABLE_ECONOMIC_CATEGORIES
    )
    metadata = metadata or {}
    for variable in dict.fromkeys(str(item) for item in variables):
        grouped[variable_economic_category(variable, metadata.get(variable))].append(variable)
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
    metadata: dict[str, dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Aggregate variable FEVD weights into independent variable categories."""
    frame = contribution_weights.copy() if isinstance(contribution_weights, pd.DataFrame) else pd.DataFrame()
    if frame.empty or "ExternalVariable" not in frame.columns:
        return pd.DataFrame(columns=["Target", "Category", "Channel", "WeightPercent"])
    weight_column = (
        "ExternalRelativeWeightPercent"
        if "ExternalRelativeWeightPercent" in frame.columns
        else "ExternalRelativeWeight"
    )
    metadata = metadata or {}
    frame["Category"] = frame["ExternalVariable"].astype(str).map(
        lambda variable: variable_economic_category(variable, metadata.get(variable))
    )
    frame["WeightPercent"] = pd.to_numeric(frame.get(weight_column), errors="coerce").fillna(0.0)
    target_column = "Target" if "Target" in frame.columns else None
    group_columns = [column for column in [target_column, "Category"] if column]
    summary = frame.groupby(group_columns, as_index=False)["WeightPercent"].sum()
    targets = (
        summary["Target"].dropna().astype(str).unique().tolist()
        if "Target" in summary.columns
        else [""]
    )
    complete_rows: list[dict[str, Any]] = []
    label_key = "label_zh" if language == "zh" else "label_en"
    for target in targets:
        for category, details in VARIABLE_ECONOMIC_CATEGORIES.items():
            selector = summary["Category"].eq(category)
            if "Target" in summary.columns:
                selector &= summary["Target"].astype(str).eq(target)
            values = summary.loc[selector, "WeightPercent"]
            complete_rows.append(
                {
                    "Target": target,
                    "Category": category,
                    "Channel": details[label_key],
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
