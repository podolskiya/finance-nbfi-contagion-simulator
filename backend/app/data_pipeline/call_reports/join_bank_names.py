"""
Joins bank names onto the NDFI exposure CSV produced by
parse_ndfi_exposure.py, using the "Call Bulk POR" (Panel of Reporters)
file from the same quarterly bulk download.

Usage:
    python join_bank_names.py <por_file.txt> <exposure_csv.csv> --out <joined.csv>
"""
import argparse
from pathlib import Path

import pandas as pd


def load_por_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
    df.columns = [c.strip('"') for c in df.columns]
    return df


def find_name_column(df: pd.DataFrame) -> str:
    candidates = [c for c in df.columns if "NAME" in c.upper()]
    if not candidates:
        raise ValueError(
            f"No name-like column found in POR file. Columns: {list(df.columns)}"
        )
    preferred = [c for c in candidates if "INST" in c.upper() or "BANK" in c.upper()]
    return preferred[0] if preferred else candidates[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("por_file")
    parser.add_argument("exposure_csv")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    por = load_por_file(Path(args.por_file))
    id_col = [c for c in por.columns if "RSSD" in c.upper()][0]
    name_col = find_name_column(por)
    print(f"Using POR columns: id='{id_col}', name='{name_col}'")

    por_slim = por[[id_col, name_col]].rename(columns={id_col: "rssd_id", name_col: "bank_name"})
    por_slim["rssd_id"] = por_slim["rssd_id"].astype(str)

    exposure = pd.read_csv(args.exposure_csv, dtype={"rssd_id": str})
    exposure = exposure.drop(columns=["bank_name"], errors="ignore")

    merged = exposure.merge(por_slim, on="rssd_id", how="left")
    missing = merged["bank_name"].isna().sum()
    print(f"{missing} of {len(merged)} banks had no matching name in the POR file.")

    merged.to_csv(args.out, index=False)
    print(f"Wrote {args.out}")
    print(merged.head(10).to_string())

if __name__ == "__main__":
    main()