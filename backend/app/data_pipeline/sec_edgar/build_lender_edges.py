"""
Turns the raw named-lender candidate mentions (from extract_named_lenders.py
v2) into a clean bank-BDC edge list for Phase 3 network construction.

v2 simplification: extract_named_lenders.py now attaches RSSD ids directly
at extraction time (since its search list already carries them), so this
script no longer needs the fuzzy bank-name-to-RSSD matching step from v1 -
it just filters XBRL noise and aggregates duplicate mentions.

Usage:
    python -m app.data_pipeline.sec_edgar.build_lender_edges
"""
import csv
from collections import defaultdict
from pathlib import Path

CANDIDATES_PATH = Path(__file__).parent.parent / "processed" / "named_lender_candidates.csv"
OUT_PATH = Path(__file__).parent.parent / "processed" / "bank_bdc_lender_edges.csv"


def is_xbrl_noise(context: str) -> bool:
    # XBRL taxonomy element names almost always end in "...Member" - real
    # prose doesn't contain that word repeated like this.
    return context.count("Member") >= 2


def main():
    with CANDIDATES_PATH.open() as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    noise_count = 0
    edges = defaultdict(lambda: {"mention_count": 0, "most_recent_filing": "", "rssd_id": ""})

    for row in rows:
        if is_xbrl_noise(row["context"]):
            noise_count += 1
            continue

        key = (row["bdc_cik"], row["bdc_name"], row["bank_matched"])
        edges[key]["mention_count"] += 1
        edges[key]["rssd_id"] = row["rssd_id"]
        if row["source_filing_date"] > edges[key]["most_recent_filing"]:
            edges[key]["most_recent_filing"] = row["source_filing_date"]

    print(f"{total} raw candidate rows -> {noise_count} filtered as XBRL noise -> {len(edges)} clean (bank, BDC) edges")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        fieldnames = ["bdc_cik", "bdc_name", "bank_matched", "rssd_id", "mention_count", "most_recent_filing", "is_foreign_branch"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (bdc_cik, bdc_name, bank_matched), data in edges.items():
            writer.writerow({
                "bdc_cik": bdc_cik, "bdc_name": bdc_name, "bank_matched": bank_matched,
                "rssd_id": data["rssd_id"], "mention_count": data["mention_count"],
                "most_recent_filing": data["most_recent_filing"],
                "is_foreign_branch": data["rssd_id"] == "",
            })

    print(f"Wrote {OUT_PATH}")

    matched_to_rssd = sum(1 for e in edges.values() if e["rssd_id"])
    print(f"\n{matched_to_rssd} of {len(edges)} edges have a real RSSD id (usable as a Phase 3 network edge)")
    print(f"{len(edges) - matched_to_rssd} edges are foreign branches (no RSSD - no Call Report node yet)")


if __name__ == "__main__":
    main()