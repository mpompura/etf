"""Streamlit dashboard for ETF analytics and risk reporting.

The original dashboard in this repository focused on two sheets (Summary and
Holdings).  The new workbook that the user provided contains a rich `ETFs`
sheet with risk, performance, income, and quality metrics.  This script builds
an interactive experience around that sheet so it can run inside a local
Streamlit container (Docker or bare-metal).
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Union

import pandas as pd
import plotly.express as px
import streamlit as st
from openpyxl import load_workbook


st.set_page_config(
    page_title="ETF Lab — Risk & Performance Explorer",
    layout="wide",
    page_icon="📊",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


CANONICAL_COLUMNS: Dict[str, Iterable[str]] = {
    "rank": ["rank"],
    "symbol": ["symbol", "ticker"],
    "fund_name": ["fund name", "fund"],
    "price": ["price"],
    "change_pct": ["change %", "change pct", "change"],
    "asset_class": ["asset class & sub-class", "asset class", "asset class & sub class"],
    "fund_type": ["fund type"],
    "issuer": ["issuer", "provider"],
    "inception_date": ["inception date"],
    "aum": ["aum", "aum ($b)", "aum ($mm)", "aum ($m)", "aum (usd)"],
    "expense_ratio": ["expense ratio", "expense"],
    "quant_rating": ["quant rating"],
    "sa_rating": ["sa analyst ratings", "analyst rating"],
    "perf_1y": ["1y perf", "1y %", "1y perf %", "1 year perf"],
    "perf_3y": ["3y perf", "3 year perf"],
    "return_3y": ["3y total return"],
    "perf_5y": ["5y perf"],
    "return_5y": ["5y total return"],
    "perf_10y": ["10y perf"],
    "return_10y": ["10y total return"],
    "ytd_perf": ["ytd perf", "ytd %"],
    "top10_weight": [
        "% top 10",
        "% top 10 holdings",
        "top 10 holdings",
        "top 10 weight",
    ],
    "holdings_count": ["holdings", "# holdings", "number of holdings"],
    "div_growth_5y": ["div growth 5y"],
    "div_growth_3y": ["div growth 3y"],
    "yield_fwd": ["yield fwd"],
    "yield_ttm": ["yield ttm"],
    "frequency": ["frequency", "distribution frequency"],
    "beta_60m": ["60m beta", "beta"],
    "days_quant": ["days at quant rating"],
}

PERCENT_COLUMNS = {
    "change_pct",
    "perf_1y",
    "perf_3y",
    "return_3y",
    "perf_5y",
    "return_5y",
    "perf_10y",
    "return_10y",
    "ytd_perf",
    "top10_weight",
    "div_growth_5y",
    "div_growth_3y",
    "yield_fwd",
    "yield_ttm",
}


@dataclass
class ColumnMap:
    """Container for column names after cleaning."""

    rank: Optional[str] = None
    symbol: Optional[str] = None
    fund_name: Optional[str] = None
    price: Optional[str] = None
    change_pct: Optional[str] = None
    asset_class: Optional[str] = None
    fund_type: Optional[str] = None
    issuer: Optional[str] = None
    inception_date: Optional[str] = None
    aum: Optional[str] = None
    expense_ratio: Optional[str] = None
    quant_rating: Optional[str] = None
    sa_rating: Optional[str] = None
    perf_1y: Optional[str] = None
    perf_3y: Optional[str] = None
    return_3y: Optional[str] = None
    perf_5y: Optional[str] = None
    return_5y: Optional[str] = None
    perf_10y: Optional[str] = None
    return_10y: Optional[str] = None
    ytd_perf: Optional[str] = None
    top10_weight: Optional[str] = None
    holdings_count: Optional[str] = None
    div_growth_5y: Optional[str] = None
    div_growth_3y: Optional[str] = None
    yield_fwd: Optional[str] = None
    yield_ttm: Optional[str] = None
    frequency: Optional[str] = None
    beta_60m: Optional[str] = None
    days_quant: Optional[str] = None


def _normalize_numeric(series: pd.Series, to_percent: bool = False) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(r"[,$%]", "", regex=True)
        .str.replace(r"[A-Za-z]", "", regex=True)
        .str.strip()
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    if to_percent and numeric.abs().max(skipna=True) > 2:
        numeric = numeric / 100.0
    return numeric


def _find_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lowered = {c.lower().strip(): c for c in df.columns}
    for cand in candidates:
        cand_lower = cand.lower().strip()
        if cand_lower in lowered:
            return lowered[cand_lower]
    return None


def clean_etf_sheet(df: pd.DataFrame) -> tuple[pd.DataFrame, ColumnMap]:
    """Standardize the ETF sheet so downstream logic works with any workbook."""

    df = df.copy()
    colmap = ColumnMap()
    rename_dict: Dict[str, str] = {}

    for canonical, candidates in CANONICAL_COLUMNS.items():
        match = _find_column(df, candidates)
        if match:
            rename_dict[match] = canonical
            setattr(colmap, canonical, canonical)

    df = df.rename(columns=rename_dict)

    for col_name in PERCENT_COLUMNS:
        if col_name in df.columns:
            df[col_name] = _normalize_numeric(df[col_name], to_percent=True)

    numeric_cols = [
        "price",
        "aum",
        "expense_ratio",
        "quant_rating",
        "sa_rating",
        "beta_60m",
        "days_quant",
    ]
    for col_name in numeric_cols:
        if col_name in df.columns:
            df[col_name] = _normalize_numeric(df[col_name], to_percent=False)

    if "aum" in df.columns:
        df["aum_billions"] = df["aum"] / 1_000_000_000

    if "inception_date" in df.columns:
        df["inception_date"] = pd.to_datetime(df["inception_date"], errors="coerce")

    return df, colmap


def _ensure_bytes_buffer(source: Union[str, os.PathLike, io.BytesIO, bytes]) -> tuple[Union[str, os.PathLike, io.BytesIO], Optional[bytes]]:
    """Return an object pandas can read plus raw bytes for fallback."""

    if isinstance(source, (str, os.PathLike)):
        return source, None

    if isinstance(source, bytes):
        buffer = io.BytesIO(source)
        return buffer, source

    if isinstance(source, io.BytesIO):
        raw = source.getvalue()
        return io.BytesIO(raw), raw

    if hasattr(source, "getvalue"):
        raw = source.getvalue()
        return io.BytesIO(raw), raw

    if hasattr(source, "read"):
        pos = source.tell() if hasattr(source, "tell") else None
        raw = source.read()
        if pos is not None:
            source.seek(pos)
        return io.BytesIO(raw), raw

    raise TypeError("Unsupported data source for Excel loading")


def _load_with_openpyxl(source: Union[str, os.PathLike, io.BytesIO]) -> Dict[str, pd.DataFrame]:
    workbook = load_workbook(source, read_only=True, data_only=True, keep_links=False)
    frames: Dict[str, pd.DataFrame] = {}
    for ws in workbook.worksheets:
        rows = list(ws.values)
        if not rows:
            frames[ws.title] = pd.DataFrame()
            continue
        header = rows[0]
        data = rows[1:]
        frames[ws.title] = pd.DataFrame(data, columns=header)
    return frames


@st.cache_data(show_spinner=False)
def load_excel(path: Union[str, os.PathLike, io.BytesIO, bytes]) -> Dict[str, pd.DataFrame]:
    prepared, raw_bytes = _ensure_bytes_buffer(path)
    try:
        xls = pd.ExcelFile(prepared, engine="openpyxl")
        return {sheet: pd.read_excel(xls, sheet_name=sheet) for sheet in xls.sheet_names}
    except ValueError as exc:
        # Certain workbooks include conditional-format operators unsupported by
        # openpyxl's parser.  Fall back to loading via openpyxl directly so we
        # can ignore the problematic formatting while keeping the cell values.
        if "Value must be one of" not in str(exc) and "Conditional Formatting" not in str(exc):
            raise
        fallback_source: Union[str, os.PathLike, io.BytesIO]
        if isinstance(prepared, (str, os.PathLike)):
            fallback_source = prepared
        else:
            buffer_bytes = raw_bytes if raw_bytes is not None else prepared.getvalue()
            fallback_source = io.BytesIO(buffer_bytes)
        return _load_with_openpyxl(fallback_source)


def format_percent(value: float | int | str, decimals: int = 1) -> str:
    if pd.isna(value):
        return "—"
    try:
        return f"{float(value):.{decimals}%}"
    except Exception:
        return str(value)


def format_number(value: float | int | str, decimals: int = 2, suffix: str = "") -> str:
    if pd.isna(value):
        return "—"
    try:
        return f"{float(value):,.{decimals}f}{suffix}"
    except Exception:
        return str(value)


def min_max_scale(series: pd.Series) -> pd.Series:
    s = series.astype(float)
    valid = s.dropna()
    if valid.empty:
        return pd.Series(0.0, index=series.index)
    min_val, max_val = valid.min(), valid.max()
    if min_val == max_val:
        return pd.Series(0.5, index=series.index)
    scaled = (s - min_val) / (max_val - min_val)
    return scaled.fillna(0.0)


def build_score(df: pd.DataFrame, weights: Dict[str, float], cols: ColumnMap) -> pd.Series:
    def _mean_of(columns: List[Optional[str]]) -> pd.Series:
        frames = [df[c] for c in columns if c in df.columns]
        if not frames:
            return pd.Series(0.0, index=df.index)
        return pd.concat(frames, axis=1).mean(axis=1, skipna=True)

    returns = _mean_of([
        cols.ytd_perf,
        cols.perf_1y,
        cols.perf_3y,
        cols.perf_5y,
        cols.perf_10y,
        cols.return_3y,
        cols.return_5y,
        cols.return_10y,
    ])
    income = _mean_of([cols.yield_fwd, cols.yield_ttm, cols.div_growth_3y, cols.div_growth_5y])
    quality = _mean_of([cols.quant_rating, cols.sa_rating])
    risk = _mean_of([cols.expense_ratio, cols.beta_60m])

    components = {
        "returns": min_max_scale(returns),
        "income": min_max_scale(income),
        "quality": min_max_scale(quality),
        "risk": 1 - min_max_scale(risk),  # lower expense/beta = better
    }

    total_weight = sum(weights.values()) or 1.0
    score = sum(components[name] * weights[name] for name in components)
    score = score / total_weight
    return score


def display_metric(col, label: str, value: str, delta: Optional[str] = None):
    try:
        col.metric(label, value, delta)
    except Exception:
        col.write(f"**{label}:** {value}")


# ---------------------------------------------------------------------------
# Sidebar (data source + filters)
# ---------------------------------------------------------------------------


st.sidebar.header("Data source")
uploaded_file = st.sidebar.file_uploader("Upload Excel workbook", type=["xlsx"])
default_path = "AI_Ecosystem_ETFs_Cleaned_for_GoogleSheets.xlsx"

if uploaded_file is not None:
    workbook = load_excel(uploaded_file)
elif os.path.exists(default_path):
    workbook = load_excel(default_path)
else:
    st.error(
        "No Excel file found. Upload a workbook or include "
        "AI_Ecosystem_ETFs_Cleaned_for_GoogleSheets.xlsx in the project."
    )
    st.stop()

sheet_name = st.sidebar.selectbox("Sheet for ETF analytics", list(workbook.keys()))
raw_df = workbook[sheet_name]
etf_df, columns_map = clean_etf_sheet(raw_df)

if etf_df.empty:
    st.error("The selected sheet does not contain data.")
    st.stop()


# Sidebar filters -----------------------------------------------------------
def build_filter_options(column: Optional[str]) -> List[str]:
    if column and column in etf_df.columns:
        values = sorted(etf_df[column].dropna().astype(str).unique())
        return values
    return []


asset_classes = build_filter_options(columns_map.asset_class)
fund_types = build_filter_options(columns_map.fund_type)
issuers = build_filter_options(columns_map.issuer)

selected_assets = st.sidebar.multiselect("Asset Class", asset_classes, default=asset_classes)
selected_fund_types = st.sidebar.multiselect("Fund Type", fund_types, default=fund_types)
selected_issuers = st.sidebar.multiselect("Issuer", issuers, default=issuers)


filtered = etf_df.copy()
if columns_map.asset_class and selected_assets:
    filtered = filtered[filtered[columns_map.asset_class].astype(str).isin(selected_assets)]
if columns_map.fund_type and selected_fund_types:
    filtered = filtered[filtered[columns_map.fund_type].astype(str).isin(selected_fund_types)]
if columns_map.issuer and selected_issuers:
    filtered = filtered[filtered[columns_map.issuer].astype(str).isin(selected_issuers)]

search_symbol = st.sidebar.text_input("Search symbol or fund name")
if search_symbol:
    mask = pd.Series(True, index=filtered.index)
    if columns_map.symbol in filtered.columns:
        mask &= filtered[columns_map.symbol].astype(str).str.contains(search_symbol, case=False, na=False)
    if columns_map.fund_name in filtered.columns:
        mask |= filtered[columns_map.fund_name].astype(str).str.contains(search_symbol, case=False, na=False)
    filtered = filtered[mask]


# Metrics section -----------------------------------------------------------

st.title("ETF Lab: analytics-ready dashboard")
st.caption("Upload your Excel file, explore risk, and surface the best ETFs using your metrics.")

metric_cols = st.columns(4)

if columns_map.aum and columns_map.aum in filtered.columns:
    total_aum = filtered[columns_map.aum].sum()
    display_metric(metric_cols[0], "Total AUM", format_number(total_aum / 1_000_000_000, 2, "B"))
else:
    display_metric(metric_cols[0], "Total AUM", "Data missing")

if columns_map.expense_ratio and columns_map.expense_ratio in filtered.columns:
    median_expense = filtered[columns_map.expense_ratio].median()
    display_metric(metric_cols[1], "Median Expense Ratio", format_percent(median_expense, 2))
else:
    display_metric(metric_cols[1], "Median Expense Ratio", "—")

if columns_map.perf_1y and columns_map.perf_1y in filtered.columns:
    median_1y = filtered[columns_map.perf_1y].median()
    display_metric(metric_cols[2], "Median 1Y Perf", format_percent(median_1y, 2))
else:
    display_metric(metric_cols[2], "Median 1Y Perf", "—")

if columns_map.beta_60m and columns_map.beta_60m in filtered.columns:
    median_beta = filtered[columns_map.beta_60m].median()
    display_metric(metric_cols[3], "Median 60M Beta", format_number(median_beta, 2))
else:
    display_metric(metric_cols[3], "Median 60M Beta", "—")


# Tabs ----------------------------------------------------------------------

overview_tab, risk_tab, top_tab, data_tab = st.tabs(
    ["Overview", "Risk & Performance", "Top 10 ETFs", "Raw Data"]
)


with overview_tab:
    left, right = st.columns(2)

    if columns_map.asset_class and columns_map.aum and not filtered.empty:
        st.subheader("AUM by Asset Class")
        grouped = (
            filtered.groupby(columns_map.asset_class)[columns_map.aum]
            .sum()
            .reset_index()
        )
        grouped["AUM (Billions)"] = grouped[columns_map.aum] / 1_000_000_000
        fig = px.bar(
            grouped,
            x=columns_map.asset_class,
            y="AUM (Billions)",
            color=columns_map.asset_class,
            title=None,
        )
        fig.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig, use_container_width=True)

    if columns_map.perf_1y and columns_map.aum and columns_map.asset_class:
        st.subheader("Performance vs. Fund Size")
        scatter = px.scatter(
            filtered,
            x=columns_map.perf_1y,
            y=columns_map.aum,
            color=columns_map.asset_class,
            hover_data=[columns_map.symbol, columns_map.fund_name],
            labels={columns_map.perf_1y: "1Y Performance", columns_map.aum: "AUM"},
        )
        scatter.update_layout(height=420)
        st.plotly_chart(scatter, use_container_width=True)

    st.markdown("### Filtered ETFs")
    display_df = filtered.copy()
    for col in PERCENT_COLUMNS:
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda x: format_percent(x, 2))
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    csv_buffer = io.StringIO()
    filtered.to_csv(csv_buffer, index=False)
    st.download_button(
        "Download filtered ETFs (CSV)",
        data=csv_buffer.getvalue(),
        file_name="filtered_etfs.csv",
        mime="text/csv",
        use_container_width=True,
    )


with risk_tab:
    st.subheader("Risk diagnostics")
    col_a, col_b = st.columns(2)

    if columns_map.beta_60m and columns_map.beta_60m in filtered.columns:
        hist = px.histogram(
            filtered,
            x=columns_map.beta_60m,
            nbins=25,
            title="Beta distribution",
        )
        col_a.plotly_chart(hist, use_container_width=True)

    if columns_map.beta_60m and columns_map.perf_1y:
        scatter_risk = px.scatter(
            filtered,
            x=columns_map.beta_60m,
            y=columns_map.perf_1y,
            size=columns_map.aum if columns_map.aum in filtered.columns else None,
            color=columns_map.asset_class if columns_map.asset_class in filtered.columns else None,
            hover_data=[columns_map.symbol, columns_map.fund_name],
            labels={columns_map.beta_60m: "60M Beta", columns_map.perf_1y: "1Y Performance"},
        )
        col_b.plotly_chart(scatter_risk, use_container_width=True)

    if columns_map.expense_ratio and columns_map.yield_ttm:
        st.subheader("Income vs. Cost")
        income_chart = px.scatter(
            filtered,
            x=columns_map.expense_ratio,
            y=columns_map.yield_ttm,
            color=columns_map.asset_class if columns_map.asset_class in filtered.columns else None,
            hover_data=[columns_map.symbol, columns_map.fund_name],
            labels={
                columns_map.expense_ratio: "Expense Ratio",
                columns_map.yield_ttm: "Yield TTM",
            },
        )
        st.plotly_chart(income_chart, use_container_width=True)

    st.markdown("#### Risk table")
    risk_cols = [
        c
        for c in [
            columns_map.symbol,
            columns_map.fund_name,
            columns_map.aum,
            columns_map.beta_60m,
            columns_map.expense_ratio,
            columns_map.quant_rating,
            columns_map.days_quant,
        ]
        if c
    ]
    risk_table = filtered[risk_cols].copy()
    if columns_map.aum in risk_table:
        risk_table[columns_map.aum] = risk_table[columns_map.aum] / 1_000_000_000
        risk_table = risk_table.rename(columns={columns_map.aum: "AUM (Billions)"})
    if columns_map.expense_ratio in risk_table:
        risk_table[columns_map.expense_ratio] = risk_table[columns_map.expense_ratio].map(
            lambda x: format_percent(x, 2)
        )
    st.dataframe(risk_table, use_container_width=True, hide_index=True)


with top_tab:
    st.subheader("Top ETFs based on your metrics")
    st.write(
        "Scores combine returns, income, quality, and risk. Adjust the weights to align "
        "with your investment policy, then review the top 10 ideas."
    )

    weight_cols = st.columns(4)
    return_weight = weight_cols[0].slider("Returns weight", 0.0, 4.0, 2.0, 0.1)
    income_weight = weight_cols[1].slider("Income weight", 0.0, 4.0, 1.0, 0.1)
    quality_weight = weight_cols[2].slider("Quality weight", 0.0, 4.0, 1.0, 0.1)
    risk_weight = weight_cols[3].slider("Risk control weight", 0.0, 4.0, 2.0, 0.1)

    weights = {
        "returns": return_weight,
        "income": income_weight,
        "quality": quality_weight,
        "risk": risk_weight,
    }

    scores = build_score(filtered, weights, columns_map)
    top_frame = filtered.copy()
    top_frame["ETF Score"] = scores
    top10 = top_frame.sort_values("ETF Score", ascending=False).head(10)

    if not top10.empty:
        st.markdown("#### Ranked list")
        score_cols = [
            columns_map.symbol,
            columns_map.fund_name,
            columns_map.asset_class,
            columns_map.aum,
            columns_map.expense_ratio,
            columns_map.perf_1y,
            columns_map.perf_3y,
            columns_map.perf_5y,
            columns_map.yield_ttm,
            columns_map.beta_60m,
            "ETF Score",
        ]
        score_cols = [c for c in score_cols if c in top10.columns]
        table = top10[score_cols].copy()
        if columns_map.aum in table.columns:
            table[columns_map.aum] = table[columns_map.aum] / 1_000_000_000
            table = table.rename(columns={columns_map.aum: "AUM (Billions)"})
        for col in PERCENT_COLUMNS:
            if col in table.columns:
                table[col] = table[col].map(lambda x: format_percent(x, 2))
        table["ETF Score"] = table["ETF Score"].map(lambda x: f"{x:.3f}")
        st.dataframe(table, hide_index=True, use_container_width=True)

        bar = px.bar(
            top10,
            x=columns_map.symbol if columns_map.symbol else columns_map.fund_name,
            y="ETF Score",
            color=columns_map.asset_class if columns_map.asset_class in top10.columns else None,
            hover_data=[columns_map.fund_name] if columns_map.fund_name in top10.columns else None,
        )
        bar.update_layout(height=420)
        st.plotly_chart(bar, use_container_width=True)
    else:
        st.info("No ETFs remain after filtering.")


with data_tab:
    st.subheader("Raw workbook preview")
    selected_sheet = st.selectbox("Preview sheet", list(workbook.keys()), index=list(workbook.keys()).index(sheet_name))
    st.dataframe(workbook[selected_sheet], use_container_width=True, hide_index=True)

