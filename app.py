from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = FastAPI(title="World Bank Data Downloader")

WORLD_BANK_BASE_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
WORLD_BANK_QUERY_PARAMS = {"format": "json", "per_page": 100}
PUBLIC_INDEX_FILE = Path(__file__).resolve().parent / "public" / "index.html"
WORLD_BANK_REQUEST_HEADERS = {"User-Agent": "WorldBankDataDownloader/1.0"}
WORLD_BANK_TIMEOUT = (5, 10)
WORLD_BANK_RETRY_CONFIG = Retry(
    total=2,
    connect=2,
    read=2,
    status=2,
    backoff_factor=0.3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)


def build_world_bank_session() -> requests.Session:
    """Create a shared session with retry-aware transport adapters."""
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=WORLD_BANK_RETRY_CONFIG)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


WORLD_BANK_SESSION = build_world_bank_session()

# Only the indicator codes from the specification are accepted.
ALLOWED_INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP",
    "SI.POV.GINI": "Gini Index",
    "NY.GDS.TOTL.ZS": "Gross Domestic Savings",
    "SP.DYN.CDRT.IN": "Death Rate",
}

# Allow local file previews and localhost development requests.
LOCAL_APP_ORIGINS = [
    "null",
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_APP_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/", include_in_schema=False)
def serve_frontend() -> Response:
    """Serve the frontend locally and redirect to the static asset on Vercel."""
    if os.getenv("VERCEL"):
        return RedirectResponse(url="/index.html", status_code=307)
    return FileResponse(PUBLIC_INDEX_FILE)


@app.get("/health", include_in_schema=False)
def health_check() -> dict[str, str]:
    """Expose a simple health route for local and hosted smoke tests."""
    return {"status": "ok"}


def validate_indicator(indicator: str) -> str:
    """Reject any indicator that is not explicitly allowed."""
    normalized_indicator = indicator.strip()
    if normalized_indicator not in ALLOWED_INDICATORS:
        raise HTTPException(status_code=400, detail="Invalid indicator")
    return normalized_indicator


def fetch_world_bank_data(country: str, indicator: str) -> list[dict[str, Any]]:
    """Request the World Bank API and verify the top-level payload shape."""
    url = WORLD_BANK_BASE_URL.format(country=country, indicator=indicator)

    try:
        response = WORLD_BANK_SESSION.get(
            url,
            params=WORLD_BANK_QUERY_PARAMS,
            headers=WORLD_BANK_REQUEST_HEADERS,
            timeout=WORLD_BANK_TIMEOUT,
        )
        response.raise_for_status()
        payload: Any = response.json()
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch data from the World Bank API",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail="Invalid response from the World Bank API",
        ) from exc

    # The API contract requires a JSON array with metadata first and data second.
    if (
        not isinstance(payload, list)
        or len(payload) != 2
        or not isinstance(payload[0], dict)
        or not isinstance(payload[1], list)
    ):
        raise HTTPException(
            status_code=500,
            detail="Invalid response from the World Bank API",
        )

    return payload[1]


def extract_data_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only usable year/value pairs and sort them from newest to oldest."""
    cleaned_rows: list[dict[str, Any]] = []

    for record in records:
        if not isinstance(record, dict):
            raise HTTPException(
                status_code=500,
                detail="Invalid response from the World Bank API",
            )

        year = record.get("date")
        value = record.get("value")

        # Null values are explicitly removed before building the CSV.
        if value is None:
            continue

        try:
            cleaned_rows.append({"date": int(str(year)), "value": value})
        except (TypeError, ValueError):
            continue

    cleaned_rows.sort(key=lambda row: row["date"], reverse=True)
    return cleaned_rows


def build_csv_content(rows: list[dict[str, Any]], years: int) -> str:
    """Limit the result set and convert it into CSV text with pandas."""
    limited_rows = rows[:years]
    if not limited_rows:
        raise HTTPException(status_code=404, detail="No data available")

    dataframe = pd.DataFrame(limited_rows, columns=["date", "value"])
    return dataframe.to_csv(index=False)


@app.get("/download")
def download_data(
    country: str = Query(..., min_length=2, max_length=3),
    indicator: str = Query(...),
    years: int = Query(10, ge=1),
) -> Response:
    """Download indicator data as a CSV file."""
    normalized_country = country.strip().upper()
    validated_indicator = validate_indicator(indicator)

    raw_records = fetch_world_bank_data(normalized_country, validated_indicator)
    cleaned_rows = extract_data_rows(raw_records)

    if not cleaned_rows:
        raise HTTPException(status_code=404, detail="No data available")

    csv_content = build_csv_content(cleaned_rows, years)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
