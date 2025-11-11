
import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
import plotly.express as px

st.set_page_config(page_title="AI Ecosystem ETFs — Interactive Explorer", layout="wide")

PERCENT_CANDIDATES = [
    "YTD %","1Y %","3Y % (Total Return)","5Y % (Total Return)",
    "YTD_Percent","1Y_Percent","3Y_Total_Return_Percent","5Y_Total_Return_Percent",
    "Max Drawdown (3Y)","Max_Drawdown_3Y",
    "Expense Ratio","Expense_Ratio",
    "Dividend Yield %","Dividend_Yield_Percent",
    "Top-10 Weight %","Top_10_Weight_Percent",
    "Weight %","Weight_Percent"
]

def is_percent_col(col_name):
    return any(col_name == c for c in PERCENT_CANDIDATES)

def format_percent(v, decimals=1):
    try:
        return f"{float(v):.{decimals}%}"
    except Exception:
        return v


@st.cache_data
def load_excel(file):
    xls = pd.ExcelFile(file)
    dfs = {name: pd.read_excel(file, sheet_name=name) for name in xls.sheet_names}
    return dfs

def clean_summary(df):
    df = df.copy()
    # Standardize columns (handle both cleaned + original headers)
    cols = {c.lower().strip(): c for c in df.columns}
    def get_col(*cands):
        for c in cands:
            if c in df.columns: return c
            lc = c.lower()
            for k in cols:
                if k == lc:
                    return cols[k]
        return None

    # Map possible names
    aum_col = get_col("AUM ($B)", "AUM_Billions")
    ytd_col = get_col("YTD %", "YTD_Percent")
    r1_col  = get_col("1Y %", "1Y_Percent")
    r3_col  = get_col("3Y % (Total Return)", "3Y_Total_Return_Percent")
    r5_col  = get_col("5Y % (Total Return)", "5Y_Total_Return_Percent")
    dd_col  = get_col("Max Drawdown (3Y)", "Max_Drawdown_3Y")
    exp_col = get_col("Expense Ratio", "Expense_Ratio")
    div_col = get_col("Dividend Yield %", "Dividend_Yield_Percent")
    top10_col = get_col("Top-10 Weight %", "Top_10_Weight_Percent")
    adv_col = get_col("Average Daily Dollar Volume 3M", "Avg_Daily_Dollar_Volume_3M")
    etf_col = get_col("ETF")
    theme_col = get_col("Theme")

    # Coerce numeric (AUM stays as number, percent-like fields are stored as FRACTIONS 0–1)
    if aum_col in df:
        df[aum_col] = pd.to_numeric(
            df[aum_col]
              .astype(str)
              .str.replace(r'[^0-9\.\-]', '', regex=True)  # remove $, B, commas, spaces
              .str.strip(),
            errors="coerce"  # invalid entries become NaN safely
        )

    for col in [ytd_col, r1_col, r3_col, r5_col, dd_col, exp_col, div_col, top10_col, adv_col]:
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- KEY FIX: normalize Top-10 Weight to a fraction (0–1) if it's 100× too small ---
    if top10_col in df and df[top10_col].notna().any():
        # If values look like 0.0059 (0.59%) instead of 0.59 (59%), scale ×100
        if df[top10_col].max() < 0.02:
            df[top10_col] = df[top10_col] * 100.0

    return df, dict(aum=aum_col, ytd=ytd_col, r1=r1_col, r3=r3_col, r5=r5_col, dd=dd_col,
                    exp=exp_col, div=div_col, top10=top10_col, adv=adv_col, etf=etf_col, theme=theme_col)

