"""
Merges the official BDC Report (bdc_list_2026.csv) with the confirmed real
gaps recovered via N-54A cross-checking (bdc_reconciliation_gaps.csv) into
one master entity list, tagged by source for auditability.

This is the final BDC universe Phase 1 hands off to Phase 2/3 - not either
individual list on its own.

Usage:
    python -m app.data_pipeline.sec_edgar.build_master_bdc_list
"""
import csv
import re
from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "raw" / "sec_edgar"

NAME_CIK_SUFFIX_RE = re.compile(r"\s*\(CIK\s+\d+\)\s*$")


def clean_display_name(display_names: str) -> str:
    """
    display_names looks like 'ARES CAPITAL CORP  (ARCC)  (CIK 0001287750)'
    or 'PennantPark Private Income Fund  (CIK 0002089126)' (no ticker).
    Strips the trailing '(CIK ...)' part; keeps any ticker parenthetical.
    """
    # Multiple entities are joined with "; " if a CIK had several display
    # names across filings - just take the first.
    first = display_names.split(";")[0].strip()
    return NAME_CIK_SUFFIX_RE.sub("", first).strip()


def main():
    official_path = RAW_DIR / "bdc_list_2026.csv"
    gaps_path = RAW_DIR / "bdc_reconciliation_gaps.csv"
    out_path = RAW_DIR / "bdc_master_list.csv"

    master_records = []

    with official_path.open() as f:
        for row in csv.DictReader(f):
            if not row.get("cik"):
                continue
            master_records.append({
                "cik": row["cik"],
                "name": row.get("name") or "",
                "source": "official_report",
            })

    with gaps_path.open() as f:
        for row in csv.DictReader(f):
            master_records.append({
                "cik": row["cik"].zfill(10),
                "name": clean_display_name(row.get("display_names", "")),
                "source": "n54a_recovered",
            })

    seen_ciks = set()
    deduped = []
    for r in master_records:
        if r["cik"] not in seen_ciks:
            seen_ciks.add(r["cik"])
            deduped.append(r)

    print(f"Official report: {sum(1 for r in master_records if r['source'] == 'official_report')}")
    print(f"N-54A recovered gaps: {sum(1 for r in master_records if r['source'] == 'n54a_recovered')}")
    print(f"Merged master list (deduped): {len(deduped)}")

    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["cik", "name", "source"])
        writer.writeheader()
        writer.writerows(deduped)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()