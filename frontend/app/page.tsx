"use client";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { useState, useEffect, useRef } from "react";
import { useUser } from "./hooks/useUser";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search, ShieldAlert, CheckCircle, AlertTriangle,
  XCircle, ArrowRight, MessageSquare, Send,
  FileText, Activity, Globe, Info, Download, Mail, Volume2, VolumeX,
  BarChart3, TrendingDown, TrendingUp, Clock
} from "lucide-react";
import GraphView from "../components/GraphView";
import ContradictionTable from "../components/ContradictionTable";
import ChatPanel from "../components/ChatPanel";
import ReviewsPanel from "../components/ReviewsPanel";
import ScoreBreakdown from "../components/ScoreBreakdown";

// --- Types ---
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
  };
  reviews?: unknown;
  progress_steps?: string[];
  progress?: number;
  steps?: { step: string, detail: string, pct: number }[];
}

const LoadingSkeleton = ({ steps }: { steps?: { step: string, detail: string, pct: number }[] }) => (
  <div className="space-y-6 animate-pulse">
    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-8">
      <div className="flex items-center gap-4 mb-6">
        <div className="w-12 h-12 bg-neutral-800 rounded-full animate-spin border-2 border-t-blue-500 border-neutral-700" />
        <div>
          <div className="h-5 w-48 bg-neutral-800 rounded mb-2" />
          <div className="h-3 w-32 bg-neutral-800 rounded opacity-50" />
        </div>
      </div>
      <div className="space-y-3">
        {(steps ?? []).slice(-3).map((s, i) => (
          <div key={i} className="flex items-center gap-3 text-xs text-neutral-500">
            <span className="text-blue-500">→</span>
            <span>{s.detail}</span>
          </div>
        ))}
      </div>
    </div>
    <div className="h-64 bg-neutral-900 border border-neutral-800 rounded-2xl" />
  </div>
);

