"""Descarcă ultimele 6 filing-uri 10-K de pe SEC EDGAR pentru un set de companii hardcodate."""

import os
import time

import requests

USER_AGENT_NAME = os.environ.get("EDGAR_USER_AGENT_NAME", "Placeholder Name")
USER_AGENT_EMAIL = os.environ.get("EDGAR_USER_AGENT_EMAIL", "placeholder@example.com")
HEADERS = {"User-Agent": f"{USER_AGENT_NAME} {USER_AGENT_EMAIL}"}

COMPANIES = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
}

RATE_LIMIT_SECONDS = 0.2
FILINGS_PER_COMPANY = 6

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(SCRIPT_DIR, "..", "data", "raw")

for ticker, cik in COMPANIES.items():
    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(submissions_url, headers=HEADERS)
    time.sleep(RATE_LIMIT_SECONDS)

    if response.status_code != 200:
        print(f"Eroare: nu s-a putut accesa {submissions_url} (status {response.status_code})")
        continue

    data = response.json()
    recent = data["filings"]["recent"]
    forms = recent["form"]
    accession_numbers = recent["accessionNumber"]
    primary_documents = recent["primaryDocument"]
    filing_dates = recent["filingDate"]
    report_dates = recent.get("reportDate", [])

    ten_k_indices = [i for i, form in enumerate(forms) if form == "10-K"][:FILINGS_PER_COMPANY]

    for i in ten_k_indices:
        accession_number = accession_numbers[i].replace("-", "")
        primary_document = primary_documents[i]
        filing_date = filing_dates[i]
        report_date = report_dates[i] if i < len(report_dates) else ""
        fiscal_year = report_date[:4] if report_date else filing_date[:4]

        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
            f"{accession_number}/{primary_document}"
        )

        print(f"Descarc {ticker} - filing din {filing_date} - {doc_url}")

        doc_response = requests.get(doc_url, headers=HEADERS)
        time.sleep(RATE_LIMIT_SECONDS)

        if doc_response.status_code != 200:
            print(f"Eroare: nu s-a putut descărca {doc_url} (status {doc_response.status_code})")
            continue

        filename = f"{ticker}_{fiscal_year}.html"
        filepath = os.path.join(RAW_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(doc_response.content)
