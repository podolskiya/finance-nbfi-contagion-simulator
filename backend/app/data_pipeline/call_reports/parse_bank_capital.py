from pathlib import Path

import pandas as pd

EQUITY_CAPITAL_MDRM_CODE = "3210"
EQUITY_CAPITAL_COLUMNS = [f"RCON{EQUITY_CAPITAL_MDRM_CODE}", f"RCFD{EQUITY_CAPITAL_MDRM_CODE}"]

ID_COLUMN_CANDIDATES = ["IDRSSD", "RSSD"]


def load_bulk_file(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", low_memory=False, dtype=str)


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        matches = [c for c in df.columns if candidate.lower() in c.lower()]
        if matches:
            return matches[0]
    return None


def extract_equity_capital(df: pd.DataFrame) -> pd.DataFrame:
    id_col = _find_column(df, ID_COLUMN_CANDIDATES)
    if id_col is None:
        raise ValueError(
            f"Could not find an institution ID column. Columns present: "
            f"{list(df.columns)[:20]}... - update ID_COLUMN_CANDIDATES."
        )

    present_cols = [c for c in EQUITY_CAPITAL_COLUMNS if c in df.columns]
    if not present_cols:
        raise ValueError(
            f"Could not find any equity capital column ({EQUITY_CAPITAL_COLUMNS}). "
            f"Search df.columns for '{EQUITY_CAPITAL_MDRM_CODE}' to check."
        )

    numeric = pd.DataFrame({c: pd.to_numeric(df[c], errors="coerce") for c in present_cols})
    coalesced = numeric.bfill(axis=1).iloc[:, 0]

    result = pd.DataFrame({
        "rssd_id": df[id_col],
        "total_equity_capital": coalesced,
    })

    # Call Report dollar amounts are reported in thousands.
    result["total_equity_capital_usd"] = result["total_equity_capital"] * 1000

    before = len(result)
    result = result[result["total_equity_capital_usd"].notna()]
    print(f"{len(result)} of {before} reporting banks have equity capital data.")

    return result.sort_values("total_equity_capital_usd", ascending=False).reset_index(drop=True)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("rc_schedule_file", help="Path to the extracted RC schedule tab-delimited file")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    df = load_bulk_file(Path(args.rc_schedule_file))
    result = extract_equity_capital(df)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    print(f"Wrote {out_path}")
    print(result.head(10))


if __name__ == "__main__":
    main()