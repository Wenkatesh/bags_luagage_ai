
from pathlib import Path
import json

from fastapi import FastAPI, HTTPException, Query

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "processed" / "scored_companies.json"

app = FastAPI(
    title="Bags & Luggage AI API",
    description="API for company analysis, buying signals and lead scores.",
    version="1.0.0",
)


def load_companies():
    """Load the latest scored company data from JSON."""

    if not DATA_FILE.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Scored company data was not found. "
                "Run the existing scoring pipeline first."
            ),
        )

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        raise HTTPException(
            status_code=500,
            detail="Could not read the scored company data.",
        )

    # Support a JSON list or a dictionary containing a company list.
    if isinstance(data, list):
        companies = data
    elif isinstance(data, dict):
        companies = data.get("companies", [])

        # Also support a dictionary keyed by company name.
        if not isinstance(companies, list) and all(
            isinstance(value, dict) for value in data.values()
        ):
            companies = []
            for name, details in data.items():
                company = details.copy()
                company.setdefault("company_name", name)
                companies.append(company)
    else:
        companies = []

    return [item for item in companies if isinstance(item, dict)]


def get_company_name(company):
    """Handle common company-name field names."""
    return (
        company.get("company_name")
        or company.get("name")
        or company.get("company")
        or company.get("domain")
        or "Unknown company"
    )


@app.get("/")
def home():
    return {
        "message": "Bags & Luggage AI API is running.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Bags & Luggage AI API",
        "data_file_exists": DATA_FILE.exists(),
    }


@app.get("/api/companies")
def list_companies(
    search: str | None = Query(default=None, description="Search company names"),
):
    """Return all companies, or filter them by name."""

    companies = load_companies()

    if search:
        search_text = search.strip().casefold()
        companies = [
            company
            for company in companies
            if search_text in get_company_name(company).casefold()
        ]

    return {
        "count": len(companies),
        "companies": companies,
    }


@app.get("/api/company")
def get_company(name: str = Query(..., min_length=1)):
    """Return the analysis for one company by its name."""

    companies = load_companies()
    requested_name = name.strip().casefold()

    for company in companies:
        if get_company_name(company).casefold() == requested_name:
            return company

    raise HTTPException(
        status_code=404,
        detail=f"No company found with the name '{name}'.",
    )
