"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Download,
  FileSearch,
  Gauge,
  Globe2,
  Link2,
  LogOut,
  Network,
  Search,
  ShieldAlert,
  Sparkles,
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
    extended_sources?: Record<string, {
      found?: boolean;
      count?: number;
      rating?: number;
    }>;
  };
  reviews?: unknown;
  progress_steps?: string[];
  progress_pct?: number;
}

type ViewKey = "overview" | "evidence" | "graph";

const viewTabs: { key: ViewKey; label: string; icon: typeof Gauge }[] = [
  { key: "overview", label: "Overview", icon: Gauge },
  { key: "evidence", label: "Evidence", icon: FileSearch },
  { key: "graph", label: "Graph", icon: Network },
];

const verdictStyles: Record<string, string> = {
  LEGITIMATE: "border-emerald-500/25 bg-emerald-500/10 text-emerald-300",
  LIKELY_LEGITIMATE: "border-teal-500/25 bg-teal-500/10 text-teal-300",
  UNCERTAIN: "border-amber-500/25 bg-amber-500/10 text-amber-300",
  LIKELY_FRAUDULENT: "border-orange-500/25 bg-orange-500/10 text-orange-300",
  FRAUDULENT: "border-red-500/25 bg-red-500/10 text-red-300",
};

function riskTone(risk?: string) {
  if (risk === "LOW") return "text-emerald-300 bg-emerald-500/10 border-emerald-500/20";
  if (risk === "HIGH") return "text-red-300 bg-red-500/10 border-red-500/20";
  return "text-amber-300 bg-amber-500/10 border-amber-500/20";
}

function StatCard({ label, value, tone = "neutral" }: { label: string; value: string | number; tone?: "neutral" | "good" | "warn" | "bad" }) {
  const tones = {
    neutral: "border-slate-800 bg-slate-900/70 text-slate-100",
    good: "border-emerald-500/20 bg-emerald-500/10 text-emerald-200",
    warn: "border-amber-500/20 bg-amber-500/10 text-amber-200",
    bad: "border-red-500/20 bg-red-500/10 text-red-200",
  };
  return (
    <div className={`rounded-lg border p-3 ${tones[tone]}`}>
      <div className="text-[10px] font-semibold uppercase text-slate-400">{label}</div>
      <div className="mt-1 text-xl font-semibold">{value}</div>
    </div>
  );
}

