# World Bank Data Downloader

Plain HTML + Vanilla JavaScript frontend with a FastAPI backend that fetches live World Bank indicator data and downloads it as CSV.

## Stack

- Python 3.11+
- FastAPI
- requests
- pandas
- Plain HTML, CSS, and Vanilla JavaScript

## Project structure

```text
.
|-- app.py
|-- public/
|   `-- index.html
|-- requirements.txt
|-- start_localhost.bat
|-- .gitignore
`-- README.md
```

## Run locally

### Windows

Double-click `start_localhost.bat`

Or run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Then open `http://127.0.0.1:8000`

## Deploy to Vercel

This project is structured for FastAPI on Vercel using a root `app.py` entrypoint and a static `public/` directory.

1. Push this folder to a GitHub repository
2. Import the repository into Vercel
3. Deploy

For local Vercel-style development:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
vercel dev
```

## API

### `GET /download`

Query parameters:

- `country`: ISO code such as `IN`, `US`, `GB`
- `indicator`: one of the supported World Bank indicator codes
- `years`: number of latest non-null years to keep, default `10`

Supported indicators:

- `NY.GDP.MKTP.CD`
- `SI.POV.GINI`
- `NY.GDS.TOTL.ZS`
- `SP.DYN.CDRT.IN`
