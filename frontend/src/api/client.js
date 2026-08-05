const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function getHealth() {
  return request("/health");
}

export function getQuarters() {
  return request("/api/quarters");
}

export function getNetwork(quarter, { topBanks, topBdcs } = {}) {
  const params = new URLSearchParams({ quarter });
  if (topBanks) params.set("top_banks", topBanks);
  if (topBdcs) params.set("top_bdcs", topBdcs);
  return request(`/api/network?${params.toString()}`);
}

export function simulate({ quarter, shockBdcCik, shockFraction, shockLevel, algorithm = "both" }) {
  return request("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quarter,
      shock_bdc_cik: shockBdcCik,
      shock_fraction: shockFraction,
      shock_level: shockLevel ?? null,
      algorithm,
    }),
  });
}