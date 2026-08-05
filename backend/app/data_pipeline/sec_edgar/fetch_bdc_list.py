"""
Fetch the canonical list of all SEC-registered Business Development
Companies (BDCs).

Source: SEC's own "Business Development Company Report" — a CSV listing
every entity with an active 814- filer number (i.e., every company that has
either filed Form N-6F notifying intent to become a BDC, or Form N-54A
electing BDC status under the Investment Company Act of 1940).
https://www.sec.gov/data-research/sec-markets-data/opendatasetsshtmlbdc

This is the *entity universe* for the NBFI side of the network — every BDC
that currently exists as a going concern. It does NOT include private,
non-SEC-registered credit funds (those don't file publicly, which is exactly
why this project scopes to BDCs specifically: they're the disclosed subset
of the private credit universe).

No API key needed. SEC does require a descriptive User-Agent identifying
the requester on every request, or it will return 403s.
"""
import csv
import io
import sys
from pathlib import Path

import requests

# SEC publishes one file per year, updated when new BDCs register.
# Update this if you want a specific year's snapshot; defaults to latest.
BDC_REPORT_YEAR = 2026
BDC_REPORT_URL = (
    "https://www.sec.gov/files/investment/data/other/"
    f"business-development-company-report/business-development-company-{BDC_REPORT_YEAR}.csv"
)

RAW_DATA_DIR = Path(__file__).parent.parent / "raw" / "sec_edgar"


def fetch_bdc_list(user_agent: str) -> list[dict]:
    """
    Downloads and parses the SEC's BDC report CSV.

    Returns a list of dicts, one per BDC, with keys matching the SEC's
    documented schema: reporting_file_number, cik, name, address_1,
    address_2, city, state, zip_code, date_last_filing, type_last_filing.
    """
    headers = {"User-Agent": user_agent}
    resp = requests.get(BDC_REPORT_URL, headers=headers, timeout=30)
    resp.raise_for_status()

    return parse_bdc_csv(resp.text)


def parse_bdc_csv(csv_text: str) -> list[dict]:
    """
    Parses the SEC BDC report CSV text into structured records.

    Split out from fetch_bdc_list() so it can be unit tested against a
    fixture without hitting the network — see tests/test_fetch_bdc_list.py.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    records = []
    for row in reader:
        # SEC's column names are inconsistent about spacing/casing across
        # years, so normalize defensively rather than assuming exact keys.
        normalized = {k.strip().lower().replace(" ", "_"): v.strip() if v else v
                      for k, v in row.items()}
        records.append({
            "reporting_file_number": normalized.get("reporting_file_number") or normalized.get("814_number") or normalized.get("file_no"),
            "cik": (normalized.get("cik") or "").zfill(10) if normalized.get("cik") else None,
            "name": normalized.get("name_of_registrant") or normalized.get("name") or normalized.get("registrant_name"),
            "address_1": normalized.get("address_1"),
            "address_2": normalized.get("address_2"),
            "city": normalized.get("city"),
            "state": normalized.get("state"),
            "zip_code": normalized.get("zip_code"),
            "date_last_filing": normalized.get("date_last_filing") or normalized.get("filing_date"),
            "type_last_filing": normalized.get("type_last_filing") or normalized.get("filing_type"),
        })
    return records


def main():
    from app.core.config import get_settings
    settings = get_settings()

    print(f"Fetching BDC list from {BDC_REPORT_URL} ...")
    records = fetch_bdc_list(settings.sec_edgar_user_agent)
    print(f"Parsed {len(records)} BDC records.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DATA_DIR / f"bdc_list_{BDC_REPORT_YEAR}.csv"
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