def clean_holdings(df):
    df = df.copy()
    # Normalize column names
    df.columns = [c.strip() for c in df.columns]

    # Standardize weight column name
    if "Weight_Percent" not in df.columns and "Weight %" in df.columns:
        df = df.rename(columns={"Weight %": "Weight_Percent"})

    # Coerce numeric
    if "Weight_Percent" in df:
        df["Weight_Percent"] = pd.to_numeric(df["Weight_Percent"], errors="coerce")

        # --- KEY FIX: normalize to FRACTIONS (0–1) per ETF ---
        # If an ETF's median weight > 1, it’s in percent (0–100) → divide by 100.
        med = df.groupby("ETF")["Weight_Percent"].median()
        percent_scale = med[med > 1].index
        df.loc[df["ETF"].isin(percent_scale), "Weight_Percent"] = (
            df.loc[df["ETF"].isin(percent_scale), "Weight_Percent"] / 100.0
        )

    return df


# Sidebar — file input

st.sidebar.header("Data")

# Check Streamlit secret flag for owner mode
is_owner = st.secrets.get("OWNER", "").lower() == "yes"

if is_owner:
    uploaded = st.sidebar.file_uploader("Upload Excel (AI_Ecosystem_ETFs file)", type=["xlsx"])
    st.sidebar.success("Owner mode enabled — you can upload a new dataset.")
else:
    st.sidebar.info("Static dashboard (viewer mode)")

# Always prefer uploaded when in owner mode; otherwise load bundled dataset
demo_path = "AI_Ecosystem_ETFs_Cleaned_for_GoogleSheets.xlsx"

if is_owner and uploaded is not None:
    dfs = load_excel(uploaded)
else:
    if os.path.exists(demo_path):
        dfs = load_excel(demo_path)
    else:
        st.error(
            "Dataset not found. Please include AI_Ecosystem_ETFs_Cleaned_for_GoogleSheets.xlsx "
            "in the repo, or set OWNER=yes in secrets and upload a file."
        )
        st.stop()

sheet_names = list(dfs.keys())
list(dfs.keys())
summary = dfs.get("Summary")
holdings = dfs.get("Holdings")
glossary = dfs.get("Glossary")

if summary is None or holdings is None:
    st.error("Expected sheets 'Summary' and 'Holdings' were not found.")
    st.stop()

summary, sm = clean_summary(summary)
holdings = clean_holdings(holdings)

# --- Top KPIs ---
col1, col2, col3, col4 = st.columns(4)
if sm['aum'] and sm['etf']:
    total_aum = summary[sm['aum']].sum()
    col1.metric("Total AUM ($B)", f"{total_aum:,.2f}")
if sm['exp']:
    col2.metric("Median Expense Ratio", f"{summary[sm['exp']].median():.3%}")
if sm['r1']:
    col3.metric("Median 1Y Return", f"{summary[sm['r1']].median():.2%}")
if sm['dd']:
    col4.metric("Median Max Drawdown (3Y)", f"{summary[sm['dd']].median():.2%}")

st.markdown("---")

# --- ETF Filters ---
etf_list = summary[sm['etf']].dropna().astype(str).unique().tolist() if sm['etf'] else []
selected_etfs = st.multiselect("Select ETFs", etf_list, default=etf_list)
summary_f = summary[summary[sm['etf']].isin(selected_etfs)] if sm['etf'] else summary

# --- AUM Bar ---
if sm['aum'] and sm['etf'] and not summary_f.empty:
    st.subheader("AUM by ETF ($B)")
    chart_aum = alt.Chart(summary_f).mark_bar().encode(
        x=alt.X(f"{sm['etf']}:N", title="ETF", sort='-y'),
        y=alt.Y(f"{sm['aum']}:Q", title="AUM ($B)"),
        tooltip=[sm['etf'], sm['theme'], sm['aum'], sm['exp']]
    ).properties(height=320)
    st.altair_chart(chart_aum, use_container_width=True)

cols = st.columns(2)

