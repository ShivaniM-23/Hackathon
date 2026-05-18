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
  domain_age: "Domain age",
  employee_consistency: "Employees",
  social_presence: "Social presence",
  news_coverage: "News coverage",
  address_verification: "Address",
  review_sentiment: "Reviews",
  client_verification: "Clients",
  document_integrity: "Documents",
  digital_footprint: "Footprint",
  extended_presence: "Extended presence",
};

function getBarColor(pct: number, isFlag: boolean) {
  if (isFlag) return "bg-red-400";
  if (pct >= 70) return "bg-emerald-400";
  if (pct >= 40) return "bg-amber-400";
  return "bg-red-400";
}

function riskStyle(risk: string) {
  if (risk.includes("LOW")) return "text-emerald-200 border-emerald-400/20 bg-emerald-400/10";
  if (risk.includes("HIGH")) return "text-red-200 border-red-400/20 bg-red-400/10";
  return "text-amber-200 border-amber-400/20 bg-amber-400/10";
}

export default function ScoreBreakdown({ breakdown, score, riskLevel }: Props) {
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 80);
    return () => clearTimeout(timer);
  }, []);

  const factors = Object.entries(breakdown || {});
  const redFlagCount = factors.filter(([, value]) => value?.is_red_flag).length;

  return (
    <section className="rounded-lg border border-slate-800 bg-[#0b1224]/95 p-4 sm:p-5 shadow-xl shadow-black/20">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Trust score</p>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-4xl sm:text-5xl font-semibold tracking-tight text-white">{score}</span>
            <span className="text-lg text-slate-500">/100</span>
          </div>
        </div>
        <div className="text-right">
          <span className={`inline-flex rounded-lg border px-3 py-1.5 text-xs font-bold uppercase ${riskStyle(riskLevel)}`}>
            {riskLevel.replace(/_/g, " ")} risk
          </span>
          <p className="mt-2 text-xs text-slate-500">{redFlagCount} scored flag{redFlagCount === 1 ? "" : "s"}</p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {factors.map(([key, value]) => {
          if (!value) return null;
          const pct = value.max > 0 ? Math.round((value.score / value.max) * 100) : 0;
          const label = FACTOR_LABELS[key] || key.replace(/_/g, " ");

          return (
            <div key={key} className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    {value.is_red_flag && (
                      <span className="rounded-md border border-red-400/20 bg-red-400/10 px-1.5 py-0.5 text-[10px] font-bold uppercase text-red-300">
                        flag
                      </span>
                    )}
                    <p className="truncate text-xs font-semibold text-slate-200">{label}</p>
                  </div>
                </div>
                <span className="shrink-0 text-xs font-semibold text-slate-400">
                  {value.score}/{value.max}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${getBarColor(pct, value.is_red_flag)}`}
                  style={{ width: animated ? `${pct}%` : "0%" }}
                />
              </div>
              {value.reason && <p className="mt-2 line-clamp-2 text-[11px] leading-4 text-slate-500">{value.reason}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
