"use client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "../hooks/useUser";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, Clock, Search, AlertTriangle,
  ExternalLink, FileText
} from "lucide-react";

interface HistoryEntry {
  job_id: string;
  company_name: string;
  url: string;
  trust_score: number;
  risk_level: string;
  legitimacy_verdict: string;
  red_flags_count: number;
  contradictions_count: number;
  tier: number | null;
}

const verdictConfig: Record<string, { color: string; bg: string; border: string }> = {
  LEGITIMATE: { color: "text-green-400", bg: "bg-green-500/10", border: "border-green-500/20" },
  LIKELY_LEGITIMATE: { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  UNCERTAIN: { color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20" },
  LIKELY_FRAUDULENT: { color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20" },
  FRAUDULENT: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
};

function getScoreColor(score: number): string {
  if (score >= 75) return "text-green-400";
  if (score >= 55) return "text-yellow-400";
  if (score >= 30) return "text-orange-400";
  return "text-red-400";
}

function getScoreGlow(score: number): string {
  if (score >= 75) return "shadow-green-500/20";
  if (score >= 55) return "shadow-yellow-500/20";
  if (score >= 30) return "shadow-orange-500/20";
  return "shadow-red-500/20";
}

function getScoreRing(score: number): string {
  if (score >= 75) return "border-green-500/40";
  if (score >= 55) return "border-yellow-500/40";
  if (score >= 30) return "border-orange-500/40";
  return "border-red-500/40";
}

export default function HistoryPage() {
  const { user, loading: authLoading } = useUser();
  const router = useRouter();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterRisk, setFilterRisk] = useState<string>("ALL");

  useEffect(() => {
    if (!user && !authLoading) {
      router.push("/login");
    }
  }, [user, authLoading, router]);

  const fetchHistory = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const emailParam = user.email ? `?user_email=${encodeURIComponent(user.email)}` : "";
      const res = await fetch(`${API_URL}/api/history${emailParam}`);
      const data = await res.json();
      setHistory(data);
    } catch (error) {
      console.error("Failed to fetch history:", error);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading || !user) return;
    const timer = window.setTimeout(() => {
      fetchHistory();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchHistory, user, authLoading]);

  const filtered = history.filter((entry) => {
    const matchesSearch =
      entry.company_name.toLowerCase().includes(search.toLowerCase()) ||
      entry.url.toLowerCase().includes(search.toLowerCase());
    const matchesFilter =
      filterRisk === "ALL" || entry.risk_level.includes(filterRisk);
    return matchesSearch && matchesFilter;
  });

  // Stats
  const totalInvestigations = history.length;
  const highRisk = history.filter(h => h.risk_level.includes("HIGH")).length;
  const avgScore = totalInvestigations > 0
    ? Math.round(history.reduce((sum, h) => sum + h.trust_score, 0) / totalInvestigations)
    : 0;

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 font-sans p-4 sm:p-6 md:p-12">
      <div className="max-w-6xl mx-auto">

        {/* Header */}
        <header className="mb-8">
          <button
            onClick={() => window.location.href = '/'}
            className="flex items-center gap-2 text-neutral-400 hover:text-white transition-colors mb-4 text-sm"
          >
            <ArrowLeft size={16} /> Back to Dashboard
          </button>
          <h1 className="text-xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <Clock className="text-blue-500" /> Investigation History
          </h1>
          <p className="text-neutral-400 mt-2">
            All past due diligence investigations performed by ShadowTrace AI
          </p>
        </header>

        {/* Stats Bar */}
        <div className="grid grid-cols-3 gap-3 sm:gap-4 mb-6 sm:mb-8">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
            <div className="text-2xl sm:text-3xl font-black text-white">{totalInvestigations}</div>
            <div className="text-xs text-neutral-500 uppercase tracking-wider mt-1 font-semibold">Investigations</div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
            <div className={`text-2xl sm:text-3xl font-black ${getScoreColor(avgScore)}`}>{avgScore}/100</div>
            <div className="text-xs text-neutral-500 uppercase tracking-wider mt-1 font-semibold">Avg Score</div>
          </div>
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
            <div className="text-2xl sm:text-3xl font-black text-red-400">{highRisk}</div>
            <div className="text-xs text-neutral-500 uppercase tracking-wider mt-1 font-semibold">High Risk</div>
          </div>
        </div>

        {/* Search & Filter */}
        <div className="flex flex-col md:flex-row gap-3 mb-6">
          <div className="flex-1 relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              placeholder="Search by company name or URL..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-neutral-900 border border-neutral-800 rounded-xl pl-11 pr-4 py-3 outline-none focus:ring-1 focus:ring-blue-500 text-sm"
            />
          </div>
          <div className="flex gap-2">
            {["ALL", "HIGH", "MEDIUM", "LOW"].map((level) => (
              <button
                key={level}
                onClick={() => setFilterRisk(level)}
                className={`px-4 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all border ${
                  filterRisk === level
                    ? "bg-blue-600 border-blue-500 text-white"
                    : "bg-neutral-900 border-neutral-800 text-neutral-500 hover:text-white hover:border-neutral-700"
                }`}
              >
                {level === "ALL" ? "All" : level}
              </button>
            ))}
          </div>
        </div>

        {/* Results */}
        {loading ? (
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 animate-pulse">
                <div className="flex gap-4 items-center">
                  <div className="w-16 h-16 bg-neutral-800 rounded-full" />
                  <div className="flex-1">
                    <div className="h-5 w-48 bg-neutral-800 rounded mb-2" />
                    <div className="h-3 w-32 bg-neutral-800 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-16 border border-neutral-800 border-dashed rounded-2xl text-center">
            <FileText className="mx-auto text-neutral-600 mb-4" size={40} />
            <p className="text-neutral-400">
              {history.length === 0
                ? "No investigations yet. Start one from the dashboard!"
                : "No results match your filters."}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence>
              {filtered.map((entry, idx) => {
                const vc = verdictConfig[entry.legitimacy_verdict] || verdictConfig.UNCERTAIN;

                return (
                  <motion.div
                    key={entry.job_id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ delay: idx * 0.03 }}
                    className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 hover:border-neutral-700 transition-all cursor-pointer group"
                    onClick={() => {
                      localStorage.setItem("investigate_url", entry.url);
                      localStorage.setItem("investigate_job_id", entry.job_id);
                      window.location.href = `/?job_id=${encodeURIComponent(entry.job_id)}`;
                    }}
                  >
                    <div className="flex items-center gap-3 sm:gap-5">
                      {/* Score Circle — hidden on mobile */}
                      <div className={`hidden sm:flex w-14 h-14 sm:w-16 sm:h-16 rounded-full border-2 ${getScoreRing(entry.trust_score)} items-center justify-center shrink-0 shadow-lg ${getScoreGlow(entry.trust_score)}`}>
                        <span className={`text-lg sm:text-xl font-black ${getScoreColor(entry.trust_score)}`}>
                          {entry.trust_score}
                        </span>
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 sm:gap-3 mb-1.5 flex-wrap">
                          <h3 className="text-base sm:text-lg font-bold text-white truncate group-hover:text-blue-400 transition-colors">
                            {entry.company_name}
                          </h3>
                          {/* Mobile score */}
                          <span className={`sm:hidden text-sm font-black ${getScoreColor(entry.trust_score)}`}>
                            {entry.trust_score}/100
                          </span>
                          {entry.tier && (
                            <span className="hidden sm:inline px-2 py-0.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full text-[10px] font-bold uppercase shrink-0">
                              Tier {entry.tier}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 sm:gap-3 text-xs text-neutral-500 flex-wrap">
                          <span className="truncate max-w-[150px] sm:max-w-[250px]">{entry.url}</span>
                          <span className="hidden sm:inline">•</span>
                          <span className="flex items-center gap-1">
                            <AlertTriangle size={10} /> {entry.red_flags_count} flags
                          </span>
                          <span className="hidden sm:inline">•</span>
                          <span className="hidden sm:inline">{entry.contradictions_count} contradictions</span>
                        </div>
                      </div>

                      {/* Verdict Badge */}
                      <div className="flex flex-col items-end gap-1 sm:gap-2 shrink-0">
                        <span className={`px-2 sm:px-3 py-1 rounded-full text-[9px] sm:text-xs font-bold border ${vc.bg} ${vc.color} ${vc.border}`}>
                          {entry.legitimacy_verdict.replace(/_/g, " ")}
                        </span>
                        <span className={`text-[9px] sm:text-[10px] font-bold uppercase tracking-wider ${
                          entry.risk_level.includes("HIGH") ? "text-red-500" :
                          entry.risk_level.includes("MEDIUM") ? "text-yellow-500" :
                          "text-green-500"
                        }`}>
                          {entry.risk_level}
                        </span>
                      </div>

                      {/* Arrow — hidden on mobile */}
                      <ExternalLink size={16} className="hidden sm:block text-neutral-700 group-hover:text-blue-500 transition-colors shrink-0" />
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>
        )}
      </div>
    </main>
  );
}
