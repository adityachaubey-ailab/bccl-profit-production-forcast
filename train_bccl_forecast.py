from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "bccl_model_dataset.csv"
SUMMARY_PATH = BASE_DIR / "bccl_forecast_summary.json"


def make_features(series: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"target": series.astype(float)})
    df["lag1"] = df["target"].shift(1)
    df["lag2"] = df["target"].shift(2)
    df["rolling_mean_3"] = df["target"].shift(1).rolling(3).mean()
    df["trend"] = np.arange(len(df), dtype=float)
    return df.dropna().reset_index()


def fit_linear_regression(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x_with_bias = np.column_stack([np.ones(len(x)), x])
    coeffs, _, _, _ = np.linalg.lstsq(x_with_bias, y, rcond=None)
    return coeffs


def predict_linear_regression(coeffs: np.ndarray, x: np.ndarray) -> np.ndarray:
    x_with_bias = np.column_stack([np.ones(len(x)), x])
    return x_with_bias @ coeffs


def evaluate_metric(df: pd.DataFrame, metric: str) -> dict[str, object] | None:
    if metric not in df.columns:
        return None

    metric_df = df[["year", metric]].dropna().copy().reset_index(drop=True)
    if len(metric_df) < 6:
        return None

    feature_df = make_features(metric_df[metric])
    if len(feature_df) < 4:
        return None

    feature_cols = ["lag1", "lag2", "rolling_mean_3", "trend"]
    test_size = 2 if len(feature_df) >= 6 else 1

    train = feature_df.iloc[:-test_size].copy()
    test = feature_df.iloc[-test_size:].copy()

    coeffs = fit_linear_regression(train[feature_cols].to_numpy(), train["target"].to_numpy())
    test_predictions = predict_linear_regression(coeffs, test[feature_cols].to_numpy())

    mae = float(np.mean(np.abs(test["target"].to_numpy() - test_predictions)))
    rmse = float(np.sqrt(np.mean((test["target"].to_numpy() - test_predictions) ** 2)))

    full_coeffs = fit_linear_regression(
        feature_df[feature_cols].to_numpy(),
        feature_df["target"].to_numpy(),
    )

    full_values = metric_df[metric].astype(float).reset_index(drop=True)
    next_features = pd.DataFrame(
        {
            "lag1": [full_values.iloc[-1]],
            "lag2": [full_values.iloc[-2]],
            "rolling_mean_3": [full_values.iloc[-3:].mean()],
            "trend": [float(len(full_values))],
        }
    )
    next_prediction = float(
        predict_linear_regression(full_coeffs, next_features[feature_cols].to_numpy())[0]
    )

    next_year = int(metric_df["year"].max()) + 1
    test_years = metric_df.loc[test["index"], "year"].astype(int).tolist()

    return {
        "metric": metric,
        "training_rows": int(len(metric_df)),
        "test_years": test_years,
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "forecast_year": next_year,
        "forecast_value": round(next_prediction, 3),
    }


def main() -> None:
    if not DATASET_PATH.exists():
        print(f"Dataset not found: {DATASET_PATH}")
        print("Run build_bccl_model_dataset.py first.")
        return

    df = pd.read_csv(DATASET_PATH)
    summaries = []
    for metric in ("production_mt", "profit_after_tax"):
        result = evaluate_metric(df, metric)
        if result is not None:
            summaries.append(result)

    if not summaries:
        print("Not enough clean data to train forecast models.")
        return

    SUMMARY_PATH.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"Saved forecast summary to {SUMMARY_PATH}")
    for item in summaries:
        print(
            f"{item['metric']}: forecast {item['forecast_year']} = "
            f"{item['forecast_value']} | MAE={item['mae']} RMSE={item['rmse']}"
        )


if __name__ == "__main__":
    main()
