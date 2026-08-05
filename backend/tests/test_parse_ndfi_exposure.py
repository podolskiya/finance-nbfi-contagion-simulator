import pandas as pd

from app.data_pipeline.call_reports.parse_ndfi_exposure import extract_ndfi_exposure

FIXTURE = pd.DataFrame({
    "IDRSSD": ["1000001", "1000002", "1000003"],
    "Financial Institution Name": ["First Example Bank", "Second Example Bank", "Third Example Bank"],
    "RCONJ454": ["50000", "0", None],   # reported in thousands, per Call Report convention
    "RCFDJ454": [None, None, "125000"],
})


def test_extract_ndfi_exposure_reads_rcon_reporting_bank():
    result = extract_ndfi_exposure(FIXTURE)
    row = result[result["rssd_id"] == "1000001"].iloc[0]
    assert row["ndfi_loans_total_usd"] == 50_000_000


def test_extract_ndfi_exposure_reads_rcfd_reporting_bank():
    # This is the case that was silently dropped before the RCON/RCFD
    # coalescing fix - confirming it's captured now.
    result = extract_ndfi_exposure(FIXTURE)
    row = result[result["rssd_id"] == "1000003"].iloc[0]
    assert row["ndfi_loans_total_usd"] == 125_000_000


def test_extract_ndfi_exposure_drops_zero_exposure_banks():
    result = extract_ndfi_exposure(FIXTURE)
    assert "1000002" not in result["rssd_id"].values


def test_extract_ndfi_exposure_sorted_descending():
    result = extract_ndfi_exposure(FIXTURE)
    assert result.iloc[0]["rssd_id"] == "1000003"  # $125M > $50M
