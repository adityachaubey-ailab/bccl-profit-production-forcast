"""
BCCL / Coal India annual report scraper.

Features:
1. Discover annual report PDF links from the BCCL reports page
2. Download missing PDFs
3. Extract tables from PDFs with Camelot or pdfplumber
4. Save each extracted table as a CSV
5. Create a combined dataset from all extracted CSVs

Install:
    pip install -r requirements-bccl.txt

Optional:
    Install Ghostscript to improve Camelot support on Windows.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Iterable, List
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://bcclweb.in"
REPORTS_PAGE = "https://bcclweb.in/?page_id=25564"

PDF_DIR = Path("bccl_reports")
CSV_DIR = Path("extracted_csvs")
COMBINED_CSV_PATH = Path("combined_bccl_dataset.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download BCCL annual report PDFs and extract tables."
    )
    parser.add_argument(
        "--reports-page",
        default=REPORTS_PAGE,
        help="Reports listing page to scrape for PDF links.",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Base URL used to resolve relative PDF links.",
    )
    parser.add_argument(
        "--pdf-dir",
        default=str(PDF_DIR),
        help="Directory where downloaded PDFs are stored.",
    )
    parser.add_argument(
        "--csv-dir",
        default=str(CSV_DIR),
        help="Directory where extracted CSVs are stored.",
    )
    parser.add_argument(
        "--combined-csv",
        default=str(COMBINED_CSV_PATH),
        help="Path for the combined output CSV.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip scraping/downloading and only process PDFs already on disk.",
    )
    parser.add_argument(
        "--extractor",
        choices=("auto", "camelot", "pdfplumber"),
        default="auto",
        help="Extraction backend. 'auto' tries Camelot first, then pdfplumber.",
    )
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )


def ensure_directories() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CSV_DIR.mkdir(parents=True, exist_ok=True)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def sanitize_filename(name: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return clean or "report"


def normalize_pdf_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if host == "www.bcclweb.in":
        host = "bcclweb.in"

    if host == "bcclweb.in" and parsed.scheme == "http":
        return parsed._replace(scheme="https", netloc=host).geturl()

    return url


def get_pdf_links(
    session: requests.Session,
    reports_page: str,
    base_url: str,
) -> List[str]:
    logging.info("Fetching report page: %s", reports_page)
    response = session.get(reports_page, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    pdf_links = set()

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if ".pdf" not in href.lower():
            continue
        pdf_links.add(normalize_pdf_url(urljoin(base_url, href)))

    sorted_links = sorted(pdf_links)
    logging.info("Found %s PDF files", len(sorted_links))
    return sorted_links


def filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    raw_name = Path(parsed.path).name or "report.pdf"
    if not raw_name.lower().endswith(".pdf"):
        raw_name = f"{raw_name}.pdf"
    return sanitize_filename(raw_name)


def download_file(session: requests.Session, url: str, destination: Path) -> bool:
    if destination.exists():
        logging.info("Already exists: %s", destination.name)
        return False

    candidate_urls = [url]
    normalized_url = normalize_pdf_url(url)
    if normalized_url != url:
        candidate_urls.append(normalized_url)

    last_error: Exception | None = None
    for candidate_url in candidate_urls:
        try:
            logging.info("Downloading: %s", destination.name)
            if candidate_url != url:
                logging.info("Retrying with normalized URL: %s", candidate_url)
            with session.get(
                candidate_url,
                timeout=REQUEST_TIMEOUT,
                stream=True,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                with destination.open("wb") as file_handle:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            file_handle.write(chunk)
            logging.info("Saved: %s", destination)
            return True
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    return False


def download_pdfs(session: requests.Session, pdf_links: Iterable[str]) -> None:
    for url in pdf_links:
        try:
            destination = PDF_DIR / filename_from_url(url)
            download_file(session, url, destination)
        except Exception as exc:
            logging.exception("Error downloading %s: %s", url, exc)


def clean_extracted_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all").dropna(axis=1, how="all")
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df.reset_index(drop=True)


def extract_tables_with_camelot(pdf_path: Path) -> List[pd.DataFrame]:
    try:
        import camelot
    except ImportError as exc:
        raise RuntimeError(
            "Camelot is not installed. Run: pip install camelot-py[cv]"
        ) from exc

    logging.info("Extracting tables from %s with Camelot", pdf_path.name)

    try:
        tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")
    except Exception as exc:
        logging.exception("Camelot extraction failed for %s: %s", pdf_path, exc)
        return []

    logging.info("Camelot found %s tables in %s", tables.n, pdf_path.name)

    combined_tables: List[pd.DataFrame] = []
    for table in tables:
        df = clean_extracted_table(table.df)
        if len(df) > 1 and len(df.columns) > 0:
            combined_tables.append(df)

    return combined_tables


def extract_tables_with_pdfplumber(pdf_path: Path) -> List[pd.DataFrame]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError(
            "pdfplumber is not installed. Run: pip install pdfplumber"
        ) from exc

    logging.info("Extracting tables from %s with pdfplumber", pdf_path.name)

    extracted_tables: List[pd.DataFrame] = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables()
                logging.info(
                    "pdfplumber page %s yielded %s candidate tables",
                    page_number,
                    len(page_tables),
                )
                for table in page_tables:
                    if not table:
                        continue
                    df = pd.DataFrame(table)
                    df = clean_extracted_table(df)
                    if len(df) > 1 and len(df.columns) > 0:
                        extracted_tables.append(df)
    except Exception as exc:
        logging.exception("pdfplumber extraction failed for %s: %s", pdf_path, exc)
        return []

    logging.info(
        "pdfplumber kept %s usable tables from %s",
        len(extracted_tables),
        pdf_path.name,
    )
    return extracted_tables


def extract_tables_from_pdf(pdf_path: Path, extractor: str) -> List[pd.DataFrame]:
    if extractor == "camelot":
        return extract_tables_with_camelot(pdf_path)

    if extractor == "pdfplumber":
        return extract_tables_with_pdfplumber(pdf_path)

    try:
        tables = extract_tables_with_camelot(pdf_path)
        if tables:
            return tables
        logging.info(
            "Camelot returned no usable tables for %s, trying pdfplumber",
            pdf_path.name,
        )
    except Exception as exc:
        logging.warning(
            "Camelot unavailable for %s: %s. Falling back to pdfplumber.",
            pdf_path.name,
            exc,
        )

    return extract_tables_with_pdfplumber(pdf_path)


def save_tables(tables: List[pd.DataFrame], pdf_name: str) -> int:
    clean_name = sanitize_filename(Path(pdf_name).stem)
    saved_count = 0

    for idx, df in enumerate(tables, start=1):
        csv_name = f"{clean_name}_table_{idx}.csv"
        csv_path = CSV_DIR / csv_name

        table_to_save = df.copy()
        table_to_save["source_pdf"] = pdf_name
        table_to_save["table_index"] = idx
        table_to_save.to_csv(csv_path, index=False)

        logging.info("Saved: %s", csv_name)
        saved_count += 1

    return saved_count


def combine_all_csvs(csv_dir: Path, combined_csv_path: Path) -> None:
    csv_files = sorted(csv_dir.glob("*.csv"))
    if not csv_files:
        logging.warning("No CSV files found in %s", csv_dir)
        return

    all_data: List[pd.DataFrame] = []
    for csv_path in csv_files:
        try:
            df = pd.read_csv(csv_path)
            df["source_file"] = csv_path.name
            all_data.append(df)
        except Exception as exc:
            logging.warning("Skipping unreadable CSV %s: %s", csv_path.name, exc)

    if not all_data:
        logging.warning("No readable CSV files found")
        return

    combined = pd.concat(all_data, ignore_index=True, sort=False)
    combined.to_csv(combined_csv_path, index=False)

    logging.info("Combined dataset saved: %s", combined_csv_path)
    logging.info("Rows: %s", len(combined))
    logging.info("Columns: %s", len(combined.columns))


def main() -> None:
    setup_logging()
    args = parse_args()

    global PDF_DIR, CSV_DIR, COMBINED_CSV_PATH
    PDF_DIR = Path(args.pdf_dir)
    CSV_DIR = Path(args.csv_dir)
    COMBINED_CSV_PATH = Path(args.combined_csv)

    ensure_directories()
    session = build_session()

    if not args.skip_download:
        pdf_links = get_pdf_links(
            session=session,
            reports_page=args.reports_page,
            base_url=args.base_url,
        )
        download_pdfs(session, pdf_links)
    else:
        logging.info("Skipping download step and using local PDFs in %s", PDF_DIR)

    total_saved_tables = 0
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        tables = extract_tables_from_pdf(pdf_path, extractor=args.extractor)
        total_saved_tables += save_tables(tables, pdf_path.name)

    combine_all_csvs(csv_dir=CSV_DIR, combined_csv_path=COMBINED_CSV_PATH)
    logging.info("Done. Saved %s tables in total.", total_saved_tables)


if __name__ == "__main__":
    main()
