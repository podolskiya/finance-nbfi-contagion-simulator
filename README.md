# NBFI Contagion Simulator

An interactive tool that reconstructs a bilateral exposure network between
U.S. banks and non-bank financial institutions (NBFIs) — business development
companies (BDCs), private credit funds — from public regulatory filings, then
runs **Eisenberg-Noe clearing** and **DebtRank** cascade simulations so a user
can shock a node (a regional bank, a BDC) and watch losses propagate through
a live network graph.

The clearing/cascade algorithms themselves are established (see the R package
[`NetworkRiskMeasures`](https://github.com/CamiloBermudez/NetworkRiskMeasures)).
The contribution here is applying them at **institution-level granularity**
to real, disclosed U.S. bank–NBFI exposures, in an interactive tool — which,
as far as we've found, nobody has built and shipped as a usable product.

## Data sources (all public, no API keys required)

- **FFIEC Call Reports** — Schedule RC-C, Part I, item 9.a ("Loans to
  nondepository financial institutions," MDRM code J454) for each bank's
  aggregate NDFI-sector loan exposure. Bulk data via the FFIEC Central Data
  Repository Public Data Distribution (no login required for the bulk
  download page itself). See "A key data reality" below for what this
  schedule can and can't tell us.
- **SEC EDGAR** — the SEC's official Business Development Company Report
  for the canonical list of all registered BDCs, plus each BDC's XBRL
  company facts (total assets, debt, NAV) and 10-K/10-Q credit-facility
  footnotes (for named bank lenders, parsed in Phase 2).

## Architecture

```
nbfi-contagion-simulator/
├── backend/          FastAPI + the data pipeline and simulation engine
│   └── app/
│       ├── api/              REST endpoints (Phase 6)
│       ├── core/             config, settings
│       ├── data_pipeline/    Call Report + SEC EDGAR ingestion and parsing
│       ├── models/           network / node / edge data models
│       └── services/         Eisenberg-Noe, DebtRank implementations
└── frontend/         React + D3, interactive network visualization
```

## A key data reality (read this before Phase 2)

Call Reports do not give bilateral, counterparty-level exposure data.
Schedule RC-C, Part I, item 9.a gives each bank's total dollar loans to the
entire nondepository-financial-institution (NDFI) sector - insurance
companies, mortgage companies, BDCs, private equity funds, broker-dealers,
etc. all lumped together. It does not say which specific BDC a bank lent
to. A finer breakdown by NDFI subtype exists for banks with $10B+ in
assets, but its availability and MDRM codes need confirming against a real
downloaded file (see `parse_ndfi_exposure.py`).

This is a known, expected constraint, not a flaw in this project. It's the
same constraint every academic and Federal Reserve contagion study runs
into without confidential supervisory data (see Berrospide, Cai,
Lewis-Hayre & Zikes, "Bank Lending to Private Credit," Federal Reserve
FEDS Notes, 2025). The standard response, and what Phase 3 will do, is to
reconstruct the plausible bilateral matrix from bank-side sector totals
(Call Reports) and BDC-side borrowing totals (SEC filings) using a network
reconstruction algorithm (minimum-density / maximum-entropy, per Anand,
Craig & von Peter, 2015), seeded with real edges where BDCs name their
lenders directly in their credit facility footnotes.

## Roadmap

- [x] **Phase 0** - Repo scaffold: FastAPI backend + React/Vite/D3 frontend,
      both verified to run and talk to each other.
- [x] **Phase 1** - Data acquisition, first pass:
  - SEC EDGAR: canonical BDC list (`data_pipeline/sec_edgar/fetch_bdc_list.py`,
    pulls SEC's official BDC Report) plus per-BDC financial facts
    (`fetch_bdc_financials.py`, pulls the XBRL company-facts API). Both are
    tested and ready to run.
  - FFIEC Call Reports: bulk downloader (`data_pipeline/call_reports/download_bulk_data.py`)
    and NDFI-exposure parser (`parse_ndfi_exposure.py`, extracts confirmed
    MDRM code J454). The download page turned out to be an ASP.NET
    UpdatePanel (selecting a product triggers an AJAX call that populates
    the dates dropdown), so the downloader drives a real headless browser
    via Playwright rather than hand-replicating the postback protocol.
    Requires a one-time local `pip install playwright && playwright install
    chromium`. Confirmed against a real `--inspect` run of the live page;
    the full download flow (`--quarter-end`) still needs a local test run.
- [ ] **Phase 2** — ETL: parse raw filings into a clean bilateral exposure table.
- [ ] **Phase 3** — Network construction: build the bank–NBFI exposure graph.
- [ ] **Phase 4** — Eisenberg-Noe clearing algorithm, validated against known
      toy examples from the literature.
- [ ] **Phase 5** — DebtRank cascade algorithm, validated similarly.
- [ ] **Phase 6** — Backend API: endpoints to load the network and run a shock
      scenario.
- [ ] **Phase 7** — Frontend: interactive live graph with shock controls,
      clean professional visual design.
- [ ] **Phase 8** — Deployment (Render).
- [ ] **Phase 9** — Polish: docs, README narrative, interview-ready framing.

## Local development

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Visit `http://127.0.0.1:8000/health` to confirm it's running.

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Visit `http://127.0.0.1:5173` — it should show "Backend status: connected".

## Honest framing

Eisenberg-Noe (2001) and DebtRank (Battiston et al., 2012) are established
methods; this project does not claim algorithmic novelty. The novelty is in
(1) sourcing and reconciling real institution-level exposure data across two
very different disclosure regimes (bank regulatory filings vs. BDC SEC
filings), and (2) making the resulting simulation interactive and legible to
a non-technical audience.
