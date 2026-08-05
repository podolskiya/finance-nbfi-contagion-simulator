"""
Pull structured financial facts for each BDC from SEC's XBRL "company facts"
API: https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit}.json

This returns EVERY XBRL fact a company has ever tagged, across every US-GAAP
concept. We deliberately do NOT try to guess which specific tags matter yet
(e.g. total assets vs. net asset value vs. debt outstanding) — BDCs use
investment-company accounting and tag things somewhat inconsistently company
to company. Instead, Phase 1 caches the full raw facts per BDC; Phase 2 is
where we inspect real data across a handful of BDCs, decide on the concept
mapping, and build a clean extraction.

This keeps a wrong guess here from silently propagating downstream.

Rate limit: SEC asks for no more than 10 requests/second, and requires a
descriptive User-Agent (company/tool name + contact email) on every request.
"""
import json
import sys
import time
from pathlib import Path

import requests

RAW_DATA_DIR = Path(__file__).parent.parent / "raw" / "sec_edgar" / "company_facts"

REQUEST_DELAY_SECONDS = 0.15  # keeps us safely under 10 req/sec


def fetch_company_facts(cik: str, user_agent: str) -> dict | None:
    """
    cik: zero-padded 10-digit string, e.g. '0001287750'
    Returns the parsed JSON, or None if the company has no XBRL facts on
    file (some very small / recently registered BDCs may not).
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, timeout=30)

    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def fetch_all(bdc_records: list[dict], user_agent: str) -> None:
    """
    Fetches and caches company facts for every BDC in bdc_records (as
    produced by fetch_bdc_list.parse_bdc_csv), writing one JSON file per
    CIK so partial runs can resume without re-fetching everything.
    """
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for i, record in enumerate(bdc_records, start=1):
        cik = record.get("cik")
        name = record.get("name", "UNKNOWN")
        if not cik:
            print(f"[{i}/{len(bdc_records)}] Skipping {name} — no CIK")
            continue

        out_path = RAW_DATA_DIR / f"{cik}.json"
        if out_path.exists():
            print(f"[{i}/{len(bdc_records)}] {name} ({cik}) — already cached, skipping")
            continue

        print(f"[{i}/{len(bdc_records)}] Fetching {name} ({cik}) ...")
        try:
            facts = fetch_company_facts(cik, user_agent)
        except requests.HTTPError as e:
            print(f"  ERROR fetching {cik}: {e}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if facts is None:
            print(f"  No XBRL facts found for {name} ({cik})")
        else:
            with out_path.open("w") as f:
                json.dump(facts, f)
            print(f"  Wrote {out_path}")

        time.sleep(REQUEST_DELAY_SECONDS)


def main():
    import csv
    from app.core.config import get_settings

    settings = get_settings()
    master_path = RAW_DATA_DIR.parent / "bdc_master_list.csv"
    with master_path.open() as f:
        bdc_records = list(csv.DictReader(f))
    print(f"Loaded {len(bdc_records)} BDCs from the master list. Fetching company facts for each ...\n")

    fetch_all(bdc_records, settings.sec_edgar_user_agent)

if __name__ == "__main__":
    main()
