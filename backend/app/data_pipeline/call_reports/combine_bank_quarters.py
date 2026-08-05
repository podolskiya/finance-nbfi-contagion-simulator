from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent.parent / "processed"

QUARTER_FILES = {
    "2026-03-31": "bank_ndfi_exposure_2026Q1_named.csv",
    "2025-12-31": "bank_ndfi_exposure_2025Q4_named.csv",
    "2025-09-30": "bank_ndfi_exposure_2025Q3_named.csv",
    "2025-06-30": "bank_ndfi_exposure_2025Q2_named.csv",
}


def main():
    all_rows = []
    missing = []

    for quarter_end, filename in QUARTER_FILES.items():
        path = PROCESSED_DIR / filename
        if not path.exists():
            missing.append(filename)
            continue
        df = pd.read_csv(path, dtype={"rssd_id": str})
        df["quarter_end"] = quarter_end
        all_rows.append(df)
        print(f"{quarter_end}: {len(df)} banks loaded from {filename}")

    if missing:
        print(f"\nWARNING: missing expected files: {missing}")
        print("Continuing with whichever quarters were found.")

    if not all_rows:
        print("No quarter files found - nothing to combine.")
        return

    combined = pd.concat(all_rows, ignore_index=True)
    combined = combined.sort_values(["rssd_id", "quarter_end"]).reset_index(drop=True)

    out_path = PROCESSED_DIR / "bank_ndfi_exposure_combined.csv"
    combined.to_csv(out_path, index=False)

    print(f"\nCombined: {len(combined)} total bank-quarter rows across {combined['rssd_id'].nunique()} unique banks")
    print(f"Wrote {out_path}")

    # Sanity check #
    wells_fargo = combined[combined["rssd_id"] == "451965"].sort_values("quarter_end")
    if not wells_fargo.empty:
        print("\nSanity check (Wells Fargo Bank, NA, across quarters):")
        print(wells_fargo[["quarter_end", "ndfi_loans_total_usd"]].to_string(index=False))


if __name__ == "__main__":
    main()