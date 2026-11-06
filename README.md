# The Wisdom of Crowds in Prediction Markets

A data science project on whether prediction markets get things right. We collected event, market, and price-history data from **Polymarket**, then used it to answer three questions:

1. **Calibration:** Do market prices match real-world outcomes? When a market says 70%, does the event happen about 70% of the time?
2. **Market structure:** Where does the trading volume actually go: sports, politics, or crypto?
3. **Forecastability:** Can an event's past price path predict where its probability will be a few hours from now?

We also ran unsupervised anomaly detection to flag events with unusually high trading volume, which can point to information asymmetry or coordinated trading.

> Built as a team project for **CS 418: Introduction to Data Science** at the University of Illinois Chicago (Spring 2026).

## Key findings

| Question | Result |
|---|---|
| Calibration | Final Polymarket prices on resolved markets line up with outcomes. **Brier score: 0.179**, and the reliability curve stays close to the diagonal. |
| Market structure | Volume is concentrated in a few categories: **Sports, Politics, and Crypto** dominate. |
| Forecasting | An XGBoost model on lagged prices reaches **RMSE ≈ 0.001 / MAE ≈ 0.0004** on 30-minute steps, but this mostly comes from probabilities staying flat. On volatile events, 4-hour autoregressive forecasts miss sudden jumps, and directional accuracy ranges from 25% to 87.5%. |
| Anomalies | Isolation Forest flags a small set of events whose volume is far above their category baseline. |

**Takeaway:** markets are good at pricing in what is already known, but price history alone can't predict where a market goes next. Big moves come from outside information such as news and announcements. Better forecasts would need news/event data and microstructure features like liquidity, spread, and order-book depth.

## Repository layout

```
.
├── final_report/
│   └── final_progress_report.ipynb   # Final report: calibration, forecasting, anomaly detection, conclusions
├── progress_report.ipynb             # Mid-semester progress report with hypotheses and EDA
├── forecasting/
│   ├── generate_forecasting_data.ipynb   # Pulls and merges price histories for modeling
│   └── forecasting.ipynb                 # Lag features + XGBoost, multi-step forecasts, window-size tests
├── eda-notebook/                     # Exploratory analysis of Polymarket events and markets
├── kaggle-dataset/
│   └── visualizations.ipynb          # Visualizations on the Kaggle Polymarket dataset
├── polymarket-scraper/               # Scrapers for the Polymarket API (events, markets, price history)
└── kalshi-scraper/                   # Scrapers for the Kalshi API (events, markets, multivariate)
```

## Data sources

- **[Kaggle Polymarket dataset](https://www.kaggle.com/datasets/ismetsemedov/polymarket-prediction-markets):** events and markets tables. Download the CSVs into `kaggle-dataset/`.
- **Polymarket API:** collected with the scripts in `polymarket-scraper/` (Gamma API for events/markets, CLOB API for price history).
- **Kalshi API:** collected with the scripts in `kalshi-scraper/`. We originally planned to compare platforms, but the final analysis focuses on Polymarket because of how much data there was.

Raw data (`*.db`, `*.csv`, API response dumps) is gitignored because of its size. Run the scrapers to regenerate it.

## Getting started

Requires **Python 3.12+**. Each scraper is its own project with a `pyproject.toml`, so [uv](https://docs.astral.sh/uv/) is the easiest way to run them.

```bash
git clone https://github.com/<your-username>/prediction-markets-wisdom-of-crowds.git
cd prediction-markets-wisdom-of-crowds

# Scrape Polymarket
cd polymarket-scraper
uv run fetch_events.py
uv run fetch_inactive_events.py
uv run fetch_markets.py
```

The scrapers are rate-limited and can be stopped and resumed: on `Ctrl+C` they save a checkpoint (`*_checkpoint.pkl`) and pick up from it on the next run. Results are written to local SQLite databases with `sqlite-utils`.

To run the analysis notebooks:

```bash
pip install jupyterlab pandas numpy matplotlib seaborn plotly scikit-learn xgboost
jupyter lab
```

Open `final_report/final_progress_report.ipynb` for the full analysis, or `forecasting/forecasting.ipynb` for the modeling details.

## Methods

- **Calibration:** Brier score and reliability curve, comparing each resolved market's `lastTradePrice` with its actual outcome.
- **Forecasting:** Resample each event's price path to 30-minute intervals, add lag and rolling-statistic features, train an XGBoost regressor on a time-ordered (unshuffled) train/test split, and run recursive 8-step (4-hour) forecasts. Window sizes of 4, 8, and 16 lags were compared on both raw and smoothed data.
- **Anomaly detection:** Isolation Forest on event volume relative to category-level baselines.

## Contributors

Deniz Caglar, Chaitu, [saifullahsshak](https://github.com/saifullahsshak), and [Moiz Ali](https://github.com/moizali01).
