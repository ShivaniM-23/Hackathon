"use client";

import { useState, useEffect, useRef } from "react";
import { useUser } from "./hooks/useUser";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, ShieldAlert, CheckCircle, AlertTriangle, 
  XCircle, ArrowRight, MessageSquare, Send, 
  FileText, Activity, Globe, Info, Download
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
  steps?: {step: string, detail: string, pct: number}[];
}

const LoadingSkeleton = ({ steps }: { steps?: {step: string, detail: string, pct: number}[] }) => (
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
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

  // --- Polling Logic (Fix for Bug 2 & Persistence Support) ---
  const failCount = useRef(0);

  useEffect(() => {
    if (!user && !authLoading) router.push("/login");
  }, [user, authLoading, router]);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/report/${jobId}`);
        
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
      const startRes = await fetch("http://localhost:8000/api/investigate", {
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
      const response = await fetch("http://localhost:8000/api/chat", {
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
              <button 
                onClick={() => window.open(`http://localhost:8000/api/export/${report.job_id}`)}
                className="w-full flex items-center justify-center gap-2 p-4 bg-neutral-900 border border-neutral-800 rounded-xl hover:bg-neutral-800 transition-all"
              >
                <Download size={18} /> Download PDF Report
              </button>
            )}
          </aside>

          {/* Main Section */}
          <section className="lg:col-span-8 space-y-6">
            {!jobId && !report && (
              <div className="h-[400px] flex flex-col items-center justify-center border border-dashed border-neutral-800 rounded-3xl bg-neutral-900/20 text-neutral-500 text-center px-10">
                <Globe size={48} className="mb-4 opacity-10" />
                <p>Submit a company domain to start the autonomous investigation pipeline.</p>
              </div>
            )}

            {jobId && (!report || report.status !== "complete") && (
              <LoadingSkeleton steps={report?.steps} />
            )}

            <AnimatePresence>
              {report?.status === "complete" && (
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
                  
                                    {/* Verdict Badge */}
                  {report.legitimacy_verdict && (
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-sm text-neutral-400 font-semibold uppercase">AI Verdict:</span>
                      <span className={`px-4 py-1.5 rounded-full text-xs font-bold border ${verdictColors[report.legitimacy_verdict] || verdictColors.UNCERTAIN}`}>
                        {report.legitimacy_verdict.replace(/_/g, " ")}
                      </span>
                    </div>
                  )}

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
