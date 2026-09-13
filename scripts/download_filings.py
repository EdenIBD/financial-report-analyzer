"""Descarca ultimele 6 filing-uri 10-K de pe SEC EDGAR pentru un set de companii
hardcodate. Wrapper subtire peste src/ingestion/pipeline.download_filing — logica
de descarcare traieste acolo, ca sa fie apelabila si din ingestia dinamica."""

from dotenv import load_dotenv

load_dotenv()

from src.ingestion.pipeline import download_filing

COMPANIES = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
}
FILINGS_PER_COMPANY = 6


def main():
    for ticker, cik in COMPANIES.items():
        try:
            paths = download_filing(cik, "10-K", FILINGS_PER_COMPANY, ticker=ticker)
        except Exception as e:
            print(f"Eroare la {ticker}: {e}")
            continue
        for path in paths:
            print(f"Descarcat {path}")


if __name__ == "__main__":
    main()
