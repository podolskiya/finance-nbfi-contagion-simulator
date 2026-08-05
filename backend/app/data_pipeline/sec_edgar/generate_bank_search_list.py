"""
Generates an expanded bank name search list for extract_named_lenders.py,
derived directly from real NDFI-exposure data rather than hand-picked.

Why not all 695 banks: many have generic names (e.g. "First National Bank",
"Community Bank") that would produce heavy false-positive noise when
searched against BDC filing text (unrelated portfolio companies, bios,
addresses - we already saw "Citigroup" match inside someone's professional
bio, not a lending relationship). Institutional-scale BDC credit facilities
are also realistically syndicated among larger banks, not tiny community
banks. So: take the top N banks by NDFI exposure - large enough to capture
real regional/super-regional lenders we know we're missing (Comerica, CIBC
Bank USA, Bank OZK, Webster Bank, Synovus, Live Oak, Santander Bank N.A. all
showed up in Phase 2's raw text and are real Call Report filers), without
the noise of the long tail.

Name-shortening: Call Report legal names are formal ("WELLS FARGO BANK,
NATIONAL ASSOCIATION") but 10-K prose almost always uses a shorter form
("Wells Fargo"). We strip the common National-Association-style suffixes;
we deliberately don't try anything more aggressive than that, since
over-shortening risks collisions with unrelated words.

Usage:
    python -m app.data_pipeline.sec_edgar.generate_bank_search_list --top-n 100
"""
import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

BANK_DATA_PATH = Path(__file__).parent.parent / "processed" / "bank_ndfi_exposure_combined.csv"
OUT_PATH = Path(__file__).parent.parent / "processed" / "bank_search_terms.csv"

# Requires a word boundary before NA/N.A./NATIONAL ASSOCIATION, or the naive
# version incorrectly strips real trailing letters - confirmed bug: without
# \b, "MERCHANTS BANK OF INDIANA" was being chopped to "...INDIA" because the
# pattern matched the "NA" inside "INDIANA".
SUFFIX_PATTERN = re.compile(
    r",?\s*\b(NATIONAL ASSOCIATION|N\.A\.|NA)\s*$", re.IGNORECASE
)
# Call Report convention puts "THE" at the end ("HUNTINGTON NATIONAL BANK,
# THE") instead of the front, which real prose never does.
THE_SUFFIX_PATTERN = re.compile(r",\s*THE\s*$", re.IGNORECASE)

# A handful of banks are essentially never referred to by their full legal
# name in prose. Manual overrides for known cases rather than guessing at a
# general-purpose abbreviation algorithm.
MANUAL_ALIASES = {
    "MANUFACTURERS AND TRADERS TRUST COMPANY": "M&T Bank",
}

# Search terms below this length are too likely to produce false-positive
# noise as a plain substring match (e.g. "TIB").
MIN_SEARCH_TERM_LENGTH = 4


def shorten_name(bank_name: str) -> str:
    if bank_name.upper() in MANUAL_ALIASES:
        return MANUAL_ALIASES[bank_name.upper()]
    name = THE_SUFFIX_PATTERN.sub("", bank_name)
    name = SUFFIX_PATTERN.sub("", name).strip()
    return name.title() if name else bank_name.title()


def find_substring_collisions(search_terms: list[str]) -> list[tuple[str, str]]:
    """Returns (shorter, longer) pairs where shorter is a substring of a
    different, longer term - a real risk: a mention of the longer bank's
    name would also incorrectly match the shorter, different bank's pattern."""
    collisions = []
    for i, short in enumerate(search_terms):
        for j, long in enumerate(search_terms):
            if i != j and short.lower() in long.lower() and short != long:
                collisions.append((short, long))
    return collisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-n", type=int, default=100)
    args = parser.parse_args()

    by_rssd = defaultdict(list)
    with BANK_DATA_PATH.open() as f:
        for row in csv.DictReader(f):
            by_rssd[row["rssd_id"]].append(row)

    ranked = []
    for rssd_id, rows in by_rssd.items():
        values = [float(r["ndfi_loans_total_usd"]) for r in rows if r.get("ndfi_loans_total_usd")]
        if not values:
            continue
        avg_exposure = sum(values) / len(values)
        most_recent = max(rows, key=lambda r: r["quarter_end"])
        ranked.append({
            "rssd_id": rssd_id,
            "bank_name": most_recent["bank_name"],
            "avg_ndfi_exposure_usd": avg_exposure,
        })

    ranked.sort(key=lambda r: r["avg_ndfi_exposure_usd"], reverse=True)
    top_banks = ranked[: args.top_n]

    print(f"Ranked {len(ranked)} banks by average NDFI exposure across quarters.")
    print(f"Taking top {len(top_banks)}.\n")

    for bank in top_banks:
        bank["search_term"] = shorten_name(bank["bank_name"])

    too_short = [b for b in top_banks if len(b["search_term"].replace(" ", "")) < MIN_SEARCH_TERM_LENGTH]
    if too_short:
        print(f"WARNING: {len(too_short)} search term(s) shorter than {MIN_SEARCH_TERM_LENGTH} chars - high false-positive risk, excluded from output:")
        for b in too_short:
            print(f"  {b['search_term']!r} (full name: {b['bank_name']})")
        print()
    top_banks = [b for b in top_banks if b not in too_short]

    all_terms = [b["search_term"] for b in top_banks]
    collisions = find_substring_collisions(all_terms)
    if collisions:
        print(f"WARNING: {len(collisions)} substring collision(s) found - a mention of the longer name would also incorrectly match the shorter, different bank:")
        for short, long in collisions:
            print(f"  {short!r} is contained within {long!r}")
        print("These are kept in the output, but extract_named_lenders.py should prefer the longest match when this happens.\n")

    print(f"{'Rank':<5}{'Search term':<35}{'Full name':<55}{'Avg NDFI exposure ($)'}")
    for i, bank in enumerate(top_banks, start=1):
        print(f"{i:<5}{bank['search_term']:<35}{bank['bank_name']:<55}{bank['avg_ndfi_exposure_usd']:,.0f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rssd_id", "bank_name", "search_term"])
        writer.writeheader()
        for bank in top_banks:
            writer.writerow({
                "rssd_id": bank["rssd_id"],
                "bank_name": bank["bank_name"],
                "search_term": bank["search_term"],
            })

    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()