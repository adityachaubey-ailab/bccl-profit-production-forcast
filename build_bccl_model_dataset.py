from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "extracted_csvs"
OUTPUT_PATH = BASE_DIR / "bccl_model_dataset.csv"

# Recent annual reports contain cleaner, restated summary tables than the
# generic PDF table extraction. We use those values to override noisier rows.
CURATED_OVERRIDES = {
    2021: {
        "production_mt": 24.66,
        "profit_before_tax": -1577.06,
        "profit_after_tax": -1202.48,
    },
    2022: {
        "production_mt": 30.51,
        "profit_before_tax": 191.31,
        "profit_after_tax": 111.62,
    },
    2023: {
        "production_mt": 36.179,
        "profit_before_tax": 530.19,
        "profit_after_tax": 664.78,
    },
    2024: {
        "production_mt": 41.096,
        "profit_before_tax": 2091.67,
        "profit_after_tax": 1564.46,
    },
}

YEAR_HEADER_PATTERNS = (
    "year ending 31st march",
    "year ended 31st march",
)


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    text = text.replace("\uf001", "fi")
    text = text.replace("\x00", "")
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def normalize_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean_text(text).lower()).strip()


def split_lines(text: object) -> list[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []
    return [line.strip() for line in cleaned.split("\n") if line.strip()]


def parse_year_label(text: str) -> int | None:
    cleaned = clean_text(text)
    if not cleaned:
        return None

    match = re.search(r"(20\d{2}|19\d{2})\s*[-/]\s*\d{2,4}", cleaned)
    if match:
        left = int(re.search(r"(19|20)\d{2}", match.group(0)).group(0))
        return left + 1

    years = re.findall(r"(19\d{2}|20\d{2})", cleaned)
    if years:
        return int(years[-1])

    return None


def parse_number(text: str) -> float | None:
    cleaned = clean_text(text)
    if not cleaned or cleaned in {"-", "--"}:
        return None

    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    cleaned = cleaned.replace(",", "")

    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None

    value = float(match.group(0))
    return -value if negative and value > 0 else value


def metric_from_context(label: str, section: str | None) -> str | None:
    normalized = normalize_label(label)

    if "net profit after tax" in normalized:
        return "profit_after_tax"
    if "net profit before tax" in normalized:
        return "profit_before_tax"
    if "sale value of production" in normalized:
        return "sale_value_of_production"
    if normalized.startswith("2 production"):
        return "production_mt"
    if section == "production_raw_coal" and normalized == "total":
        return "production_mt"

    return None


def section_from_label(label: str, current: str | None) -> str | None:
    normalized = normalize_label(label)

    if "production of raw coal" in normalized:
        return "production_raw_coal"
    if "off take" in normalized:
        return "off_take"
    if "overburden removal" in normalized:
        return "overburden"
    if "related to profit loss" in normalized or "related to profit loss" in normalized:
        return "profit_loss"

    return current


def label_consumes_value(label: str, section: str | None) -> bool:
    normalized = normalize_label(label)

    heading_phrases = (
        "related to profit loss",
        "profitability ratio",
        "liquidity ratios",
        "turnover ratios",
        "structural ratios",
        "production of raw coal",
        "off take",
        "overburden removal",
        "productivity",
        "information as per cost report",
        "overall stock",
        "break up of difference",
        "stock of",
        "as of net sales",
        "as of total expenditure",
        "as of capital employed",
        "as ratio of net sales",
    )
    if any(phrase in normalized for phrase in heading_phrases):
        return False

    unit_labels = {
        "million tonnes",
        "million cu mts",
        "qty value",
        "tonnes",
        "undergroud tonnes",
    }
    if normalized in unit_labels:
        return False

    if normalized in {"a", "b", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii"}:
        return False

    if label.strip().endswith(":") and metric_from_context(label, section) is None:
        return False

    return True


def extract_from_multiline_row(
    labels_block: str,
    year_values: dict[int, str],
    source_file: str,
) -> list[dict[str, object]]:
    labels = split_lines(labels_block)
    split_values = {year: split_lines(text) for year, text in year_values.items()}

    records: list[dict[str, object]] = []
    section: str | None = None
    value_pointers = {year: 0 for year in split_values}

    for label in labels:
        section = section_from_label(label, section)
        metric = metric_from_context(label, section)
        consumes_value = label_consumes_value(label, section)

        current_values: dict[int, str] = {}
        if consumes_value:
            for year, values in split_values.items():
                pointer = value_pointers[year]
                if pointer < len(values):
                    current_values[year] = values[pointer]
                    value_pointers[year] = pointer + 1

        if metric:
            for year, text_value in current_values.items():
                value = parse_number(text_value)
                if value is None:
                    continue
                records.append(
                    {
                        "year": year,
                        "metric": metric,
                        "value": value,
                        "source_file": source_file,
                    }
                )

    return records


def extract_from_csv(csv_path: Path) -> list[dict[str, object]]:
    try:
        df = pd.read_csv(csv_path, dtype=str)
    except Exception:
        return []

    if df.empty:
        return []

    source_file = csv_path.name
    first_col = df.columns[0]
    records: list[dict[str, object]] = []

    for row_index, row in df.iterrows():
        header_value = normalize_label(row.get(first_col, ""))
        if not any(pattern in header_value for pattern in YEAR_HEADER_PATTERNS):
            continue

        year_columns: list[tuple[str, int]] = []
        for col in df.columns[1:]:
            if col in {"source_pdf", "table_index"}:
                continue
            year = parse_year_label(row.get(col, ""))
            if year is not None:
                year_columns.append((col, year))

        if not year_columns:
            continue

        for next_row_index in range(row_index + 1, len(df)):
            labels_block = clean_text(df.iloc[next_row_index][first_col])
            if not labels_block:
                continue

            year_values = {
                year: clean_text(df.iloc[next_row_index][col])
                for col, year in year_columns
            }

            if not any(year_values.values()):
                continue

            extracted = extract_from_multiline_row(
                labels_block=labels_block,
                year_values=year_values,
                source_file=source_file,
            )
            records.extend(extracted)

    return records


def build_dataset() -> pd.DataFrame:
    all_records: list[dict[str, object]] = []
    for csv_path in sorted(CSV_DIR.glob("*.csv")):
        all_records.extend(extract_from_csv(csv_path))

    if not all_records:
        return pd.DataFrame()

    long_df = pd.DataFrame(all_records)
    aggregated_rows: list[dict[str, float]] = []
    for (year, metric), group in long_df.groupby(["year", "metric"]):
        if metric == "production_mt":
            value = group["value"].max()
        else:
            value = group["value"].median()
        aggregated_rows.append({"year": year, "metric": metric, "value": value})

    aggregated = pd.DataFrame(aggregated_rows)

    wide_df = aggregated.pivot(index="year", columns="metric", values="value").reset_index()
    wide_df = wide_df.sort_values("year").reset_index(drop=True)

    for year, overrides in CURATED_OVERRIDES.items():
        if not (wide_df["year"] == year).any():
            wide_df.loc[len(wide_df), "year"] = year
        row_mask = wide_df["year"] == year
        for column, value in overrides.items():
            wide_df.loc[row_mask, column] = value

    wide_df = wide_df.sort_values("year").reset_index(drop=True)

    preferred_columns = [
        "year",
        "production_mt",
        "sale_value_of_production",
        "profit_before_tax",
        "profit_after_tax",
    ]
    existing = [col for col in preferred_columns if col in wide_df.columns]
    return wide_df[existing]


def main() -> None:
    dataset = build_dataset()
    if dataset.empty:
        print("No modeling data could be extracted from extracted_csvs.")
        return

    dataset.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved modeling dataset to {OUTPUT_PATH}")
    print(dataset.to_string(index=False))


if __name__ == "__main__":
    main()
