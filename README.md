<h1> NBFI Contagion Simulator </h1>

An interactive tool that reconstructs a bilateral exposure network between U.S. banks and non-bank financial institutions — specifically business development companies (BDCs), the SEC-registered vehicles that make up the disclosed slice of the private credit market — and runs Eisenberg-Noe clearing and DebtRank cascade simulations on top of it. Shock a node (a bank, a BDC) and watch losses propagate through the network.

<b>Live demo</b>: 

<H2>Core Idea</H2>
Following from my dissertation, available on my LinkedIn, I wanted to translate it into a more usable and intuitive tool to explain the core idea and findings.

Eisenberg-Noe (2001) and DebtRank (Battiston et al., 2012) aren't new - there's even an R package, NetworkRiskMeasures, that implements both. I'm not claiming algorithmic novelty here.

What doesn't exist, as far as I could find, is an interactive tool that applies these methods at real institution-level granularity to the actual U.S. bank-to-private-credit lending relationships, built entirely from public filings.

Not made-up numbers, not a fake network designed to resemble reality – actual Call Report items and SEC filings, combined and reconciled with one another. In addition to being real numbers and actual filings, this project raises an important policy issue: the Federal Reserve released its own study of bank lending to private credit vehicles in May 2025 (Berrospide, Cai, Lewis-Hayre & Zikes), based on confidential supervisory data that many people do not have access to. How much can you accomplish based on the public data alone?

The short answer: further than I expected, but with real, specific gaps that are documented below..

<H2>Components</H2>
- <b>FFEIC's Call Report bulk-download page is an ASP.NET Webform with an Update Panel</b>: selecting a report type triggers AJAX call that populates the date dropdown server-side. A plain HTTP client can't see those options because they don't exist until the interaction occurs. The downloader drives a headless browser through Playwright.
- <b>SEC's own "BDC Report" is missing ~23% of the real universe</b>: BDCs like Ares Capital Corp falls within this. I caught this while cross-checking against EDGAR full-text search over historical Form N-54A filings, and chased it down. The final BDC list is a reconciliation of both.
- <b>502 of the bank-BDC edges in this network are real rather then estimated</b>: extracted directly from credit agreement exhibits filed with BDCs 10-Ks, then verified by hand against the actual legal text.

<H2>Architecture</H2>

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

<h2>What this can and can't tell you</h2>
- Foreign bank branches aren't in the bank-side network at all. SMBC, MUFG, BNP Paribas, and Deutsche Bank all show up repeatedly as real lenders in BDC credit agreements, but they file FFIEC 002 (a form for U.S. branches of foreign banks), not a standard Call Report — so they have no Call Report capital data and no node in this network. They're real, and they're missing.
- 502 edges are confirmed from real filings; the rest of the ~130,000 bank-BDC pairs in the network are allocated by a calibrated algorithm consistent with real aggregate totals, not individually verified. Nobody outside a bank supervisor has the actual full bilateral matrix — this is the standard
- Eisenberg-Noe here means balance-sheet insolvency (a bank's realised losses exceeding 100% of its own total equity capital) — not a regulatory capital ratio breach, which happens well before a bank's equity actually hits zero. Getting the latter right would require Tier 1 capital and risk-weighted assets specifically, which involve regulatory deductions complex enough that I'd rather not fake the precision.
- DebtRank treats a BDC's own asset shock as a distress signal directly, even in scenarios where Eisenberg-Noe finds no actual payment default. That's intentional — it's modeling how counterparty concern can transmit before an outright default, which is a standard feature of how DebtRank works — but it means the two panels in the UI can show what looks like a contradiction (100% recovery, but real propagated distress) unless you know why.

<H2>References</H2>
Eisenberg, L. & Noe, T. H. (2001). Systemic Risk in Financial Systems. Management Science, 47(2).
Battiston, S., Puliga, M., Kaushik, R., Tasca, P., & Caldarelli, G. (2012). DebtRank: Too Central to Fail? Financial Networks, the FED and Systemic Risk. Scientific Reports, 2, 541.
Anand, K., Craig, B., & von Peter, G. (2015). Filling in the Blanks: Network Structure and Interbank Contagion. Quantitative Finance, 15(4).
Berrospide, J., Cai, K., Lewis-Hayre, R., & Zikes, F. (2025). Bank Lending to Private Credit. FEDS Notes, Board of Governors of the Federal Reserve System.
