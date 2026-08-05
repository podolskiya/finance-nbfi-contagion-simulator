"""
Inspects a cached SEC XBRL company-facts JSON file to find which us-gaap
tags a given BDC actually uses for total assets, debt, and net asset value.
BDCs use investment-company accounting, which doesn't always follow the
same tagging conventions as a normal operating company - this needs
checking against real data rather than assumed.

Usage:
    python inspect_company_facts.py <cik>
    (cik can be zero-padded or not, e.g. 1287750 or 0001287750)
"""
import json
import sys
from pathlib import Path

CANDIDATE_KEYWORDS = ["Asset", "Debt", "Liabilit", "Equity", "NetAsset", "LineOfCredit", "Borrowing", "Investment"]


def main():
    cik = sys.argv[1].zfill(10)
    path = Path(f"app/data_pipeline/raw/sec_edgar/company_facts/{cik}.json")

    if not path.exists():
        print(f"No cached file at {path}")
        sys.exit(1)

    with path.open() as f:
        data = json.load(f)

    print(f"Entity: {data.get('entityName')}")
    print(f"Taxonomies present: {list(data.get('facts', {}).keys())}\n")

    us_gaap = data.get("facts", {}).get("us-gaap", {})
    print(f"Total us-gaap tags available: {len(us_gaap)}\n")

    matching_tags = [tag for tag in us_gaap if any(kw.lower() in tag.lower() for kw in CANDIDATE_KEYWORDS)]
    print(f"Tags matching our candidate keywords ({len(matching_tags)}):")
    for tag in sorted(matching_tags):
        print(f"  {tag}")

    print("\n--- Most recent value for each matching tag (if annual/quarterly USD figure found) ---")
    for tag in sorted(matching_tags):
        units = us_gaap[tag].get("units", {})
        usd_values = units.get("USD", [])
        if not usd_values:
            continue
        most_recent = max(usd_values, key=lambda v: v.get("end", ""))
        print(f"  {tag}: {most_recent.get('val'):,}  (period end {most_recent.get('end')}, form {most_recent.get('form')})")


if __name__ == "__main__":
    main()