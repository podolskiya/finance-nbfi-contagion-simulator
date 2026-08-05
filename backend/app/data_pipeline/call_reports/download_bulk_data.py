import argparse
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

BULK_DATA_URL = "https://cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx"

PRODUCT_LABEL = "Call Reports -- Single Period"
FORMAT_VALUE = "TSVRadioButton"  # confirmed from --inspect: Tab Delimited option's value

LISTBOX_SELECTOR = 'select[name="ctl00$MainContentHolder$ListBox1"]'
DATES_SELECTOR = 'select[name="ctl00$MainContentHolder$DatesDropDownList"]'
FORMAT_RADIO_SELECTOR = f'input[name="ctl00$MainContentHolder$FormatType"][value="{FORMAT_VALUE}"]'
DOWNLOAD_BUTTON_SELECTOR = 'input[name="ctl00$MainContentHolder$TabStrip1$Download_0"]'


def _date_candidates(quarter_end: str) -> list[str]:
    """
    quarter_end: 'YYYY-MM-DD'. We don't know exactly how FFIEC formats the
    dropdown labels, so generate a few plausible variants to match against
    - whichever one hits is a substring match against the option's visible
    text, done case-insensitively.
    """
    dt = datetime.strptime(quarter_end, "%Y-%m-%d")
    return [
        dt.strftime("%m/%d/%Y"),
        f"{dt.month}/{dt.day}/{dt.year}",
        dt.strftime("%Y-%m-%d"),
        dt.strftime("%B %d, %Y"),
        dt.strftime("%m/%Y"),
    ]


def _select_product_and_wait_for_dates(page) -> list[str]:
    """
    Selects the target product in ListBox1 and waits for the AJAX
    partial-postback to populate DatesDropDownList. Returns the list of
    resulting date option labels.
    """
    page.wait_for_selector(LISTBOX_SELECTOR)
    page.select_option(LISTBOX_SELECTOR, label=PRODUCT_LABEL)

    # The dates dropdown starts empty and gets populated after the AJAX
    # postback completes - poll for it to have more than a placeholder.
    page.wait_for_function(
        f"""() => {{
            const el = document.querySelector('{DATES_SELECTOR}');
            return el && el.options.length > 0;
        }}""",
        timeout=15000,
    )

    options = page.eval_on_selector_all(f"{DATES_SELECTOR} option", "els => els.map(e => e.textContent.trim())")
    return options


def inspect_form():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BULK_DATA_URL)

        print("Selecting product and waiting for the dates dropdown to populate...")
        try:
            date_options = _select_product_and_wait_for_dates(page)
        except PlaywrightTimeoutError:
            print(
                "Timed out waiting for DatesDropDownList to populate. "
                "The product label or selector names may have changed - "
                "open the page manually in a browser and compare against "
                "LISTBOX_SELECTOR / DATES_SELECTOR in this file."
            )
            browser.close()
            sys.exit(1)

        print(f"\nDate options available ({len(date_options)}):")
        for opt in date_options:
            print(f"  {opt}")

        format_radios = page.eval_on_selector_all(
            'input[name="ctl00$MainContentHolder$FormatType"]',
            "els => els.map(e => ({value: e.value, checked: e.checked}))",
        )
        print(f"\nFormat radio buttons: {format_radios}")

        browser.close()


def download_quarter(quarter_end: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BULK_DATA_URL)

        date_options = _select_product_and_wait_for_dates(page)

        candidates = _date_candidates(quarter_end)
        matched_option = None
        for opt in date_options:
            if any(c.lower() in opt.lower() for c in candidates):
                matched_option = opt
                break

        if matched_option is None:
            print(
                f"Could not match '{quarter_end}' against any available date "
                f"option. Available options were: {date_options}\n"
                "Update _date_candidates() to match FFIEC's actual label format."
            )
            browser.close()
            sys.exit(1)

        page.select_option(DATES_SELECTOR, label=matched_option)
        page.check(FORMAT_RADIO_SELECTOR)

        print(f"Selections made (product, {matched_option}, tab-delimited). Triggering download...")
        with page.expect_download(timeout=120000) as download_info:
            page.click(DOWNLOAD_BUTTON_SELECTOR)
        download = download_info.value

        out_path = out_dir / f"call_report_bulk_{quarter_end}.zip"
        download.save_as(out_path)
        print(f"Downloaded {out_path}")

        browser.close()
        return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="Print form/date options and exit")
    parser.add_argument("--quarter-end", help="Report period end date, e.g. 2026-03-31")
    parser.add_argument("--out", default="../raw/call_reports", help="Output directory")
    args = parser.parse_args()

    if args.inspect:
        inspect_form()
        return

    if not args.quarter_end:
        parser.error("--quarter-end is required unless --inspect is set")

    download_quarter(args.quarter_end, Path(args.out))


if __name__ == "__main__":
    main()
