"""
Builds a second, independent BDC entity list by querying SEC's EDGAR
full-text search API (efts.sec.gov) for every historical Form N-54A filing
- the form a company files exactly once, to elect regulation as a
Business Development Company under the Investment Company Act of 1940.

Why this exists: SEC's official "Business Development Company Report" CSV
(fetch_bdc_list.py) turned out to be missing Ares Capital Corp - the
largest BDC in the country, confirmed still actively filing 10-Ks. That
report is described on SEC's own page as a maintained roster ("we cannot
guarantee their accuracy"), so it can apparently go stale. Full-text
search instead indexes actual filing events, which can't silently drop a
filing that happened - so it's a better completeness check, even though
it can't tell us "active" status the way the BDC Report can.

The two lists are meant to be reconciled (see reconcile_bdc_lists.py),
not for either one to be trusted alone.

No API key needed - just a descriptive User-Agent, same as the other SEC
EDGAR scripts. SEC's documented rate limit is a shared budget across all
EDGAR endpoints; a 150ms delay between paginated requests keeps us well
under it.

Usage:
    python -m app.data_pipeline.sec_edgar.fetch_n54a_filers --inspect
    python -m app.data_pipeline.sec_edgar.fetch_n54a_filers
"""
import argparse
import sys
import time
from pathlib import Path

import requests

SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
PAGE_SIZE = 100  # observed max in practice for this endpoint; script adapts if smaller
REQUEST_DELAY_SECONDS = 0.2

RAW_DATA_DIR = Path(__file__).parent.parent / "raw" / "sec_edgar"


def _query_page(user_agent: str, from_offset: int) -> dict:
    params = {
        "q": '"business development company"',
        "forms": "N-54A",
        "from": from_offset,
    }
    headers = {"User-Agent": user_agent}
    resp = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def inspect():
    """Fetches just the first page and prints the raw structure, so we can
    confirm the response shape (field names, total hit count) before
    trusting the full paginated pull."""
    from app.core.config import get_settings
    settings = get_settings()

    data = _query_page(settings.sec_edgar_user_agent, from_offset=0)

    total = data.get("hits", {}).get("total", {}).get("value")
    print(f"Total N-54A filings reported: {total}")

    hits = data.get("hits", {}).get("hits", [])
    print(f"\nFirst {len(hits)} results (raw structure of hit #1):")
    if hits:
        import json
        print(json.dumps(hits[0], indent=2)[:1500])

    print("\nEntity names + CIKs found on this page:")
    for hit in hits:
        source = hit.get("_source", {})
        ciks = source.get('ciks', [])
        print(f"  CIK={ciks[0] if ciks else None}  name={source.get('display_names')}  filed={source.get('file_date')}")

def fetch_all(user_agent: str) -> list[dict]:
    all_records = []
    from_offset = 0

    first_page = _query_page(user_agent, from_offset=0)
    total = first_page.get("hits", {}).get("total", {}).get("value", 0)
    print(f"Total N-54A filings to fetch: {total}")

    while from_offset < total:
        page = _query_page(user_agent, from_offset) if from_offset > 0 else first_page
        hits = page.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            source = hit.get("_source", {})
            ciks = source.get("ciks", [])
            all_records.append({
                "cik": ciks[0] if ciks else None,
                "display_names": "; ".join(source.get("display_names", [])),
                "filed_date": source.get("file_date"),
                "accession_no": hit.get("_id"),
            })

        from_offset += len(hits)
        print(f"  Fetched {from_offset}/{total} ...")
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()

    from app.core.config import get_settings
    settings = get_settings()

    if args.inspect:
        inspect()
        return

    records = fetch_all(settings.sec_edgar_user_agent)

    # A company can file N-54A more than once (rare, but happens on
    # re-elections) - dedupe by CIK, keeping the earliest filing.
    by_cik = {}
    for r in records:
        cik = r["cik"]
        if cik not in by_cik or r["filed_date"] < by_cik[cik]["filed_date"]:
            by_cik[cik] = r

    print(f"\n{len(records)} total N-54A filings, {len(by_cik)} unique CIKs.")

    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DATA_DIR / "bdc_n54a_filers.csv"
    import csv
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["cik", "display_names", "filed_date", "accession_no"])
        writer.writeheader()
        writer.writerows(by_cik.values())
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()