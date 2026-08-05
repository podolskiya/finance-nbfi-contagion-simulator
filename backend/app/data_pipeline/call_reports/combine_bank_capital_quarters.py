from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "processed"

QUARTER_FILES = {
    "2026-03-31": "bank_capital_2026Q1_named.csv",
    "2025-12-31": "bank_capital_2025Q4_named.csv",
    "2025-09-30": "bank_capital_2025Q3_named.csv",
    "2025-06-30": "bank_capital_2025Q2_named.csv",
}


def main():
    all_rows = []
    missing = []

    for quarter_end, filename in QUARTER_FILES.items():
        path = PROCESSED_DIR / filename
        if not path.exists():
            missing.append(filename)
            continue
        df = pd.read_csv(path, dtype={"rssd_id": str}, encoding="utf-8", encoding_errors="replace")
        df["quarter_end"] = quarter_end
        all_rows.append(df)
        print(f"{quarter_end}: {len(df)} banks loaded from {filename}")

    if missing:
        print(f"\nWARNING: missing expected files: {missing}")

    if not all_rows:
        print("No quarter files found - nothing to combine.")
        return

    combined = pd.concat(all_rows, ignore_index=True)
    combined = combined.sort_values(["rssd_id", "quarter_end"]).reset_index(drop=True)

    out_path = PROCESSED_DIR / "bank_capital_combined.csv"
    combined.to_csv(out_path, index=False)

    print(f"\nCombined: {len(combined)} total bank-quarter rows across {combined['rssd_id'].nunique()} unique banks")
    print(f"Wrote {out_path}")

    jpm = combined[combined["rssd_id"] == "852218"].sort_values("quarter_end")
    if not jpm.empty:
        print("\nSanity check (JPMorgan Chase Bank, across quarters):")
        print(jpm[["quarter_end", "total_equity_capital_usd"]].to_string(index=False))


if __name__ == "__main__":
    main()