# --- Risk vs Return ---
with cols[0]:
    if sm['r5'] and sm['dd'] and sm['etf'] and not summary_f.empty:
        st.subheader("Risk vs Return")
        scatter = alt.Chart(summary_f).mark_point(size=120).encode(
            x=alt.X(f"{sm['dd']}:Q", title="Max Drawdown (3Y)", axis=alt.Axis(format='.1%')),
            y=alt.Y(f"{sm['r5']}:Q", title="5Y % Total Return", axis=alt.Axis(format='.1%')),
            color=alt.Color(f"{sm['theme']}:N", title="Theme") if sm['theme'] else alt.value("steelblue"),
            tooltip=[sm['etf'], sm['theme'], alt.Tooltip(f"{sm['dd']}:Q", format='.1%'), alt.Tooltip(f"{sm['r5']}:Q", format='.1%')]
        )
        text = alt.Chart(summary_f).mark_text(dy=-10).encode(
            x=f"{sm['dd']}:Q",
            y=f"{sm['r5']}:Q",
            text=f"{sm['etf']}:N"
        )
        st.altair_chart((scatter + text).interactive(), use_container_width=True)

# --- Expense Ratio vs 5Y Return ---
with cols[1]:
    if sm['exp'] and sm['r5'] and sm['etf'] and not summary_f.empty:
        st.subheader("Expense Ratio vs 5Y Return")
        exp_chart = alt.Chart(summary_f).mark_circle(size=120).encode(
            x=alt.X(f"{sm['exp']}:Q", title="Expense Ratio", axis=alt.Axis(format='.1%')),
            y=alt.Y(f"{sm['r5']}:Q", title="5Y % Total Return", axis=alt.Axis(format='.1%')),
            color=alt.Color(f"{sm['theme']}:N", title="Theme") if sm['theme'] else alt.value("orange"),
            tooltip=[sm['etf'], alt.Tooltip(f"{sm['exp']}:Q", format='.1%'), alt.Tooltip(f"{sm['r5']}:Q", format='.1%')]
        )
        labels = alt.Chart(summary_f).mark_text(dy=-10).encode(
            x=f"{sm['exp']}:Q",
            y=f"{sm['r5']}:Q",
            text=f"{sm['etf']}:N"
        )
        st.altair_chart((exp_chart + labels).interactive(), use_container_width=True)


st.markdown("---")
st.subheader("Summary Table")

if not summary_f.empty:
    # display-friendly copy: format percent columns only (not AUM)
    summary_display = summary_f.copy()
    for col in summary_display.columns:
        if is_percent_col(col):
            try:
                summary_display[col] = summary_display[col].map(lambda x: format_percent(x, 2) if pd.notna(x) else x)
            except Exception:
                pass

    # Optional quick search across ETF/Theme
    search_summary = st.text_input("Search summary (ETF or Theme)", "")
    sf = summary_display.copy()
    etf_col = sm.get('etf')
    theme_col = sm.get('theme')
    if search_summary and (etf_col or theme_col):
        mask = pd.Series([True]*len(sf))
        if etf_col in sf.columns:
            mask &= sf[etf_col].astype(str).str.contains(search_summary, case=False, na=False)
        if theme_col in sf.columns:
            mask |= sf[theme_col].astype(str).str.contains(search_summary, case=False, na=False)
        sf = sf[mask]
    st.dataframe(sf, use_container_width=True, hide_index=True)
else:
    st.info("No data in Summary after filters.")

st.markdown("---")
st.subheader("Holdings Analyzer")

# Filter holdings by ETF selection
if "ETF" in holdings.columns:
    holdings_f = holdings[holdings["ETF"].astype(str).isin(selected_etfs)] if selected_etfs else holdings.copy()
else:
    holdings_f = holdings.copy()

left, right = st.columns(2)

