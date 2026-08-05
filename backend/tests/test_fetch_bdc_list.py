from app.data_pipeline.sec_edgar.fetch_bdc_list import parse_bdc_csv

SAMPLE_CSV = """File_No,CIK,Registrant_Name,Address_1,Address_2,City,State,Zip_Code,Filing Date,Filing Type
814-00832,1287750,ARES CAPITAL CORP,245 PARK AVENUE,44TH FLOOR,NEW YORK,NY,10167,05/01/26,10-Q
814-01015,1422183,FS KKR CAPITAL CORP,201 ROUSE BLVD,,PHILADELPHIA,PA,19112,05/04/26,10-Q
"""


def test_parse_bdc_csv_basic_fields():
    records = parse_bdc_csv(SAMPLE_CSV)
    assert len(records) == 2

    ares = records[0]
    assert ares["cik"] == "0001287750"  # zero-padded to 10 digits
    assert ares["name"] == "ARES CAPITAL CORP"
    assert ares["state"] == "NY"
    assert ares["reporting_file_number"] == "814-00832"


def test_parse_bdc_csv_handles_missing_address_2():
    records = parse_bdc_csv(SAMPLE_CSV)
    fs_kkr = records[1]
    assert fs_kkr["name"] == "FS KKR CAPITAL CORP"
    assert fs_kkr["address_2"] in (None, "")