export default function Home() {
  const { user, loading: authLoading, signOut } = useUser();
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [gst, setGst] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  // Chat state
  const [chatMessage, setChatMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<{ role: string, content: string }[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  // Dashboard stats
  interface DashStat {
    job_id: string;
    company_name: string;
    trust_score: number;
    risk_level: string;
    legitimacy_verdict: string;
    red_flags_count: number;
  }
  const [dashStats, setDashStats] = useState<DashStat[]>([]);
  const [statsLoaded, setStatsLoaded] = useState(false);

  useEffect(() => {
    if (!jobId && !report) {
      fetch(`${API_URL}/api/history`)
        .then(r => r.json())
        .then(data => { setDashStats(data); setStatsLoaded(true); })
        .catch(() => setStatsLoaded(true));
    }
  }, [jobId, report]);

  // Voice briefing state
  const [isSpeaking, setIsSpeaking] = useState(false);

  const speakBriefing = () => {
    if (!report || report.status !== "complete") return;

    // Toggle off if already speaking
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

    if (flags.length > 0) {
      script += `We detected ${flags.length} red flag${flags.length > 1 ? "s" : ""}. `;
      script += `The top concern is: ${flags[0]}. `;
    } else {
      script += `No major red flags were identified. `;
    }

    if (contradictions.length > 0) {
      script += `${contradictions.length} contradiction${contradictions.length > 1 ? "s were" : " was"} found between the company's claims and our evidence. `;
    }

    if (signals.length > 0) {
      script += `On the positive side, ${signals[0].toLowerCase()}. `;
    }

    script += `This concludes the Shadow Trace AI executive briefing.`;

    const utterance = new SpeechSynthesisUtterance(script);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    // Try to pick a good English voice
    const voices = window.speechSynthesis.getVoices();
    const preferred = voices.find(v => v.name.includes("Google") && v.lang.startsWith("en")) ||
                      voices.find(v => v.lang.startsWith("en"));
    if (preferred) utterance.voice = preferred;

    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  // --- Polling Logic (Fix for Bug 2 & Persistence Support) ---
  const failCount = useRef(0);

  useEffect(() => {
    if (!user && !authLoading) {
      router.push("/login");
      return;
    }

    const storedUrl = localStorage.getItem("investigate_url");
    const storedJobId = localStorage.getItem("investigate_job_id");
    
    if (storedUrl) {
      setUrl(storedUrl);
      localStorage.removeItem("investigate_url");
    }
    
    if (storedJobId) {
      setJobId(storedJobId);
      setLoading(true);
      localStorage.removeItem("investigate_job_id");
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await fetch(`${API_URL}/api/report/${jobId}`);

        if (!res.ok) {
          if (res.status === 404) {
            failCount.current += 1;
            if (failCount.current >= 3) {
              // Server state lost or job expired
              setLoading(false);
              setJobId(null);
              alert("Investigation session lost (likely due to server restart). Please start the investigation again.");
              clearInterval(pollInterval);
            }
          }
          return;
        }

        // Reset fail count on success
        failCount.current = 0;

        const data = await res.json();
        setReport(data);
        console.log("REPORT DATA SUCCESS:", data.job_id);

        if (data.status === "complete" || data.status === "error") {
          setLoading(false);
          setJobId(null); // Stop polling
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    const pollInterval: NodeJS.Timeout = setInterval(poll, 2000);
    poll(); // Initial call

    return () => clearInterval(pollInterval);
  }, [jobId]);

  if (authLoading) {
    return (
      <div className="min-h-screen bg-neutral-950 flex items-center justify-center">
        <div className="text-neutral-500">Loading...</div>
      </div>
    );
  }

  if (!user && !authLoading) {
    return null;
  }

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setReport(null);
    setChatHistory([]);
    setJobId(null); // Reset prev job

    try {
      const startRes = await fetch(`${API_URL}/api/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          linkedin_url: linkedin,
          gst_number: gst,
          user_email: user?.email
        }),
      });
      const data = await startRes.json();

      if (data.job_id) {
        setJobId(data.job_id); // This triggers the useEffect polling
      } else {
        throw new Error("No job_id returned");
      }
    } catch (error) {
      console.error("Analysis initiation failed:", error);
      alert("Failed to start investigation.");
      setLoading(false);
    }
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim() || !report) return;

    const newUserMsg = chatMessage;
    setChatHistory(prev => [...prev, { role: "user", content: newUserMsg }]);
    setChatMessage("");
    setChatLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: newUserMsg, job_id: report.job_id }),
      });
      const data = await response.json();
      setChatHistory(prev => [...prev, { role: "assistant", content: data.response || data.reply }]);
    } catch (error) {
      setChatHistory(prev => [...prev, { role: "assistant", content: "Error connecting to AI." }]);
    } finally {
      setChatLoading(false);
    }
  };


  const verdictColors: Record<string, string> = {
    LEGITIMATE: "bg-green-500/20 text-green-400 border-green-500/30",
    LIKELY_LEGITIMATE: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    UNCERTAIN: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    LIKELY_FRAUDULENT: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    FRAUDULENT: "bg-red-500/20 text-red-400 border-red-500/30",
  };

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 font-sans">
      <div className="max-w-7xl mx-auto px-6 py-12">

        <header className="mb-12">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-sm font-medium">
              <ShieldAlert size={16} /> ShadowTrace AI
            </div>
            {user && (
              <div className="flex items-center gap-3">
                <img
                  src={user.image ?? ""}
                  className="w-8 h-8 rounded-full"
                  alt="avatar"
                />
                <span className="text-sm text-neutral-400">{user.email}</span>
                <button
                  onClick={signOut}
                  className="text-xs text-neutral-600 hover:text-red-400 transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
          <h1 className="text-4xl font-bold tracking-tight mt-4">Digital Due Diligence</h1>
        </header>

        <div className="grid lg:grid-cols-12 gap-8">

          {/* Sidebar */}
          <aside className="lg:col-span-4 space-y-6">
            <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6">
              <h2 className="text-lg font-semibold mb-6 flex items-center gap-2">
                <Search className="text-blue-400" size={18} /> New Investigation
              </h2>
              <form onSubmit={handleAnalyze} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-neutral-500 uppercase ml-1">Company Website</label>
                  <input
                    type="url" required placeholder="https://company.com"
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 outline-none focus:ring-1 focus:ring-blue-500 text-sm"
                    value={url} onChange={(e) => setUrl(e.target.value)}
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-bold text-neutral-500 uppercase ml-1">LinkedIn URL (Optional)</label>
                  <input
                    type="url" placeholder="https://linkedin.com/company/..."
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 outline-none focus:ring-1 focus:ring-blue-500 text-sm"
                    value={linkedin} onChange={(e) => setLinkedin(e.target.value)}
                  />
                </div>

                <button
                  type="submit" disabled={loading}
                  className="w-full bg-blue-600 hover:bg-blue-500 py-4 rounded-xl font-bold transition-all disabled:opacity-50 shadow-lg shadow-blue-500/10"
                >
                  {loading ? "Discovering & Analyzing..." : "Start Investigation"}
                </button>

                <button
                  type="button"
                  onClick={() => window.location.href = '/compare'}
                  className="w-full bg-neutral-950 border border-neutral-800 hover:bg-neutral-800 py-3 rounded-xl font-bold text-neutral-400 hover:text-white transition-all flex items-center justify-center gap-2"
                >
                  <Activity size={16} /> Multi-Vendor Comparison
                </button>

                <button
                  type="button"
                  onClick={() => window.location.href = '/history'}
                  className="w-full bg-neutral-950 border border-neutral-800 hover:bg-neutral-800 py-3 rounded-xl font-bold text-neutral-400 hover:text-white transition-all flex items-center justify-center gap-2"
                >
                  <FileText size={16} /> Investigation History
                </button>
              </form>

              {/* Discovered Links Feedback */}
              {report?.discovered_links && Object.values(report.discovered_links).some(v => v) && (
                <div className="mt-6 pt-6 border-t border-neutral-800">
                  <h3 className="text-[10px] font-bold text-neutral-500 uppercase mb-3 flex items-center gap-1">
                    <Globe size={10} /> Discovered Links
                  </h3>
                  <div className="space-y-2">
                    {Object.entries(report.discovered_links).map(([key, val]) => {
                      if (!val || key === 'website') return null
                      const icons: Record<string, string | null> = {
                        linkedin: '💼', twitter: '🐦', github: '💻',
                        crunchbase: '📊', company_name: null
                      }
                      if (key === 'company_name') return null
                      return (
                        <a
                          key={key}
                          href={val as string}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center justify-between text-[11px] bg-neutral-950 border border-neutral-800 hover:border-blue-500/50 p-2 rounded-lg transition-all group"
                        >
                          <span className="text-neutral-400 capitalize flex items-center gap-1.5">
                            <span>{icons[key] || '🔗'}</span> {key}
                          </span>
                          <span className="text-blue-400 text-[10px] group-hover:text-blue-300 truncate max-w-[110px]">
                            {(val as string).replace('https://', '').replace('http://', '').slice(0, 25)}...
                          </span>
                        </a>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Scraped Sources */}
              {report?.raw_data_summary?.scraped_sources && (
                <div className="mt-4 pt-4 border-t border-neutral-800">
                  <h3 className="text-[10px] font-bold text-neutral-500 uppercase mb-2">Sources Scraped</h3>
                  <div className="flex flex-wrap gap-1">
                    {Array.from(new Set(report.raw_data_summary.scraped_sources as string[])).map((src: string) => (
                      <span key={src} className="text-[10px] px-2 py-0.5 bg-green-500/10 text-green-400 border border-green-500/20 rounded-full">
                        ✓ {src}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Progress Steps */}
              {report?.progress_steps && report.status !== 'complete' && (
                <div className="mt-4 pt-4 border-t border-neutral-800 space-y-1">
                  {(report.progress_steps as string[]).slice(-4).map((step: string, i: number) => (
                    <div key={i} className="text-[10px] text-neutral-500 flex gap-1.5">
                      <span className="text-blue-400 shrink-0">›</span>
                      <span>{step}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {report?.status === "complete" && (
              <div className="space-y-2">
                <button
                  onClick={() => window.open(`${API_URL}/api/export/${report.job_id}`)}
                  className="w-full flex items-center justify-center gap-2 p-4 bg-neutral-900 border border-neutral-800 rounded-xl hover:bg-neutral-800 transition-all"
                >
                  <Download size={18} /> Download PDF Report
                </button>
                <button
                  onClick={speakBriefing}
                  className={`w-full flex items-center justify-center gap-2 p-4 rounded-xl font-semibold transition-all border ${
                    isSpeaking
                      ? "bg-blue-600/20 border-blue-500/40 text-blue-400 hover:bg-blue-600/30"
                      : "bg-neutral-900 border-neutral-800 text-neutral-400 hover:bg-neutral-800 hover:text-white"
                  }`}
                >
                  {isSpeaking ? <VolumeX size={18} /> : <Volume2 size={18} />}
                  {isSpeaking ? "Stop Briefing" : "Voice AI Briefing"}
                </button>
              </div>
            )}
          </aside>

          {/* Main Section */}
          <section className="lg:col-span-8 space-y-6">
            {!jobId && !report && (
              <div className="space-y-6">
                {/* Stats Cards */}
                {statsLoaded && dashStats.length > 0 ? (
                  <>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
                        <BarChart3 className="mx-auto text-blue-500 mb-2" size={24} />
                        <div className="text-3xl font-black text-white">{dashStats.length}</div>
                        <div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1 font-semibold">Investigations</div>
                      </div>
                      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
                        <TrendingUp className="mx-auto text-green-500 mb-2" size={24} />
                        <div className={`text-3xl font-black ${
                          (dashStats.reduce((s, h) => s + h.trust_score, 0) / dashStats.length) >= 55 ? 'text-green-400' : 'text-yellow-400'
                        }`}>
                          {Math.round(dashStats.reduce((s, h) => s + h.trust_score, 0) / dashStats.length)}
                        </div>
                        <div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1 font-semibold">Avg Score</div>
                      </div>
                      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
                        <AlertTriangle className="mx-auto text-red-500 mb-2" size={24} />
                        <div className="text-3xl font-black text-red-400">
                          {dashStats.filter(h => h.risk_level.includes('HIGH')).length}
                        </div>
                        <div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1 font-semibold">High Risk</div>
                      </div>
                      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5 text-center">
                        <CheckCircle className="mx-auto text-emerald-500 mb-2" size={24} />
                        <div className="text-3xl font-black text-emerald-400">
                          {dashStats.filter(h => h.trust_score >= 75).length}
                        </div>
                        <div className="text-[10px] text-neutral-500 uppercase tracking-wider mt-1 font-semibold">Trusted</div>
                      </div>
                    </div>

                    {/* Highest Risk Company */}
                    {(() => {
                      const riskiest = dashStats.reduce((a, b) => a.trust_score < b.trust_score ? a : b);
                      return (
                        <div className="bg-gradient-to-r from-red-950/30 to-neutral-900 border border-red-900/30 rounded-2xl p-5">
                          <div className="flex items-center gap-3 mb-2">
                            <TrendingDown className="text-red-500" size={18} />
                            <span className="text-xs font-bold text-red-400 uppercase tracking-wider">Highest Risk Detected</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <div>
                              <h4 className="text-lg font-bold text-white">{riskiest.company_name}</h4>
                              <span className="text-xs text-neutral-500">{riskiest.red_flags_count} red flags • {riskiest.risk_level.replace(/_/g, ' ')}</span>
                            </div>
                            <div className="text-3xl font-black text-red-400">{riskiest.trust_score}<span className="text-sm text-neutral-600">/100</span></div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Recent Investigations */}
                    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-5">
                      <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-4 flex items-center gap-2">
                        <Clock size={14} /> Recent Investigations
                      </h3>
                      <div className="space-y-2">
                        {dashStats.slice(0, 5).map((h) => (
                          <div
                            key={h.job_id}
                            className="flex items-center justify-between p-3 bg-neutral-950 rounded-xl hover:bg-neutral-800 transition-colors cursor-pointer"
                            onClick={() => {
                              localStorage.setItem('investigate_url', '');
                              localStorage.setItem('investigate_job_id', h.job_id);
                              window.location.reload();
                            }}
                          >
                            <div className="flex items-center gap-3">
                              <div className={`w-2 h-2 rounded-full ${
                                h.trust_score >= 75 ? 'bg-green-500' :
                                h.trust_score >= 55 ? 'bg-yellow-500' :
                                h.trust_score >= 30 ? 'bg-orange-500' : 'bg-red-500'
                              }`} />
                              <span className="font-semibold text-sm text-neutral-200">{h.company_name}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                h.risk_level.includes('HIGH') ? 'bg-red-500/10 text-red-400' :
                                h.risk_level.includes('MEDIUM') ? 'bg-yellow-500/10 text-yellow-400' :
                                'bg-green-500/10 text-green-400'
                              }`}>{h.risk_level.replace(/_/g, ' ')}</span>
                              <span className={`text-sm font-black ${
                                h.trust_score >= 75 ? 'text-green-400' :
                                h.trust_score >= 55 ? 'text-yellow-400' :
                                h.trust_score >= 30 ? 'text-orange-400' : 'text-red-400'
                              }`}>{h.trust_score}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="h-[400px] flex flex-col items-center justify-center border border-dashed border-neutral-800 rounded-3xl bg-neutral-900/20 text-neutral-500 text-center px-10">
                    <Globe size={48} className="mb-4 opacity-10" />
                    <p>Submit a company domain to start the autonomous investigation pipeline.</p>
                  </div>
                )}
              </div>
            )}

            {jobId && (!report || report.status !== "complete") && (
              <LoadingSkeleton steps={report?.steps} />
            )}

            <AnimatePresence>
              {report?.status === "complete" && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">

                  {/* Executive Summary Panel */}
                  <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl mb-6">
                    <div className="flex flex-wrap items-center justify-between mb-4 gap-4">
                      <h3 className="text-white font-bold uppercase flex items-center gap-2">
                        <ShieldAlert size={18} className="text-blue-500" /> Executive Summary
                      </h3>
                      <div className="flex gap-2">
                        {report.tier && (
                          <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            {report.tier === 1 ? 'TIER 1: ENTERPRISE' : report.tier === 2 ? 'TIER 2: ESTABLISHED SME' : 'TIER 3: UNKNOWN'}
                          </span>
                        )}
                        {report.legitimacy_verdict && (
                          <span className={`px-3 py-1 rounded-full text-xs font-bold border ${verdictColors[report.legitimacy_verdict] || verdictColors.UNCERTAIN}`}>
                            {report.legitimacy_verdict.replace(/_/g, " ")}
                          </span>
                        )}
                      </div>
                    </div>
                    {report.ai_reasoning && (
                      <div className="bg-neutral-950 p-5 rounded-xl border border-neutral-800 text-sm text-neutral-300 leading-relaxed relative">
                        <div className="absolute top-0 left-0 w-1 h-full bg-blue-500/50 rounded-l-xl"></div>
                        <span className="font-semibold text-blue-400 mr-2">AI Summary:</span>
                        {report.ai_reasoning}
                      </div>
                    )}
                  </div>

                  {/* Score Breakdown Section */}
                  <ScoreBreakdown
                    score={report.trust_score}
                    riskLevel={report.risk_level}
                    breakdown={report.score_breakdown}
                  />

                  {/* Red Flags */}
                  {(report.red_flags ?? []).length > 0 && (
                    <div className="bg-red-500/5 border border-red-500/20 rounded-2xl p-6">
                      <h3 className="text-red-400 text-xs font-bold uppercase mb-4 flex items-center gap-2">
                        <AlertTriangle size={14} /> Red Flags Detected
                      </h3>
                      <div className="space-y-2">
                        {(report.red_flags ?? []).map((f, i) => (
                          <div key={i} className="text-sm text-red-200/70 flex gap-2">
                            <span className="text-red-500">•</span> {f}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Legitimacy Signals */}
                  {(report.legitimacy_signals ?? []).length > 0 && (
                    <div className="bg-green-500/5 border border-green-500/20 rounded-2xl p-6">
                      <h3 className="text-green-400 text-xs font-bold uppercase mb-4 flex items-center gap-2">
                        <CheckCircle size={14} /> Legitimacy Signals
                      </h3>
                      <div className="space-y-2">
                        {(report.legitimacy_signals ?? []).map((s, i) => (
                          <div key={i} className="text-sm text-green-200/70 flex gap-2">
                            <span className="text-green-500">✓</span> {s}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ContradictionTable Component */}
                  <ContradictionTable contradictions={report.contradictions} redFlags={report.red_flags} />

                  {/* Reviews & Sentiment Panel */}
                  <ReviewsPanel report={report} />

                  {/* Bottom Analysis Section: Graph & Chat */}
                  <div className="grid md:grid-cols-2 gap-6">
                    {/* Knowledge Graph */}
                    <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl h-[500px] flex flex-col">
                      <h3 className="text-sm font-bold text-neutral-500 mb-4 uppercase flex items-center gap-2">
                        < Globe size={16} /> Knowledge Graph
                      </h3>
                      <div className="flex-1 bg-neutral-950 rounded-xl border border-neutral-800 overflow-hidden relative">
                        <GraphView
                          report={report}
                        />
                      </div>
                    </div>

                    {/* Chat Panel */}
                    <ChatPanel
                      jobId={report.job_id}
                      companyName={report.company_name}
                      trustScore={report.trust_score}
                      riskLevel={report.risk_level}
                    />
                  </div>

                </motion.div>
              )}
            </AnimatePresence>
          </section>
        </div>
      </div>
    </main>
  );
}