# Treemap by Industry (Plotly) — mobile-friendly labels
with left:
    if {"ETF", "Industry", "Weight_Percent"}.issubset(holdings_f.columns):
        st.markdown("**Industry Composition (Treemap)**")

        # Toggle for small screens
        mobile_mode = st.checkbox("Mobile-friendly labels", value=True, key="treemap_mobile_toggle")

        treemap = px.treemap(
            holdings_f,
            path=["ETF", "Industry"],
            values="Weight_Percent",
            hover_data=["Ticker", "Holding"] if {"Ticker", "Holding"}.issubset(holdings_f.columns) else None,
        )

        # 1) Hide cluttered labels automatically, keep hover clean
        # 2) In mobile mode, show only ETF + industry percent (no tiny leaf text walls)
        if mobile_mode:
            # Show label+percent for each box relative to its parent, cap depth to keep it readable
            treemap.update_traces(
                textinfo="label+percent parent",
                maxdepth=2,                    # ETF + Industry only
                textfont=dict(size=16),
                hovertemplate='<b>%{label}</b><br>Weight: %{value:.2%}<extra></extra>'
            )
            treemap.update_layout(
                uniformtext=dict(minsize=12, mode="hide"),  # auto-hide cramped labels
                margin=dict(t=30, l=0, r=0, b=0),
                treemapcolorway=None
            )
        else:
            # Desktop/full labels (still guarded to avoid overlaps)
            treemap.update_traces(
                textinfo="label+percent entry",
                textfont=dict(size=18),
                hovertemplate='<b>%{label}</b><br>Weight: %{value:.2%}<extra></extra>'
            )
            treemap.update_layout(
                uniformtext=dict(minsize=12, mode="hide"),
                margin=dict(t=30, l=0, r=0, b=0),
            )

        # Optional: remove the breadcrumb bar to save vertical space
        treemap.update_layout(pathbar=dict(visible=False))

        st.plotly_chart(treemap, use_container_width=True)
# Stacked bar by Country
with right:
    if {"ETF", "Country", "Weight_Percent"}.issubset(holdings_f.columns):
        st.markdown("**Country Breakdown (Stacked Bar)**")
        country_pivot = holdings_f.pivot_table(index="Country", columns="ETF", values="Weight_Percent", aggfunc="sum").fillna(0)
        country_pivot = country_pivot.reset_index().melt(id_vars="Country", var_name="ETF", value_name="Weight_Percent")
        bar = alt.Chart(country_pivot).mark_bar().encode(
            x=alt.X("Country:N", sort='-y'),
            y=alt.Y("Weight_Percent:Q", stack="normalize", title="Share of Weight", axis=alt.Axis(format='.0%')),
            color="ETF:N",
            tooltip=["Country", "ETF", alt.Tooltip("Weight_Percent:Q", format=".2f")]
        ).properties(height=320)
        st.altair_chart(bar, use_container_width=True)


# Holdings table (filter + search)
st.markdown("### Holdings Table")
if not holdings_f.empty:
    display_df = holdings_f.copy()
    # Format percent-looking columns as percentages for display only (do not touch underlying for charts)
    for col in display_df.columns:
        if is_percent_col(col):
            try:
                display_df[col] = display_df[col].map(lambda x: format_percent(x, 2) if pd.notna(x) else x)
            except Exception:
                pass
    search = st.text_input("Search holdings (by Ticker or Name)", "")
    hf = display_df.copy()
    if search:
        mask = pd.Series([True]*len(hf))
        for col in ["Ticker", "Holding", "Industry", "Country"]:
            if col in hf.columns:
                mask &= hf[col].astype(str).str.contains(search, case=False, na=False)
        hf = hf[mask]
    st.dataframe(hf, use_container_width=True, hide_index=True)

# Downloads
st.markdown("---")
col_a, col_b = st.columns(2)
with col_a:
    if st.button("Download cleaned Summary + Holdings (CSV in ZIP)", type="primary"):
        import io, zipfile
        buff = io.BytesIO()
        with zipfile.ZipFile(buff, "w", zipfile.ZIP_DEFLATED) as zf:
            summ = summary_f if not summary_f.empty else summary
            zf.writestr("Summary.csv", summ.to_csv(index=False))
            zf.writestr("Holdings.csv", holdings_f.to_csv(index=False))
        st.download_button("Save ZIP", data=buff.getvalue(), file_name="AI_ETFs_cleaned.zip", mime="application/zip")

# Glossary
if isinstance(dfs.get("Glossary"), pd.DataFrame):
    with st.expander("Glossary"):
        st.dataframe(dfs["Glossary"], use_container_width=True, hide_index=True)

st.caption("Tip: Connect this file to Google Sheets or Looker Studio for live dashboards.")
