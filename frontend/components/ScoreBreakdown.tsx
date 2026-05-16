"use client";
import { useEffect, useState } from "react";

interface Factor {
  score: number;
  max: number;
  reason: string;
  is_red_flag: boolean;
}

interface Props {
  breakdown: Record<string, Factor>;
  score: number;
  riskLevel: string;
}

const FACTOR_LABELS: Record<string, string> = {
  domain_age: "Domain age vs founding year",
  employee_consistency: "Employee count consistency",
  social_presence: "Social media presence",
  news_coverage: "News coverage",
  address_verification: "Address verification",
  review_sentiment: "Review sentiment",
  client_verification: "Client claim verification",
  document_integrity: "Document integrity",
};

const RISK_COLORS = {
  LOW:    { text: "#1D9E75", bg: "#E1F5EE", bar: "#1D9E75" },
  MEDIUM: { text: "#BA7517", bg: "#FAEEDA", bar: "#EF9F27" },
  HIGH:   { text: "#A32D2D", bg: "#FCEBEB", bar: "#E24B4A" },
};

function getBarColor(pct: number) {
  if (pct >= 70) return "#1D9E75";
  if (pct >= 40) return "#EF9F27";
  return "#E24B4A";
}

export default function ScoreBreakdown({ breakdown, score, riskLevel }: Props) {
  const [animated, setAnimated] = useState(false);
  const risk = RISK_COLORS[riskLevel as keyof typeof RISK_COLORS] || RISK_COLORS.MEDIUM;

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 100);
    return () => clearTimeout(t);
  }, []);

  const factors = Object.entries(breakdown || {});
  const maxPts = factors.reduce((a, [, v]) => a + (v?.max || 0), 0);

  return (
    <div style={{ background: "var(--bg, #111)", borderRadius: 12, padding: "1.25rem", border: "0.5px solid rgba(255,255,255,0.08)" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
        <div>
          <div style={{ fontSize: 11, color: "#888", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>trust score</div>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 42, fontWeight: 500, color: risk.text, lineHeight: 1 }}>{score}</span>
            <span style={{ fontSize: 18, color: "#666" }}>/100</span>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <span style={{ background: risk.bg, color: risk.text, fontSize: 12, fontWeight: 500, padding: "4px 12px", borderRadius: 20 }}>
            {riskLevel} RISK
          </span>
          <div style={{ fontSize: 11, color: "#666", marginTop: 8 }}>
            {factors.filter(([, v]) => v?.is_red_flag).length} red flag{factors.filter(([, v]) => v?.is_red_flag).length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

      {/* Risk range legend */}
      <div style={{ display: "flex", gap: 16, marginBottom: "1rem", fontSize: 11 }}>
        <span style={{ color: "#A32D2D" }}>0–39 HIGH</span>
        <span style={{ color: "#BA7517" }}>40–69 MEDIUM</span>
        <span style={{ color: "#1D9E75" }}>70–100 LOW</span>
      </div>

      {/* Factor bars */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {factors.map(([key, val]) => {
          if (!val) return null;
          const pct = val.max > 0 ? Math.round((val.score / val.max) * 100) : 0;
          const barColor = val.is_red_flag ? "#E24B4A" : getBarColor(pct);
          const label = FACTOR_LABELS[key] || key.replace(/_/g, " ");

          return (
            <div key={key}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  {val.is_red_flag && (
                    <span style={{ fontSize: 10, background: "#FCEBEB", color: "#A32D2D", padding: "1px 6px", borderRadius: 10 }}>flag</span>
                  )}
                  <span style={{ fontSize: 12, color: "#aaa" }}>{label}</span>
                </div>
                <span style={{ fontSize: 12, fontWeight: 500, color: barColor }}>
                  {val.score}/{val.max}
                </span>
              </div>
              <div style={{ height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{
                  height: "100%",
                  borderRadius: 3,
                  background: barColor,
                  width: animated ? `${pct}%` : "0%",
                  transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)",
                }} />
              </div>
              {val.reason && (
                <div style={{ fontSize: 11, color: "#666", marginTop: 3 }}>{val.reason}</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Contradiction penalty note */}
      <div style={{ marginTop: "1rem", padding: "0.75rem", background: "rgba(255,255,255,0.03)", borderRadius: 8, border: "0.5px solid rgba(255,255,255,0.06)" }}>
        <div style={{ fontSize: 11, color: "#666" }}>
          Contradiction penalty: up to −20pts deducted from raw total based on confirmed mismatches.
          Raw total: {factors.reduce((a, [, v]) => a + (v?.score || 0), 0)}/100 → Final: {score}/100
        </div>
      </div>
    </div>
  );
}