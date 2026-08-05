from pathlib import Path

import pandas as pd

NDFI_LOANS_MDRM_CODE = "J454"

NDFI_LOANS_COLUMNS = [f"RCON{NDFI_LOANS_MDRM_CODE}", f"RCFD{NDFI_LOANS_MDRM_CODE}"]

ID_COLUMN_CANDIDATES = ["IDRSSD", "RSSD"]
NAME_COLUMN_CANDIDATES = ["Financial Institution Name", "Bank Name", "Name"]


def load_bulk_file(path: Path) -> pd.DataFrame:
    """
    Loads the tab-delimited bulk file. FFIEC's bulk files are known to
    sometimes ship with two header-like rows (codes, then descriptions) —
    if the first data row doesn't look numeric where we expect numbers,
    that's the signal to skip an extra row. Inspect a real file once
    downloaded and adjust `skiprows` here if needed.
    """
    df = pd.read_csv(path, sep="\t", low_memory=False, dtype=str)
    return df


def extract_ndfi_exposure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a clean DataFrame with one row per reporting bank:
    rssd_id, bank_name (if found), ndfi_loans_total (numeric, in dollars).
    """
    id_col = _find_column(df, ID_COLUMN_CANDIDATES)
    name_col = _find_column(df, NAME_COLUMN_CANDIDATES)

    if id_col is None:
        raise ValueError(
            f"Could not find an institution ID column. Columns present: "
            f"{list(df.columns)[:20]}... - update ID_COLUMN_CANDIDATES."
        )

    present_ndfi_cols = [c for c in NDFI_LOANS_COLUMNS if c in df.columns]
    if not present_ndfi_cols:
        raise ValueError(
            f"Could not find any NDFI loans column ({NDFI_LOANS_COLUMNS}). "
            f"The MDRM code prefix convention may differ from expected - "
            f"search df.columns for '{NDFI_LOANS_MDRM_CODE}' to check."
        )

    ndfi_numeric = pd.DataFrame({
        c: pd.to_numeric(df[c], errors="coerce") for c in present_ndfi_cols
    })
    coalesced_ndfi = ndfi_numeric.bfill(axis=1).iloc[:, 0]

    result = pd.DataFrame({
        "rssd_id": df[id_col],
        "bank_name": df[name_col] if name_col else None,
        "ndfi_loans_total": coalesced_ndfi,
    })

    # Call Report dollar amounts are typically reported in thousands.
    result["ndfi_loans_total_usd"] = result["ndfi_loans_total"] * 1000

    before = len(result)
    result = result[result["ndfi_loans_total_usd"].fillna(0) > 0]
    print(f"{len(result)} of {before} reporting banks have nonzero NDFI loan exposure.")

    return result.sort_values("ndfi_loans_total_usd", ascending=False).reset_index(drop=True)


def _find_column(df: pd.DataFrame, candidates: list[str], exact: bool = False) -> str | None:
    for candidate in candidates:
        if exact:
            if candidate in df.columns:
                return candidate
        else:
            matches = [c for c in df.columns if candidate.lower() in c.lower()]
            if matches:
                return matches[0]
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("bulk_file", help="Path to the extracted tab-delimited bulk data file")
    parser.add_argument("--out", default="../processed/bank_ndfi_exposure.csv")
    args = parser.parse_args()

    df = load_bulk_file(Path(args.bulk_file))
    result = extract_ndfi_exposure(df)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")
    print(result.head(10))


if __name__ == "__main__":
    main()
