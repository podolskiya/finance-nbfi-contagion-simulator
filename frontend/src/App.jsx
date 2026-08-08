import { useEffect, useState, useCallback } from "react";
import NetworkGraph from "./components/NetworkGraph";
import ControlPanel from "./components/ControlPanel";
import ResultsPanel from "./components/ResultsPanel";
import { getQuarters, getNetwork, simulate } from "./api/client";

const TOP_BANKS = 40;
const TOP_BDCS = 40;

function App() {
  const [quarters, setQuarters] = useState([]);
  const [quarter, setQuarter] = useState(null);
  const [networkData, setNetworkData] = useState(null);
  const [selectedBdc, setSelectedBdc] = useState(null);
  const [shockFraction, setShockFraction] = useState(0.4);
  const [results, setResults] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getQuarters()
      .then((qs) => {
        setQuarters(qs);
        if (qs.length > 0) setQuarter(qs[0]);
      })
      .catch((e) => setError(`Could not reach backend: ${e.message}`));
  }, []);

  useEffect(() => {
    if (!quarter) return;
    setResults(null);
    setSelectedBdc(null);
    getNetwork(quarter, { topBanks: TOP_BANKS, topBdcs: TOP_BDCS })
      .then(setNetworkData)
      .catch((e) => setError(`Could not load network: ${e.message}`));
  }, [quarter]);

  const handleSelectBdc = useCallback((node) => {
    setSelectedBdc(node);
    setResults(null);
  }, []);

  const handleRunSimulation = useCallback(async () => {
    if (!selectedBdc) return;
    setIsRunning(true);
    setError(null);
    try {
      const res = await simulate({
        quarter,
        shockBdcCik: selectedBdc.id,
        shockFraction,
        algorithm: "both",
      });
      setResults(res);
    } catch (e) {
      setError(`Simulation failed: ${e.message}`);
    } finally {
      setIsRunning(false);
    }
  }, [quarter, selectedBdc, shockFraction]);

  const distressMap = {};
  if (results?.debtrank) {
    [...results.debtrank.affected_banks, ...results.debtrank.affected_bdcs].forEach((n) => {
      distressMap[n.node_id] = n.final_distress;
    });
    distressMap[results.shocked_bdc_cik] = 1;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <header
        style={{
          padding: "14px 24px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "var(--bg-surface)",
          boxShadow: "var(--shadow-card)",
          zIndex: 1,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <img
            src="/logo.svg"
            alt="Logo"
            style={{ height: 28, width: "auto" }}
            onError={(e) => (e.target.style.display = "none")}
          />
          <div style={{ fontFamily: "var(--font-display)", fontWeight: 800, fontSize: 16, letterSpacing: "0.2px" }}>
            NBFI CONTAGION SIMULATOR
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20, fontSize: 11, color: "var(--text-faint)", fontFamily: "var(--font-mono)" }}>
          <LegendDot color="var(--accent-bank)" label="Bank" />
          <LegendDot color="var(--accent-bdc)" label="BDC" />
          <LegendDot color="var(--accent-distress)" label="Distress" />
        </div>
      </header>

      {error && (
        <div style={{ background: "var(--accent-distress-dim)", color: "var(--text-primary)", padding: "8px 24px", fontSize: 12 }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <main style={{ flex: 1, padding: 16, minWidth: 0 }}>
          {networkData ? (
            <NetworkGraph
              nodes={networkData.nodes}
              edges={networkData.edges}
              shockedNodeId={results?.shocked_bdc_cik}
              distressMap={Object.keys(distressMap).length ? distressMap : null}
              onSelectBdc={handleSelectBdc}
            />
          ) : (
            <div style={{ color: "var(--text-faint)", padding: 24 }}>Loading network…</div>
          )}
        </main>

        <aside
          style={{
            width: 320,
            flexShrink: 0,
            borderLeft: "1px solid var(--border)",
            padding: 20,
            overflowY: "auto",
            background: "var(--bg-base)",
          }}
        >
          <ControlPanel
            quarters={quarters}
            quarter={quarter}
            onQuarterChange={setQuarter}
            selectedBdc={selectedBdc}
            shockFraction={shockFraction}
            onShockFractionChange={setShockFraction}
            onRunSimulation={handleRunSimulation}
            isRunning={isRunning}
          />
          <ResultsPanel results={results} />
        </aside>
      </div>
    </div>
  );
}

export default App;

function LegendDot({ color, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }} />
      {label}
    </span>
  );
}
