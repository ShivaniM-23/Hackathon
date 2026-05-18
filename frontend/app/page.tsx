"use client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  Gauge,
  GitCompareArrows,
  Globe,
  History,
  Link2,
  LogOut,
  Network,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useUser } from "./hooks/useUser";
import ChatPanel from "../components/ChatPanel";
import ContradictionTable from "../components/ContradictionTable";
import GraphView from "../components/GraphView";
import ReviewsPanel from "../components/ReviewsPanel";
import ScoreBreakdown from "../components/ScoreBreakdown";

interface Contradiction {
  field: string;
  claimed: string;
  evidence: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
}

interface Report {
  job_id: string;
  status: string;
  company_name?: string;
  trust_score: number;
  risk_level: string;
  contradictions: Contradiction[];
  red_flags: string[];
  legitimacy_signals?: string[];
  legitimacy_verdict?: string;
  ai_reasoning?: string;
  entities?: unknown[];
  relationships?: unknown[];
  graph?: unknown;
  tier?: number;
  score_breakdown: Record<string, {
    score: number;
    max: number;
    reason: string;
    is_red_flag: boolean;
  }>;
  discovered_links?: Record<string, string | null>;
  raw_data_summary?: {
    scraped_sources?: string[];
    pages_scraped?: number;
    reviews?: unknown;
    discovered_links?: Record<string, string | null>;
    extended_sources?: Record<string, {
      found?: boolean;
      count?: number;
      rating?: number;
    }>;
  };
  reviews?: unknown;
  progress_steps?: string[];
  progress_pct?: number;
  progress?: number;
  steps?: { step: string; detail: string; pct: number }[];
}

interface DashStat {
  job_id: string;
  company_name: string;
  trust_score: number;
  risk_level: string;
  legitimacy_verdict: string;
  red_flags_count: number;
}

type ActiveTab = "overview" | "evidence" | "graph";

const tabs: { key: ActiveTab; label: string; icon: typeof Gauge }[] = [
  { key: "overview", label: "Overview", icon: Gauge },
  { key: "evidence", label: "Evidence", icon: FileText },
  { key: "graph", label: "Graph", icon: Network },
];

function riskClass(risk?: string) {
  if (risk?.includes("LOW")) return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  if (risk?.includes("HIGH")) return "border-red-400/25 bg-red-400/10 text-red-200";
  return "border-amber-400/25 bg-amber-400/10 text-amber-200";
}

function scoreClass(score = 0) {
  if (score >= 75) return "text-emerald-300";
  if (score >= 55) return "text-amber-300";
  if (score >= 30) return "text-orange-300";
  return "text-red-300";
}

function tierLabel(tier?: number) {
  if (tier === 1) return "Tier 1 Enterprise";
  if (tier === 2) return "Tier 2 Established";
  if (tier === 3) return "Tier 3 Unknown";
  return "Verification tier";
}

function verdictClass(verdict?: string) {
  if (verdict === "LEGITIMATE" || verdict === "LIKELY_LEGITIMATE") {
    return "border-emerald-400/25 bg-emerald-400/10 text-emerald-200";
  }
  if (verdict === "FRAUDULENT" || verdict === "LIKELY_FRAUDULENT") {
    return "border-red-400/25 bg-red-400/10 text-red-200";
  }
  return "border-amber-400/25 bg-amber-400/10 text-amber-200";
}

