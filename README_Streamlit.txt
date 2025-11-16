# ETF Lab — Streamlit Dashboard

This repository ships with a Streamlit app (`streamlit_app.py`) that turns the
`ETFs` worksheet from the Excel workbook into a multi-tab analytics studio. It
can be launched directly with `streamlit run` on your machine or inside a local
Docker Desktop container.

## Quick start (local machine)

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Run inside Docker Desktop

The repo now includes a `Dockerfile` so you can build a self-contained image
with all dependencies and assets (including the Excel workbook) baked in.

```bash
# Build the image once
docker build -t etf-lab .

# Launch the dashboard
docker run --rm -p 8501:8501 etf-lab
```

Then open http://localhost:8501 in your browser. Hot-reload is provided by
Streamlit inside the container, so rebuilding is only required when
dependencies change.

## Features

- **Flexible data ingestion** – upload any workbook with an `ETFs` sheet or use
  the bundled sample file. Column names are normalized automatically and
  conditional formatting is stripped so even exotic spreadsheets load cleanly.
- **Filters + search** – slice by Asset Class, Fund Type, Issuer, and ticker or
  fund name search.
- **10 purpose-built dashboards** – the tab strip now includes:
  1. **Overview** (AUM by asset class, performance vs. size, formatted table).
  2. **Risk & Performance** (beta histogram, beta vs. return bubble, risk
     table, and income vs. cost plot).
  3. **Income & Dividends** (yield vs. dividend-growth scatter, top yielders,
     and descriptive stats).
  4. **Concentration** (holdings vs. % top-10 scatter and most concentrated
     funds table).
  5. **Issuer Spotlight** (issuer-level aggregates with AUM bars and metrics).
  6. **Quality Radar** (rating histograms, rating scatter, and a radar summary).
  7. **Performance Heatmap** (multi-horizon performance matrix for up to 40
     tickers).
  8. **Cost & Liquidity** (expense box plot, AUM bubble, and AUM distribution).
  9. **Top 10 ETFs** (configurable scoring engine with sortable table + chart).
  10. **Raw Data** (worksheet preview for any tab in the uploaded workbook).
- **Percent normalization fixes** – expense ratio, yield, and dividend-growth
  inputs are converted to proper percentages so values like `0.50` display as
  `0.50%` instead of `50%`.

The interface is optimized for the columns listed in the user request (Rank,
Symbol, Fund Name, Price, Change %, Asset Class & Sub-class, Fund Type, Issuer,
Inception Date, AUM, Expense Ratio, Quant Rating, SA Analyst Ratings, 1Y Perf,
3Y Perf, 3Y Total Return, 5Y Perf, 5Y Total Return, 10Y Perf, 10Y Total Return,
YTD Perf, % top 10 Holdings, Div Growth 5Y, Div Growth 3Y, Yield FWD, Yield TTM,
Frequency, 60M Beta, Days at Quant Rating). Missing columns are handled
gracefully.
