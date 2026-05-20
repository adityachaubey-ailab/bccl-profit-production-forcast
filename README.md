# BCCL Prediction Model

This student project uses BCCL (Bharat Coking Coal Limited) annual report data to forecast:

- Coal production
- Profit after tax

The project collects report data, cleans it into a yearly dataset, trains a simple forecasting model, and creates an HTML/React dashboard so the results are easy to view and present.

## Quick Start

If you only want to view the existing dashboard, open:

```powershell
start forecast_dashboard_react.html
```

The dashboard is a static HTML file, but it loads React and Babel from `unpkg.com`, so keep your internet connection on when opening it.

## Setup

Run these commands from the project folder:

```powershell
cd "C:\Users\shash\bccl-profit-production-forcast"
py -m pip install -r requirements-bccl.txt
```

If `py` is not available on your system, use `python` instead:

```powershell
python -m pip install -r requirements-bccl.txt
```

## How To Regenerate The Results

Use this workflow when you want to rebuild the dataset, rerun the model, and recreate the dashboard.

```powershell
py build_bccl_model_dataset.py
py train_bccl_forecast.py
py build_forecast_dashboard_react.py
start forecast_dashboard_react.html
```

What each step does:

| Step | Command | Output |
| --- | --- | --- |
| 1 | `py build_bccl_model_dataset.py` | Rebuilds `bccl_model_dataset.csv` |
| 2 | `py train_bccl_forecast.py` | Rebuilds `bccl_forecast_summary.json` |
| 3 | `py build_forecast_dashboard_react.py` | Rebuilds `forecast_dashboard_react.html` |
| 4 | `start forecast_dashboard_react.html` | Opens the dashboard |

## Optional: Download And Extract Annual Reports

The scraper is only needed if you want to collect report tables again from the BCCL website.

```powershell
py bccl_scraper.py
```

This script can create these generated folders/files:

- `bccl_reports/` for downloaded PDF reports
- `extracted_csvs/` for extracted report tables
- `combined_bccl_dataset.csv` for the combined extracted tables

On Windows, installing Ghostscript can improve Camelot PDF table extraction. If Camelot does not work, the scraper can fall back to pdfplumber.

## Project Files

| File | Purpose |
| --- | --- |
| `bccl_scraper.py` | Downloads BCCL annual report PDFs and extracts tables into CSV files |
| `build_bccl_model_dataset.py` | Creates the cleaned yearly modeling dataset |
| `train_bccl_forecast.py` | Trains the forecast model and writes forecast/error results |
| `build_forecast_dashboard_react.py` | Builds the final React-based dashboard HTML |
| `bccl_model_dataset.csv` | Final cleaned dataset used by the model |
| `bccl_forecast_summary.json` | Forecast output and model error values |
| `forecast_dashboard_react.html` | Final dashboard with charts, metrics, and the cleaned dataset table |
| `requirements-bccl.txt` | Python dependencies needed for the project |

## Dataset

The dataset is based on yearly BCCL values such as:

- Production
- Sale value of production
- Profit before tax
- Profit after tax

Example cleaned values:

| Year | Production | Profit After Tax |
| --- | ---: | ---: |
| 2021 | 24.66 | -1202.48 |
| 2022 | 30.51 | 111.62 |
| 2023 | 36.179 | 664.78 |
| 2024 | 41.096 | 1564.46 |

## Current Forecast Output

| Metric | Forecast Year | Forecast Value |
| --- | --- | ---: |
| Production | 2025 | 39.308 |
| Profit After Tax | 2025 | 828.367 |

## Model Performance

| Metric | MAE | RMSE |
| --- | ---: | ---: |
| Production | 1.689 | 1.747 |
| Profit After Tax | 2285.129 | 2430.158 |

The production model performs better than the profit model. Profit prediction is harder here because the dataset is small and the profit values are more unstable.

## Dashboard

The dashboard makes the forecast easier to understand and present. It shows:

- Production forecast graph
- Profit forecast graph
- Model metrics
- Cleaned yearly dataset table

Open it with:

```powershell
start forecast_dashboard_react.html
```

## Troubleshooting

If the dashboard does not show correctly:

- Check that you are connected to the internet, because the HTML file loads React from `unpkg.com`.
- Regenerate the dashboard with `py build_forecast_dashboard_react.py`.
- Make sure `bccl_model_dataset.csv` and `bccl_forecast_summary.json` are in the project folder.

If model training does not run:

- Install dependencies again with `py -m pip install -r requirements-bccl.txt`.
- Make sure `bccl_model_dataset.csv` exists before running `py train_bccl_forecast.py`.

If dataset rebuilding does not create data:

- Make sure extracted report CSV files exist inside `extracted_csvs/`.
- Run `py bccl_scraper.py` if you want to download and extract the report tables again.

## Project Objective

The main aim of this project is to understand how real company data can be used for prediction.

The project focuses on:

- Working with real annual report data
- Cleaning messy extracted data
- Building a prediction model
- Comparing prediction results
- Presenting the result in a better visual format

## What I Learned

From this project I learned:

- How to work with real-world messy data
- How to clean extracted annual report tables
- How prediction models depend a lot on data quality
- How to present model output in a more understandable way
- How production and profit behave differently in forecasting

## Limitations

- The dataset is small
- Some annual report values were difficult to extract cleanly
- The profit model is weaker than the production model
- The prediction is a baseline model, not a highly advanced model

## Future Improvement

In future, this project can be improved by:

- Using more years of data
- Adding more financial features
- Trying better machine learning models
- Making the dashboard fully interactive as a web app
- Improving the profit prediction model

## Data Source

BCCL official reports page:

- [https://bcclweb.in/?page_id=25564](https://bcclweb.in/?page_id=25564)

## Conclusion

This project shows the full process from BCCL annual report data collection and cleaning to prediction and visualization.

The most important part of this project was learning how to turn raw company report data into something useful for analysis and presentation.
