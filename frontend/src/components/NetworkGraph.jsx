import { useMemo, useState } from "react";
import { scaleSqrt, scaleLinear } from "d3";

const VIEW_W = 900;
const VIEW_H = 900;
const MARGIN_TOP = 32;
const MARGIN_BOTTOM = 32;
const LEFT_X = 130;
const RIGHT_X = 770;
const MAX_LABEL_CHARS = 20;
const ALWAYS_LABEL_TOP_N = 12; // by rank, not by value - avoids power-law data hiding almost every label

function truncateLabel(label) {
  if (!label) return "";
  return label.length > MAX_LABEL_CHARS ? `${label.slice(0, MAX_LABEL_CHARS - 1)}\u2026` : label;
}

function layoutColumn(items, x) {
  const availableH = VIEW_H - MARGIN_TOP - MARGIN_BOTTOM;
  const rowH = items.length > 0 ? availableH / items.length : availableH;
  return items.map((item, i) => ({
    ...item,
    x,
    y: MARGIN_TOP + i * rowH + rowH / 2,
    rank: i,
  }));
}

// Distress heat: interpolate from the node's own base color toward the
// reserved distress-red accent, proportional to distress level (0-1).
function heatColor(baseColor, distress) {
  if (!distress || distress <= 0) return baseColor;
  const t = Math.min(1, distress * 6); // amplify small values so early distress is visible
  return `color-mix(in srgb, var(--accent-distress) ${Math.round(t * 100)}%, ${baseColor})`;
}

export default function NetworkGraph({ nodes, edges, shockedNodeId, distressMap, onSelectBdc }) {
  const [hovered, setHovered] = useState(null);

  const { bankNodes, bdcNodes, nodeById } = useMemo(() => {
    const banks = nodes.filter((n) => n.type === "bank").sort((a, b) => b.size_metric - a.size_metric);
    const bdcs = nodes.filter((n) => n.type === "bdc").sort((a, b) => b.size_metric - a.size_metric);
    const positionedBanks = layoutColumn(banks, LEFT_X);
    const positionedBdcs = layoutColumn(bdcs, RIGHT_X);
    const byId = {};
    [...positionedBanks, ...positionedBdcs].forEach((n) => (byId[n.id] = n));
    return { bankNodes: positionedBanks, bdcNodes: positionedBdcs, nodeById: byId };
  }, [nodes]);

  const radiusScale = useMemo(() => {
    const max = Math.max(1, ...nodes.map((n) => n.size_metric));
    return scaleSqrt().domain([0, max]).range([3, 20]);
  }, [nodes]);

  const edgeWidthScale = useMemo(() => {
    const max = Math.max(1, ...edges.map((e) => e.exposure_usd));
    return scaleLinear().domain([0, max]).range([0.4, 5]);
  }, [edges]);

  const edgeOpacityScale = useMemo(() => {
    const max = Math.max(1, ...edges.map((e) => e.exposure_usd));
    return scaleLinear().domain([0, max]).range([0.06, 0.55]);
  }, [edges]);

  function formatUsd(v) {
    if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
    if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`;
    if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
    return `$${Math.round(v)}`;
  }

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} style={{ width: "100%", height: "100%" }}>
        <text x={LEFT_X} y={18} textAnchor="middle" fill="var(--text-faint)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="1.5">
          BANKS
        </text>
        <text x={RIGHT_X} y={18} textAnchor="middle" fill="var(--text-faint)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="1.5">
          BDCs
        </text>

        {edges.map((edge, i) => {
          const source = nodeById[edge.source];
          const target = nodeById[edge.target];
          if (!source || !target) return null;
          const isHighlighted = hovered && (hovered.id === edge.source || hovered.id === edge.target);
          const midX = (source.x + target.x) / 2;
          const path = `M ${source.x} ${source.y} C ${midX} ${source.y}, ${midX} ${target.y}, ${target.x} ${target.y}`;
          const distress = distressMap?.[edge.target] || 0;
          return (
            <path
              key={i}
              d={path}
              fill="none"
              stroke={distress > 0 ? "var(--accent-distress)" : "var(--text-faint)"}
              strokeWidth={isHighlighted ? edgeWidthScale(edge.exposure_usd) + 1 : edgeWidthScale(edge.exposure_usd)}
              opacity={isHighlighted ? 0.9 : distress > 0 ? Math.min(0.7, distress * 8 + 0.1) : edgeOpacityScale(edge.exposure_usd)}
            />
          );
        })}

        {bankNodes.map((node) => {
          const distress = distressMap?.[node.id] || 0;
          return (
            <g key={node.id} onMouseEnter={() => setHovered(node)} onMouseLeave={() => setHovered(null)}>
              <circle cx={node.x} cy={node.y} r={radiusScale(node.size_metric)} fill={heatColor("var(--accent-bank)", distress)} stroke="var(--bg-base)" strokeWidth="1" />
              {(hovered?.id === node.id || node.rank < ALWAYS_LABEL_TOP_N) && (
                <text x={node.x - radiusScale(node.size_metric) - 8} y={node.y + 4} textAnchor="end" fill="var(--text-muted)" fontSize="11" fontFamily="var(--font-body)">
                  {truncateLabel(node.label)}
                </text>
              )}
            </g>
          );
        })}

        {bdcNodes.map((node) => {
          const distress = distressMap?.[node.id] || 0;
          const isShocked = node.id === shockedNodeId;
          return (
            <g
              key={node.id}
              onMouseEnter={() => setHovered(node)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onSelectBdc(node)}
              style={{ cursor: "pointer" }}
            >
              {isShocked && (
                <circle cx={node.x} cy={node.y} r={radiusScale(node.size_metric) + 6} fill="none" stroke="var(--accent-distress)" strokeWidth="2">
                  <animate attributeName="r" values={`${radiusScale(node.size_metric) + 4};${radiusScale(node.size_metric) + 10};${radiusScale(node.size_metric) + 4}`} dur="2s" repeatCount="indefinite" />
                </circle>
              )}
              <circle cx={node.x} cy={node.y} r={radiusScale(node.size_metric)} fill={heatColor("var(--accent-bdc)", distress)} stroke="var(--bg-base)" strokeWidth="1" />
              {(hovered?.id === node.id || node.rank < ALWAYS_LABEL_TOP_N || isShocked) && (
                <text x={node.x + radiusScale(node.size_metric) + 8} y={node.y + 4} textAnchor="start" fill="var(--text-muted)" fontSize="11" fontFamily="var(--font-body)">
                  {truncateLabel(node.label)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {hovered && (
        <div
          style={{
            position: "absolute",
            left: hovered.x < VIEW_W / 2 ? "8%" : "auto",
            right: hovered.x >= VIEW_W / 2 ? "8%" : "auto",
            top: `${(hovered.y / VIEW_H) * 100}%`,
            transform: "translateY(-50%)",
            background: "var(--bg-surface-2)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: "8px 12px",
            fontSize: "12px",
            pointerEvents: "none",
            maxWidth: "220px",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{hovered.label}</div>
          <div style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
            {hovered.type === "bank" ? "Total exposure: " : "Total assets: "}
            {formatUsd(hovered.size_metric)}
          </div>
        </div>
      )}
    </div>
  );
}