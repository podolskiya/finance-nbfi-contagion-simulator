export default function ResultsPanel({ results }) {
  if (!results) {
    return (
      <div style={{ color: "var(--text-faint)", fontSize: 13, marginTop: 24 }}>
        Results will appear here after you run a simulation.
      </div>
    );
  }

  const en = results.eisenberg_noe;
  const dr = results.debtrank;

  return (
    <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 14 }}>
      {en && (
        <div style={cardStyle}>
          <SectionTitle>Direct impact (Eisenberg-Noe)</SectionTitle>
          <Stat label="Recovery rate" value={`${(en.shocked_bdc.recovery_rate * 100).toFixed(1)}%`} alarm={en.shocked_bdc.is_distressed} />
          <Stat label="Insolvent banks" value={en.insolvent_bank_count} alarm={en.insolvent_bank_count > 0} />
          <Stat label="Total bank losses" value={formatUsd(en.total_loss_usd)} />

          {en.affected_banks.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-faint)", marginBottom: 6 }}>TOP AFFECTED LENDERS</div>
              {en.affected_banks.slice(0, 5).map((b) => (
                <RowItem key={b.rssd_id} label={b.bank_name} value={formatUsd(b.total_loss_usd)} sub={b.severity} />
              ))}
            </div>
          )}
        </div>
      )}

      {dr && (
        <div style={cardStyle}>
          <SectionTitle>Propagated distress (DebtRank)</SectionTitle>
          {en && !en.shocked_bdc.is_distressed && dr.affected_bdcs.length > 0 && (
            <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 10, padding: "8px 10px", background: "var(--bg-surface-2)", borderRadius: "6px" }}>
              Eisenberg-Noe found no payment default here, but DebtRank treats the
              shocked BDC's own asset impairment as a stress signal on its own &mdash; modelling how
              counterparty concern can transmit before an outright default.
            </div>
          )}
          <Stat label="Rounds to settle" value={dr.rounds_used} />
          <Stat label="Banks touched" value={dr.affected_banks.length} />
          <Stat label="Other BDCs pulled in" value={dr.affected_bdcs.length} alarm={dr.affected_bdcs.length > 0} />

          {dr.affected_bdcs.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-faint)", marginBottom: 6 }}>
                MOST-AFFECTED BDCs (SHARED-LENDER CHANNEL)
              </div>
              {dr.affected_bdcs.slice(0, 5).map((b) => (
                <RowItem key={b.node_id} label={b.label} value={`${(b.final_distress * 100).toFixed(2)}%`} />
              ))}
              <div style={{ fontSize: 11, color: "var(--text-faint)", marginTop: 6, lineHeight: 1.4 }}>
                Estimated from reconstructed exposure shares, not confirmed shared-lender relationships.
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const cardStyle = {
  background: "var(--bg-surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  boxShadow: "var(--shadow-card)",
  padding: "16px",
};

function SectionTitle({ children }) {
  return <h3 style={{ fontSize: 13, fontWeight: 700, margin: "0 0 10px 0", color: "var(--text-primary)" }}>{children}</h3>;
}

function Stat({ label, value, alarm }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 13 }}>
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono)", color: alarm ? "var(--accent-distress)" : "var(--text-primary)", fontWeight: alarm ? 600 : 400 }}>
        {value}
      </span>
    </div>
  );
}

function RowItem({ label, value, sub }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 12 }}>
      <span style={{ color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "60%" }}>
        {label}
      </span>
      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-primary)", textAlign: "right" }}>
        {value}
        {sub && <div style={{ fontSize: 10, color: "var(--text-faint)" }}>{sub}</div>}
      </span>
    </div>
  );
}

function formatUsd(v) {
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
  return `$${Math.round(v)}`;
}
