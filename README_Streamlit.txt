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
  the bundled sample file. Column names are normalized automatically.
- **Filters + search** – slice by Asset Class, Fund Type, Issuer, and ticker or
  fund name search.
- **Overview tab** – compare AUM by asset class, plot 1Y performance vs. fund
  size, download the filtered view, and inspect a formatted table.
- **Risk & Performance tab** – beta histogram, beta vs. returns scatter, and an
  income-vs-expense view plus a compact risk table.
- **Top 10 tab** – configurable weights (returns, income, quality, risk) feed a
  composite score so you can surface the best ETFs from your sheet.
- **Raw data preview** – inspect any worksheet in the uploaded workbook without
  leaving the app.

The interface is optimized for the columns listed in the user request (Rank,
Symbol, Fund Name, Price, Change %, Asset Class & Sub-class, Fund Type, Issuer,
Inception Date, AUM, Expense Ratio, Quant Rating, SA Analyst Ratings, 1Y Perf,
3Y Perf, 3Y Total Return, 5Y Perf, 5Y Total Return, 10Y Perf, 10Y Total Return,
YTD Perf, % top 10 Holdings, Div Growth 5Y, Div Growth 3Y, Yield FWD, Yield TTM,
Frequency, 60M Beta, Days at Quant Rating). Missing columns are handled
gracefully.
