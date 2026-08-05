"""
Extracts quarter-aligned financial figures (total assets, liabilities,
stockholders' equity / NAV, long-term debt) from every cached SEC XBRL
company-facts JSON file, for a fixed set of target quarter-ends matching
the bank-side Call Report quarters.

Tag choice, confirmed by inspecting two major BDCs (Ares Capital Corp and
FS KKR Capital Corp) via inspect_company_facts.py:
  - Assets, Liabilities, StockholdersEquity: present in both, and the
    accounting identity Assets - Liabilities = StockholdersEquity held
    exactly in both cases - strong evidence these are reliable, standard
    tags rather than company-specific quirks.
  - LongTermDebt: present in both, and close to (but distinct from)
    DebtInstrumentCarryingAmount. Deliberately NOT using
    DebtInstrumentFaceAmount (includes undrawn credit capacity, not
    actual owed exposure) or AssetsNet (present for FS KKR but absent for
    Ares - not universal).

For each tag, a company may report the same period-end value more than
once across different filings (e.g. as a prior-year comparative in a
later 10-K). We take the value from the filing closest to the period end
(smallest filed-date gap), since that's the originally-reported figure
rather than a later restatement.

Usage:
    python -m app.data_pipeline.sec_edgar.extract_bdc_financials
"""
import csv
from pathlib import Path

TARGET_TAGS = ["Assets", "Liabilities", "StockholdersEquity", "LongTermDebt"]
TARGET_QUARTER_ENDS = ["2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"]

COMPANY_FACTS_DIR = Path(__file__).parent.parent / "raw" / "sec_edgar" / "company_facts"
OUT_PATH = Path(__file__).parent.parent / "processed" / "bdc_financials.csv"


def best_value_for_period(usd_values: list[dict], target_end: str):
    """Among all reported values for a tag, return the one whose 'end'
    matches target_end and whose 'filed' date is earliest after that end
    (the originally-reported figure, not a later comparative)."""
    candidates = [v for v in usd_values if v.get("end") == target_end and v.get("val") is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda v: v.get("filed", "9999-99-99"))
    return candidates[0]["val"]


def extract_one_company(data: dict) -> list[dict]:
    us_gaap = data.get("facts", {}).get("us-gaap", {})
    name = data.get("entityName", "")
    cik = str(data.get("cik", "")).zfill(10)

    rows = []
    for quarter_end in TARGET_QUARTER_ENDS:
        row = {"cik": cik, "name": name, "quarter_end": quarter_end}
        any_value_found = False
        for tag in TARGET_TAGS:
            usd_values = us_gaap.get(tag, {}).get("units", {}).get("USD", [])
            value = best_value_for_period(usd_values, quarter_end)
            row[tag.lower()] = value
            if value is not None:
                any_value_found = True
        if any_value_found:
            rows.append(row)
    return rows


def main():
    json_files = sorted(COMPANY_FACTS_DIR.glob("*.json"))
    print(f"Found {len(json_files)} cached company-facts files.")

    all_rows = []
    companies_with_no_data = []

    import json
    for path in json_files:
        with path.open() as f:
            data = json.load(f)
        rows = extract_one_company(data)
        if rows:
            all_rows.extend(rows)
        else:
            companies_with_no_data.append(data.get("entityName", path.stem))

    print(f"Extracted {len(all_rows)} company-quarter rows from {len(json_files) - len(companies_with_no_data)} companies.")
    print(f"{len(companies_with_no_data)} companies had no matching data for any target quarter.")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["cik", "name", "quarter_end"] + [t.lower() for t in TARGET_TAGS]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {OUT_PATH}")

    # Quick sanity preview: Ares Capital's row for the most recent quarter
    ares_rows = [r for r in all_rows if r["cik"] == "0001287750" and r["quarter_end"] == "2026-03-31"]
    if ares_rows:
        print(f"\nSanity check (Ares Capital, 2026-03-31): {ares_rows[0]}")


if __name__ == "__main__":
    main()