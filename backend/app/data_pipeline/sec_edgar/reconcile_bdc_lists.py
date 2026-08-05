"""
Reconciles the two independently-sourced BDC lists:
  - bdc_list_2026.csv     - SEC's official "active" BDC Report (can have gaps - see
                            Ares Capital Corp, confirmed missing from the live 2026 file)
  - bdc_n54a_filers.csv   - every historical N-54A filing since 2001 (complete, but
                            includes long-defunct shell companies alongside real BDCs)

For every CIK in the N-54A list but NOT in the official Report, this pulls that
CIK's SEC submissions history (data.sec.gov/submissions/CIK{cik}.json) and checks
how recently they've filed anything. Recent activity => probably a real gap in the
official Report (add it manually). No recent activity => probably a legitimately
defunct/withdrawn BDC (correctly excluded).

This does NOT try to fully automate the entity universe - it narrows ~164
unreviewed candidates down to a much shorter list of "these look real and
active, go double check them" for a human decision.

Usage:
    python -m app.data_pipeline.sec_edgar.reconcile_bdc_lists
"""
import csv
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

RAW_DIR = Path(__file__).parent.parent / "raw" / "sec_edgar"
REQUEST_DELAY_SECONDS = 0.15
RECENT_THRESHOLD_DAYS = 730  # ~2 years - filed something within this window = "likely still active"


def load_official_ciks() -> set[str]:
    path = RAW_DIR / "bdc_list_2026.csv"
    with path.open() as f:
        return {row["cik"] for row in csv.DictReader(f) if row.get("cik")}


def load_n54a_records() -> list[dict]:
    path = RAW_DIR / "bdc_n54a_filers.csv"
    with path.open() as f:
        return list(csv.DictReader(f))


def zero_pad_cik(cik: str) -> str:
    return cik.strip().zfill(10)


def get_most_recent_filing_date(cik: str, user_agent: str) -> str | None:
    url = f"https://data.sec.gov/submissions/CIK{zero_pad_cik(cik)}.json"
    headers = {"User-Agent": user_agent}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    data = resp.json()

    recent_dates = data.get("filings", {}).get("recent", {}).get("filingDate", [])
    return recent_dates[0] if recent_dates else None  # most recent is first


def main():
    from app.core.config import get_settings
    settings = get_settings()

    official_ciks = load_official_ciks()
    n54a_records = load_n54a_records()
    print(f"Official BDC Report: {len(official_ciks)} CIKs")
    print(f"N-54A historical filers: {len(n54a_records)} CIKs")

    gap_records = [r for r in n54a_records if r["cik"] not in official_ciks]
    print(f"In N-54A history but NOT in official Report: {len(gap_records)} CIKs\n")

    likely_real_gaps = []
    likely_defunct = []
    cutoff = (datetime.today() - timedelta(days=RECENT_THRESHOLD_DAYS)).strftime("%Y-%m-%d")

    for i, record in enumerate(gap_records, start=1):
        cik = record["cik"]
        name = record["display_names"]
        print(f"[{i}/{len(gap_records)}] Checking {name} (CIK {cik}) ...")

        try:
            most_recent = get_most_recent_filing_date(cik, settings.sec_edgar_user_agent)
        except requests.HTTPError as e:
            print(f"  ERROR: {e}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if most_recent is None:
            likely_defunct.append({**record, "most_recent_filing": None})
        elif most_recent >= cutoff:
            likely_real_gaps.append({**record, "most_recent_filing": most_recent})
            print(f"  -> RECENT (last filing {most_recent}) - possible real gap")
        else:
            likely_defunct.append({**record, "most_recent_filing": most_recent})

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\n{'='*60}")
    print(f"Likely REAL gaps (recent activity, missing from official Report): {len(likely_real_gaps)}")
    for r in likely_real_gaps:
        print(f"  {r['display_names']}  (last filing: {r['most_recent_filing']})")

    print(f"\nLikely legitimately excluded (stale/no recent activity): {len(likely_defunct)}")

    out_path = RAW_DIR / "bdc_reconciliation_gaps.csv"
    with out_path.open("w", newline="") as f:
        fieldnames = ["cik", "display_names", "filed_date", "accession_no", "most_recent_filing"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(likely_real_gaps)
    print(f"\nWrote likely-real-gaps list to {out_path}")


if __name__ == "__main__":
    main()