function ProgressPanel({ report }: { report: Report | null }) {
  const pct = report?.progress_pct ?? 10;
  const steps = report?.progress_steps ?? ["Queued investigation"];

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-100">Investigation running</p>
          <p className="text-xs text-slate-500">Collecting sources and building the report.</p>
        </div>
        <div className="h-9 w-9 animate-spin rounded-full border-2 border-slate-700 border-t-cyan-400" />
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full rounded-full bg-cyan-400 transition-all" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-4 space-y-2">
        {steps.slice(-4).map((step, index) => (
          <div key={`${step}-${index}`} className="flex items-start gap-2 text-xs text-slate-400">
            <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-cyan-300" />
            <span>{step}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const { user, loading: authLoading, signOut } = useUser();
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [gst, setGst] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ViewKey>("overview");
  const failCount = useRef(0);

  useEffect(() => {
    if (!user && !authLoading) router.push("/login");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await fetch(`/api/report/${jobId}`);

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
          setActiveView("overview");
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    const pollInterval: NodeJS.Timeout = setInterval(poll, 2000);
    poll();

    return () => clearInterval(pollInterval);
  }, [jobId]);

  const discoveredLinks = useMemo(
    () => Object.entries(report?.discovered_links ?? {}).filter(([key, value]) => value && key !== "website" && key !== "company_name"),
    [report?.discovered_links]
  );

  const sourceCount = new Set(report?.raw_data_summary?.scraped_sources ?? []).size;
  const hasReport = report?.status === "complete";
  const riskToneClass = riskTone(report?.risk_level);

  if (authLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
        Loading...
      </main>
    );
  }

  if (!user && !authLoading) return null;

  const handleAnalyze = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setReport(null);
    setJobId(null);
    setActiveView("overview");

    try {
      const startRes = await fetch("/api/investigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          linkedin_url: linkedin,
          gst_number: gst,
          user_email: user?.email,
        }),
      });
      const data = await startRes.json();

      if (data.job_id) setJobId(data.job_id);
      else throw new Error("No job_id returned");
    } catch (error) {
      console.error("Analysis initiation failed:", error);
      alert("Failed to start investigation.");
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/80 px-4 py-3 shadow-2xl shadow-black/20">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-400 text-slate-950">
              <ShieldAlert size={21} />
            </div>
            <div>
              <p className="text-sm font-semibold text-slate-100">ShadowTrace AI</p>
              <p className="text-xs text-slate-500">Digital due diligence command center</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {hasReport && (
              <button
                onClick={() => window.open(`/api/export/${report.job_id}`)}
                className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-cyan-400/50 hover:text-cyan-200"
              >
                <Download size={15} />
                Export
              </button>
            )}
            <div className="hidden items-center gap-2 sm:flex">
              <div
                className="h-8 w-8 rounded-full border border-slate-700 bg-slate-800 bg-cover bg-center"
                style={{ backgroundImage: user?.image ? `url(${user.image})` : undefined }}
                aria-label="User avatar"
              />
              <span className="max-w-[180px] truncate text-xs text-slate-400">{user?.email}</span>
            </div>
            <button
              onClick={signOut}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-800 text-slate-400 transition hover:border-red-500/40 hover:text-red-300"
              aria-label="Sign out"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <div className="grid flex-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)_380px]">
          <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
            <section className="rounded-lg border border-slate-800 bg-slate-900/80 p-4">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h1 className="text-lg font-semibold text-white">New investigation</h1>
                  <p className="text-xs text-slate-500">Start with a domain. Add LinkedIn only if you have it.</p>
                </div>
                <Search size={18} className="text-cyan-300" />
              </div>

              <form onSubmit={handleAnalyze} className="space-y-3">
                <label className="block">
                  <span className="mb-1 block text-[11px] font-semibold uppercase text-slate-500">Company website</span>
                  <input
                    type="url"
                    required
                    placeholder="https://company.com"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm outline-none transition placeholder:text-slate-600 focus:border-cyan-400"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-[11px] font-semibold uppercase text-slate-500">LinkedIn URL</span>
                  <input
                    type="url"
                    placeholder="Optional"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm outline-none transition placeholder:text-slate-600 focus:border-cyan-400"
                    value={linkedin}
                    onChange={(event) => setLinkedin(event.target.value)}
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-[11px] font-semibold uppercase text-slate-500">GST number</span>
                  <input
                    placeholder="Optional"
                    className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-3 text-sm outline-none transition placeholder:text-slate-600 focus:border-cyan-400"
                    value={gst}
                    onChange={(event) => setGst(event.target.value)}
                  />
                </label>

                <button
                  type="submit"
                  disabled={loading}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-cyan-400 px-4 py-3 text-sm font-bold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  <Sparkles size={16} />
                  {loading ? "Investigating..." : "Start investigation"}
                </button>
              </form>
            </section>

            {hasReport && (
              <section className="rounded-lg border border-slate-800 bg-slate-900/80 p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                  <Link2 size={16} className="text-cyan-300" />
                  Discovered links
                </div>
                <div className="space-y-2">
                  {discoveredLinks.length > 0 ? discoveredLinks.slice(0, 5).map(([key, value]) => (
                    <a
                      key={key}
                      href={value as string}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400 transition hover:border-cyan-400/40 hover:text-cyan-200"
                    >
                      <span className="capitalize">{key}</span>
                      <span className="max-w-[160px] truncate text-slate-500">{String(value).replace(/^https?:\/\//, "")}</span>
                    </a>
                  )) : (
                    <p className="text-xs text-slate-500">No external links found yet.</p>
                  )}
                </div>
              </section>
            )}
          </aside>

          <section className="min-w-0 space-y-4">
            {!hasReport && !jobId && (
              <div className="grid min-h-[calc(100vh-120px)] place-items-center rounded-lg border border-dashed border-slate-800 bg-slate-900/40 p-8 text-center">
                <div className="max-w-md">
                  <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
                    <Globe2 size={30} />
                  </div>
                  <h2 className="text-2xl font-semibold text-white">Investigate without the scroll maze</h2>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    Run a company check and the most important verdict, risks, evidence, graph, and chat will stay within reach.
                  </p>
                </div>
              </div>
            )}

            {jobId && <ProgressPanel report={report} />}

            <AnimatePresence mode="wait">
              {hasReport && (
                <motion.div
                  key="report"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-4"
                >
                  <section className="rounded-lg border border-slate-800 bg-slate-900/80 p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="mb-3 flex flex-wrap items-center gap-2">
                          <span className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-[11px] font-semibold uppercase text-slate-400">
                            {report.company_name || "Investigated company"}
                          </span>
                          {report.legitimacy_verdict && (
                            <span className={`rounded-lg border px-2.5 py-1 text-[11px] font-semibold uppercase ${verdictStyles[report.legitimacy_verdict] ?? verdictStyles.UNCERTAIN}`}>
                              {report.legitimacy_verdict.replace(/_/g, " ")}
                            </span>
                          )}
                        </div>
                        <h2 className="text-3xl font-semibold tracking-tight text-white">
                          Trust score {report.trust_score}/100
                        </h2>
                        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                          {report.ai_reasoning || "The report is ready. Review the score, contradictions, public signals, and ask the AI investigator follow-up questions."}
                        </p>
                      </div>
                      <div className={`rounded-lg border px-4 py-3 text-center ${riskToneClass}`}>
                        <div className="text-[10px] font-bold uppercase">Risk level</div>
                        <div className="mt-1 text-2xl font-semibold">{report.risk_level}</div>
                      </div>
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-4">
                      <StatCard label="Sources" value={sourceCount || "0"} />
                      <StatCard label="Pages" value={report.raw_data_summary?.pages_scraped ?? "N/A"} />
                      <StatCard label="Red flags" value={report.red_flags?.length ?? 0} tone={(report.red_flags?.length ?? 0) > 0 ? "bad" : "good"} />
                      <StatCard label="Conflicts" value={report.contradictions?.length ?? 0} tone={(report.contradictions?.length ?? 0) > 0 ? "warn" : "good"} />
                    </div>
                  </section>

                  <div className="flex gap-2 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/80 p-1">
                    {viewTabs.map(({ key, label, icon: Icon }) => (
                      <button
                        key={key}
                        onClick={() => setActiveView(key)}
                        className={`inline-flex min-w-fit flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition ${
                          activeView === key
                            ? "bg-cyan-400 text-slate-950"
                            : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"
                        }`}
                      >
                        <Icon size={16} />
                        {label}
                      </button>
                    ))}
                  </div>

                  {activeView === "overview" && (
                    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                      <ScoreBreakdown score={report.trust_score} riskLevel={report.risk_level} breakdown={report.score_breakdown} />
                      <div className="space-y-4">
                        <section className="rounded-lg border border-red-500/15 bg-red-500/5 p-4">
                          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-red-200">
                            <AlertTriangle size={16} />
                            Red flags
                          </div>
                          {(report.red_flags ?? []).length > 0 ? (
                            <div className="space-y-2">
                              {report.red_flags.slice(0, 5).map((flag, index) => (
                                <p key={index} className="rounded-md bg-slate-950/60 p-2 text-xs leading-5 text-red-100/80">{flag}</p>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-400">No scoring red flags were detected.</p>
                          )}
                        </section>

                        <section className="rounded-lg border border-emerald-500/15 bg-emerald-500/5 p-4">
                          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-emerald-200">
                            <CheckCircle2 size={16} />
                            Legitimacy signals
                          </div>
                          {(report.legitimacy_signals ?? []).length > 0 ? (
                            <div className="space-y-2">
                              {report.legitimacy_signals?.slice(0, 5).map((signal, index) => (
                                <p key={index} className="rounded-md bg-slate-950/60 p-2 text-xs leading-5 text-emerald-100/80">{signal}</p>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-400">No explicit positive signals were returned.</p>
                          )}
                        </section>
                      </div>
                    </div>
                  )}

                  {activeView === "evidence" && (
                    <div className="space-y-4">
                      <ContradictionTable contradictions={report.contradictions} redFlags={report.red_flags} />
                      <ReviewsPanel report={report} />
                    </div>
                  )}

                  {activeView === "graph" && (
                    <section className="h-[620px] rounded-lg border border-slate-800 bg-slate-900/80 p-4">
                      <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200">
                        <Network size={16} className="text-cyan-300" />
                        Knowledge graph
                      </div>
                      <div className="h-[550px] overflow-hidden rounded-lg border border-slate-800 bg-slate-950">
                        <GraphView report={report} />
                      </div>
                    </section>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </section>

          <aside className="lg:sticky lg:top-4 lg:h-[calc(100vh-96px)]">
            <section className="flex h-full min-h-[560px] flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900/90 shadow-2xl shadow-black/30">
              {hasReport ? (
                <ChatPanel
                  jobId={report.job_id}
                  companyName={report.company_name}
                  trustScore={report.trust_score}
                  riskLevel={report.risk_level}
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center p-8 text-center">
                  <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-lg border border-cyan-400/20 bg-cyan-400/10 text-cyan-300">
                    <Bot size={28} />
                  </div>
                  <h2 className="text-lg font-semibold text-white">AI investigator</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">
                    Once an investigation finishes, the chatbot stays here so users can question the report immediately.
                  </p>
                </div>
              )}
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