function MetricCard({ label, value, icon: Icon, tone = "neutral" }: {
  label: string;
  value: string | number;
  icon: typeof BarChart3;
  tone?: "neutral" | "good" | "warn" | "bad";
}) {
  const tones = {
    neutral: "border-slate-800 bg-slate-950/60 text-slate-100",
    good: "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
    warn: "border-amber-400/20 bg-amber-400/10 text-amber-200",
    bad: "border-red-400/20 bg-red-400/10 text-red-200",
  };

  return (
    <div className={`rounded-lg border p-4 ${tones[tone]}`}>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{label}</span>
        <Icon size={16} className="text-cyan-300" />
      </div>
      <div className="text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  );
}

function ProgressCard({ report }: { report: Report | null }) {
  const steps = report?.progress_steps ?? ["Queued investigation"];
  const pct = report?.progress_pct ?? report?.progress ?? 12;

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/85 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-white">Investigation in progress</p>
          <p className="text-xs text-slate-500">Scraping sources, scoring trust signals, and preparing the report.</p>
        </div>
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-slate-700 border-t-cyan-300" />
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full bg-cyan-300 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        {steps.slice(-4).map((step, index) => (
          <div key={`${step}-${index}`} className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-400">
            {step}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Home() {
  const { user, loading: authLoading, signOut } = useUser();
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [dashStats, setDashStats] = useState<DashStat[]>([]);
  const [statsLoaded, setStatsLoaded] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("overview");
  const failCount = useRef(0);

  useEffect(() => {
    if (!user && !authLoading) {
      router.push("/login");
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const requestedJobId = params.get("job_id");
    const storedUrl = localStorage.getItem("investigate_url");
    const storedJobId = requestedJobId || localStorage.getItem("investigate_job_id");

    if (storedUrl || storedJobId) {
      window.setTimeout(async () => {
        if (storedUrl) {
          setUrl(storedUrl);
          localStorage.removeItem("investigate_url");
        }

        if (storedJobId) {
          setLoading(true);
          localStorage.removeItem("investigate_job_id");
          let shouldPoll = false;
          try {
            const response = await fetch(`${API_URL}/api/report/${storedJobId}`);
            if (!response.ok) throw new Error(`Report ${storedJobId} not found`);
            const data = await response.json();
            setReport(data);
            if (data.status !== "complete" && data.status !== "error") {
              shouldPoll = true;
              setJobId(storedJobId);
            }
          } catch (error) {
            console.error("Failed to load selected history report:", error);
            shouldPoll = true;
            setJobId(storedJobId);
          } finally {
            setLoading(shouldPoll);
            if (requestedJobId) {
              window.history.replaceState({}, "", "/");
            }
          }
        }
      }, 0);
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (jobId || report || authLoading) return;

    const emailParam = user?.email ? `?user_email=${encodeURIComponent(user.email)}` : "";
    fetch(`${API_URL}/api/history${emailParam}`)
      .then((response) => response.json())
      .then((data) => {
        setDashStats(Array.isArray(data) ? data : []);
        setStatsLoaded(true);
      })
      .catch(() => setStatsLoaded(true));
  }, [jobId, report, user, authLoading]);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_URL}/api/report/${jobId}`);

        if (!res.ok) {
          if (res.status === 404) {
            failCount.current += 1;
            if (failCount.current >= 3) {
              setLoading(false);
              setJobId(null);
              alert("Investigation session lost. Please start the investigation again.");
              clearInterval(pollInterval);
            }
          }
          return;
        }

        failCount.current = 0;
        const data = await res.json();
        setReport(data);

        if (data.status === "complete" || data.status === "error") {
          setLoading(false);
          setJobId(null);
          setActiveTab("overview");
          clearInterval(pollInterval);
        }
      } catch (error) {
        console.error("Polling error:", error);
      }
    };

    const pollInterval: NodeJS.Timeout = setInterval(poll, 2000);
    poll();

    return () => clearInterval(pollInterval);
  }, [jobId]);

  const discoveredLinks = useMemo(() => {
    return Object.entries(report?.discovered_links ?? {})
      .filter(([key, value]) => value && key !== "website" && key !== "company_name" && key !== "crunchbase")
      .slice(0, 5);
  }, [report?.discovered_links]);

  const sourceCount = new Set(report?.raw_data_summary?.scraped_sources ?? []).size;
  const hasReport = report?.status === "complete";
  const averageScore = dashStats.length
    ? Math.round(dashStats.reduce((sum, item) => sum + item.trust_score, 0) / dashStats.length)
    : 0;
  const riskiest = dashStats.length
    ? dashStats.reduce((lowest, current) => current.trust_score < lowest.trust_score ? current : lowest)
    : null;

  const handleAnalyze = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setReport(null);
    setJobId(null);
    setActiveTab("overview");

    try {
      const startRes = await fetch(`${API_URL}/api/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          linkedin_url: linkedin,
          user_email: user?.email,
        }),
      });
      const data = await startRes.json();

      if (data.cached && data.status === "complete" && data.job_id) {
        // Cache hit — load the report instantly
        setJobId(data.job_id);
        const reportRes = await fetch(`${API_URL}/api/report/${data.job_id}`);
        const reportData = await reportRes.json();
        setReport(reportData);
        setLoading(false);
      } else if (data.job_id) {
        setJobId(data.job_id);
      } else {
        throw new Error("No job_id returned");
      }
    } catch (error) {
      console.error("Analysis initiation failed:", error);
      alert("Failed to start investigation.");
      setLoading(false);
    }
  };

  const speakBriefing = () => {
    if (!report || report.status !== "complete") return;

    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    const score = report.trust_score ?? 0;
    const risk = report.risk_level ?? "unknown";
    const name = report.company_name ?? "this company";
    const flags = report.red_flags ?? [];
    const contradictions = report.contradictions ?? [];
    const signals = report.legitimacy_signals ?? [];
    const verdict = (report.legitimacy_verdict ?? "uncertain").replace(/_/g, " ").toLowerCase();

    let script = `Shadow Trace AI has completed its investigation of ${name}. `;
    script += `The company received a trust score of ${score} out of 100, classified as ${risk.replace(/_/g, " ").toLowerCase()} risk. `;
    script += `Our verdict: ${verdict}. `;
    script += flags.length > 0
      ? `We detected ${flags.length} red flag${flags.length > 1 ? "s" : ""}. The top concern is: ${flags[0]}. `
      : "No major red flags were identified. ";
    if (contradictions.length > 0) {
      script += `${contradictions.length} contradiction${contradictions.length > 1 ? "s were" : " was"} found between claims and evidence. `;
    }
    if (signals.length > 0) script += `On the positive side, ${signals[0].toLowerCase()}. `;
    script += "This concludes the Shadow Trace AI executive briefing.";

    const utterance = new SpeechSynthesisUtterance(script);
    utterance.rate = 0.95;
    utterance.pitch = 1;
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.name.includes("Google") && v.lang.startsWith("en")) || voices.find(v => v.lang.startsWith("en"));
    if (preferred) utterance.voice = preferred;
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  if (authLoading) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#050816] text-slate-400">
        Loading...
      </main>
    );
  }

  if (!user && !authLoading) return null;

  return (
    <main className="min-h-screen bg-[#050816] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.14),transparent_32%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.08),transparent_28%)]" />

      <div className="relative mx-auto flex min-h-screen max-w-[1760px] flex-col px-3 py-3 sm:px-5">
        <header className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800/90 bg-[#0b1224]/95 px-4 py-3 shadow-2xl shadow-black/30">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20">
              <ShieldAlert size={21} />
            </div>
            <div>
              <div className="text-sm font-bold text-white">ShadowTrace AI</div>
              <div className="text-xs text-slate-500">Digital diligence command center</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {hasReport && (
              <>
                <button
                  onClick={() => window.open(`${API_URL}/api/export/${report.job_id}`)}
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-cyan-400/50 hover:text-cyan-200"
                >
                  <Download size={14} />
                  Export
                </button>
                <button
                  onClick={speakBriefing}
                  className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                    isSpeaking
                      ? "border-cyan-400/40 bg-cyan-400/10 text-cyan-200"
                      : "border-slate-700 bg-slate-950 text-slate-300 hover:border-cyan-400/50"
                  }`}
                >
                  {isSpeaking ? <VolumeX size={14} /> : <Volume2 size={14} />}
                  {isSpeaking ? "Stop" : "Briefing"}
                </button>
              </>
            )}
            <div className="hidden items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-2 py-1.5 sm:flex">
              <div
                className="h-7 w-7 rounded-full bg-slate-700 bg-cover bg-center"
                style={{ backgroundImage: user?.image ? `url(${user.image})` : undefined }}
              />
              <span className="max-w-[220px] truncate text-xs text-slate-400">{user?.email}</span>
            </div>
            <button
              onClick={signOut}
              className="grid h-9 w-9 place-items-center rounded-lg border border-slate-800 text-slate-400 transition hover:border-red-400/40 hover:text-red-300"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <div className="grid flex-1 gap-3 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)_380px]">
          <aside className="space-y-3 lg:sticky lg:top-3 lg:h-[calc(100vh-88px)] lg:overflow-y-auto">
            <section className="rounded-lg border border-slate-800 bg-[#0b1224]/95 p-4 shadow-xl shadow-black/20">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h1 className="text-base font-semibold text-white">New investigation</h1>
                  <p className="mt-1 text-xs leading-5 text-slate-500">Start with a domain. Add LinkedIn only when you have the correct company profile.</p>
                </div>
                <Search size={18} className="mt-1 text-cyan-300" />
              </div>

              <form onSubmit={handleAnalyze} className="space-y-3">
                <label className="block">
                  <span className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-slate-500">Company website</span>
                  <input
                    type="url"
                    required
                    placeholder="https://company.com"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-300"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-[10px] font-bold uppercase tracking-wide text-slate-500">LinkedIn URL</span>
                  <input
                    type="url"
                    placeholder="Optional"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-300"
                    value={linkedin}
                    onChange={(event) => setLinkedin(event.target.value)}
                  />
                </label>

                <button
                  type="submit"
                  disabled={loading}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-3 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  <Sparkles size={15} />
                  {loading ? "Investigating..." : "Start investigation"}
                </button>
              </form>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => window.location.href = "/compare"}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2.5 text-xs font-semibold text-slate-400 transition hover:border-cyan-400/40 hover:text-cyan-200"
                >
                  <GitCompareArrows size={14} />
                  Compare
                </button>
                <button
                  type="button"
                  onClick={() => window.location.href = "/history"}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2.5 text-xs font-semibold text-slate-400 transition hover:border-cyan-400/40 hover:text-cyan-200"
                >
                  <History size={14} />
                  History
                </button>
              </div>
            </section>

            {hasReport && (
              <section className="rounded-lg border border-slate-800 bg-[#0b1224]/95 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <Link2 size={15} className="text-cyan-300" />
                  Discovered links
                </div>
                <div className="space-y-2">
                  {discoveredLinks.length > 0 ? discoveredLinks.map(([key, value]) => (
                    <a
                      key={key}
                      href={value as string}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs transition hover:border-cyan-400/40"
                    >
                      <span className="capitalize text-slate-300">{key}</span>
                      <span className="truncate text-slate-500">{String(value).replace(/^https?:\/\//, "")}</span>
                    </a>
                  )) : (
                    <p className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-500">No external links found.</p>
                  )}
                </div>
              </section>
            )}

            {!hasReport && statsLoaded && dashStats.length > 0 && (
              <section className="rounded-lg border border-slate-800 bg-[#0b1224]/95 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <Clock size={15} className="text-cyan-300" />
                  Recent checks
                </div>
                <div className="space-y-2">
                  {dashStats.slice(0, 4).map((item) => (
                    <button
                      key={item.job_id}
                      onClick={() => {
                        localStorage.setItem("investigate_job_id", item.job_id);
                        window.location.reload();
                      }}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-left transition hover:border-cyan-400/40"
                    >
                      <span className="min-w-0 truncate text-xs font-semibold text-slate-300">{item.company_name}</span>
                      <span className={`shrink-0 text-xs font-bold ${scoreClass(item.trust_score)}`}>{item.trust_score}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </aside>

          <section className="min-w-0 space-y-3">
            {!hasReport && !jobId && (
              <div className="space-y-3">
                {statsLoaded && dashStats.length > 0 ? (
                  <>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      <MetricCard label="Investigations" value={dashStats.length} icon={BarChart3} />
                      <MetricCard label="Avg score" value={averageScore} icon={TrendingUp} tone={averageScore >= 55 ? "good" : "warn"} />
                      <MetricCard label="High risk" value={dashStats.filter(item => item.risk_level.includes("HIGH")).length} icon={AlertTriangle} tone="bad" />
                      <MetricCard label="Trusted" value={dashStats.filter(item => item.trust_score >= 75).length} icon={CheckCircle2} tone="good" />
                    </div>

                    {riskiest && (
                      <section className="rounded-lg border border-red-400/15 bg-red-400/5 p-5">
                        <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-red-300">
                          <TrendingDown size={15} />
                          Highest risk detected
                        </div>
                        <div className="flex flex-wrap items-center justify-between gap-4">
                          <div>
                            <h2 className="text-2xl font-semibold text-white">{riskiest.company_name}</h2>
                            <p className="mt-1 text-sm text-slate-500">{riskiest.red_flags_count} red flags | {riskiest.risk_level.replace(/_/g, " ")}</p>
                          </div>
                          <div className="text-4xl font-semibold text-red-300">{riskiest.trust_score}<span className="text-base text-slate-600">/100</span></div>
                        </div>
                      </section>
                    )}
                  </>
                ) : (
                  <section className="grid min-h-[calc(100vh-120px)] place-items-center rounded-lg border border-dashed border-slate-800 bg-[#0b1224]/70 p-8 text-center">
                    <div className="max-w-md">
                      <div className="mx-auto mb-5 grid h-16 w-16 place-items-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
                        <Globe size={30} />
                      </div>
                      <h2 className="text-2xl font-semibold text-white">Start a clean investigation flow</h2>
                      <p className="mt-3 text-sm leading-6 text-slate-400">Enter a company domain and the report, evidence, graph, and AI chat will stay within easy reach.</p>
                    </div>
                  </section>
                )}
              </div>
            )}

            {jobId && <ProgressCard report={report} />}

            <AnimatePresence mode="wait">
              {hasReport && (
                <motion.div
                  key="report"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-3"
                >
                  <section className="rounded-lg border border-slate-800 bg-[#0b1224]/95 p-5 shadow-xl shadow-black/20">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="mb-3 flex flex-wrap gap-2">
                          <span className="rounded-md border border-slate-700 bg-slate-950 px-2.5 py-1 text-[10px] font-bold uppercase text-slate-400">
                            {report.company_name || "Investigated company"}
                          </span>
                          {report.legitimacy_verdict && (
                            <span className={`rounded-md border px-2.5 py-1 text-[10px] font-bold uppercase ${verdictClass(report.legitimacy_verdict)}`}>
                              {report.legitimacy_verdict.replace(/_/g, " ")}
                            </span>
                          )}
                          {report.tier && (
                            <span className="rounded-md border border-blue-400/20 bg-blue-400/10 px-2.5 py-1 text-[10px] font-bold uppercase text-blue-200">
                              {tierLabel(report.tier)}
                            </span>
                          )}
                        </div>
                        <h2 className="text-3xl font-semibold tracking-tight text-white">
                          Trust score <span className={scoreClass(report.trust_score)}>{report.trust_score}/100</span>
                        </h2>
                        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                          {report.ai_reasoning || "The report is ready. Review score factors, contradictions, public signals, and ask the investigator follow-up questions."}
                        </p>
                      </div>
                      <div className={`rounded-lg border px-5 py-4 text-center ${riskClass(report.risk_level)}`}>
                        <p className="text-[10px] font-bold uppercase">Risk level</p>
                        <p className="mt-1 text-2xl font-semibold">{report.risk_level.replace(/_/g, " ")}</p>
                      </div>
                    </div>

                    <div className="mt-5 grid gap-3 grid-cols-2 sm:grid-cols-4">
                      <MetricCard label="Sources" value={sourceCount || 0} icon={Globe} />
                      <MetricCard label="Pages" value={report.raw_data_summary?.pages_scraped ?? "N/A"} icon={FileText} />
                      <MetricCard label="Red flags" value={report.red_flags?.length ?? 0} icon={AlertTriangle} tone={(report.red_flags?.length ?? 0) > 0 ? "bad" : "good"} />
                      <MetricCard label="Conflicts" value={report.contradictions?.length ?? 0} icon={Activity} tone={(report.contradictions?.length ?? 0) > 0 ? "warn" : "good"} />
                    </div>
                  </section>

                  <div className="grid grid-cols-3 gap-1 rounded-lg border border-slate-800 bg-[#0b1224]/95 p-1">
                    {tabs.map(({ key, label, icon: Icon }) => (
                      <button
                        key={key}
                        onClick={() => setActiveTab(key)}
                        className={`inline-flex items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${
                          activeTab === key
                            ? "bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20"
                            : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-100"
                        }`}
                      >
                        <Icon size={15} />
                        {label}
                      </button>
                    ))}
                  </div>

                  {activeTab === "overview" && (
                    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
                      <ScoreBreakdown score={report.trust_score} riskLevel={report.risk_level} breakdown={report.score_breakdown} />
                      <div className="space-y-3">
                        <section className="rounded-lg border border-red-400/15 bg-red-400/5 p-4">
                          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-200">
                            <AlertTriangle size={15} />
                            Red flags
                          </div>
                          {(report.red_flags ?? []).length > 0 ? (
                            <div className="space-y-2">
                              {report.red_flags.slice(0, 5).map((flag, index) => (
                                <p key={index} className="rounded-md border border-red-400/10 bg-slate-950/60 p-2 text-xs leading-5 text-red-100/80">{flag}</p>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-400">No scoring red flags were detected.</p>
                          )}
                        </section>

                        <section className="rounded-lg border border-emerald-400/15 bg-emerald-400/5 p-4">
                          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-200">
                            <CheckCircle2 size={15} />
                            Legitimacy signals
                          </div>
                          {(report.legitimacy_signals ?? []).length > 0 ? (
                            <div className="space-y-2">
                              {report.legitimacy_signals?.slice(0, 5).map((signal, index) => (
                                <p key={index} className="rounded-md border border-emerald-400/10 bg-slate-950/60 p-2 text-xs leading-5 text-emerald-100/80">{signal}</p>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-400">No explicit positive signals were returned.</p>
                          )}
                        </section>
                      </div>
                    </div>
                  )}

                  {activeTab === "evidence" && (
                    <div className="space-y-3">
                      <ContradictionTable contradictions={report.contradictions} redFlags={report.red_flags} />
                      <ReviewsPanel report={report} />
                    </div>
                  )}

                  {activeTab === "graph" && (
                    <section className="h-[400px] sm:h-[520px] lg:h-[620px] rounded-lg border border-slate-800 bg-[#0b1224]/95 p-4">
                      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                        <Network size={15} className="text-cyan-300" />
                        Knowledge graph
                      </div>
                      <div className="h-[340px] sm:h-[450px] lg:h-[550px] overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
                        <GraphView report={report} />
                      </div>
                    </section>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </section>

          <aside className="hidden xl:block xl:sticky xl:top-3 xl:h-[calc(100vh-88px)]">
            <section className="flex h-full min-h-[580px] flex-col overflow-hidden rounded-lg border border-slate-800 bg-[#0b1224]/95 shadow-2xl shadow-black/30">
              {hasReport ? (
                <ChatPanel
                  jobId={report.job_id}
                  companyName={report.company_name}
                  trustScore={report.trust_score}
                  riskLevel={report.risk_level}
                  apiUrl={API_URL}
                />
              ) : (
                <div className="grid h-full place-items-center p-8 text-center">
                  <div>
                    <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
                      <ShieldAlert size={27} />
                    </div>
                    <h2 className="text-lg font-semibold text-white">AI Investigator</h2>
                    <p className="mt-2 text-sm leading-6 text-slate-400">After the report is ready, chat remains pinned here so follow-up questions are immediate.</p>
                  </div>
                </div>
              )}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
