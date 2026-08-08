export default function ControlPanel({
  quarters,
  quarter,
  onQuarterChange,
  selectedBdc,
  shockFraction,
  onShockFractionChange,
  onRunSimulation,
  isRunning,
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <Card>
        <label style={labelStyle}>Quarter</label>
        <select value={quarter} onChange={(e) => onQuarterChange(e.target.value)} style={selectStyle}>
          {quarters.map((q) => (
            <option key={q} value={q}>
              {q}
            </option>
          ))}
        </select>
      </Card>

      <Card>
        <label style={labelStyle}>Selected BDC to shock</label>
        {selectedBdc ? (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 4 }}>{selectedBdc.label}</div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-muted)" }}>
              Assets: {formatUsd(selectedBdc.size_metric)}
            </div>
          </div>
        ) : (
          <div style={{ color: "var(--text-faint)", fontSize: 13, marginTop: 8 }}>
            Click a BDC node in the graph to select it
          </div>
        )}
      </Card>

      <Card style={{ opacity: selectedBdc ? 1 : 0.45, pointerEvents: selectedBdc ? "auto" : "none" }}>
        <label style={labelStyle}>
          Asset shock &mdash; <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)", fontWeight: 700 }}>{Math.round(shockFraction * 100)}%</span>
        </label>
        <input
          type="range"
          min="0.05"
          max="0.95"
          step="0.01"
          value={shockFraction}
          onChange={(e) => onShockFractionChange(parseFloat(e.target.value))}
          style={{ width: "100%", marginTop: 10, accentColor: "var(--accent-distress)" }}
        />

        <button onClick={onRunSimulation} disabled={isRunning} style={buttonStyle}>
          {isRunning ? "Running…" : "Run simulation"}
        </button>
      </Card>
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        boxShadow: "var(--shadow-card)",
        padding: "16px",
        ...style,
      }}
    >
      {children}
    </div>
  );
}

function formatUsd(v) {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
  return `$${Math.round(v).toLocaleString()}`;
}

const labelStyle = {
  display: "block",
  fontSize: 11,
  fontWeight: 600,
  letterSpacing: "0.5px",
  textTransform: "uppercase",
  color: "var(--text-faint)",
  marginBottom: 6,
};

const selectStyle = {
  width: "100%",
  background: "var(--bg-base)",
  color: "var(--text-primary)",
  border: "1px solid var(--border)",
  borderRadius: "6px",
  padding: "9px 10px",
  fontSize: 13,
  fontFamily: "var(--font-mono)",
  fontWeight: 500,
};

const buttonStyle = {
  width: "100%",
  marginTop: 16,
  background: "var(--accent-distress)",
  color: "#fff",
  border: "none",
  borderRadius: "6px",
  padding: "11px 14px",
  fontSize: 13,
  fontWeight: 700,
  cursor: "pointer",
  letterSpacing: "0.2px",
};
