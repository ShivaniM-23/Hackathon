"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import {
  ShieldAlert, GitCompare, Plus, Trash2, ArrowLeft,
  Activity, CheckCircle, AlertTriangle
} from "lucide-react";

export default function ComparePage() {
  const [urls, setUrls] = useState<string[]>(["", ""]);
  const [isComparing, setIsComparing] = useState(false);
  const [jobIds, setJobIds] = useState<string[]>([]);
  const [reports, setReports] = useState<any[]>([]);

  const addUrl = () => {
    if (urls.length < 3) setUrls([...urls, ""]);
  };

  const removeUrl = (index: number) => {
    setUrls(urls.filter((_, i) => i !== index));
  };

  const updateUrl = (index: number, value: string) => {
    const newUrls = [...urls];
    newUrls[index] = value;
    setUrls(newUrls);
  };

  const startComparison = async () => {
    const validUrls = urls.filter(u => u.trim() !== "");
    if (validUrls.length < 2) {
      alert("Please enter at least 2 vendor URLs to compare.");
      return;
    }

    setIsComparing(true);
    setReports([]);

    // Kick off all investigations concurrently
    const ids = [];
    for (const url of validUrls) {
      try {
        const res = await fetch("http://localhost:8000/api/investigate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, force_new: false })
        });
        const data = await res.json();
        ids.push(data.job_id);
      } catch (e) {
        console.error("Failed to start job for", url, e);
      }
    }
    setJobIds(ids);
  };

  // Poll for job status
  useEffect(() => {
    if (jobIds.length === 0) return;

    const interval = setInterval(async () => {
      const newReports = [];
      let allComplete = true;

      for (const id of jobIds) {
        try {
          const res = await fetch(`http://localhost:8000/api/report/${id}`);
          if (res.status === 404) {
            // Still initializing
            allComplete = false;
            continue;
          }
          const data = await res.json();
          newReports.push(data);
          if (data.status !== "complete" && data.status !== "error") {
            allComplete = false;
          }
        } catch (e) {
          allComplete = false;
        }
      }

      setReports(newReports);

      if (allComplete) {
        clearInterval(interval);
        setIsComparing(false);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [jobIds]);

  // Transform breakdown data for Radar Chart
  const buildRadarData = () => {
    if (reports.length < 2 || reports.some(r => r.status !== "complete")) return [];

    // Assuming all reports have similar keys in score_breakdown
    const categories = Object.keys(reports[0].score_breakdown || {}).map(k => k.replace(/_/g, " ").toUpperCase());

    return categories.map(cat => {
      const dataPoint: any = { category: cat };
      reports.forEach((report, index) => {
        const key = Object.keys(report.score_breakdown).find(k => k.replace(/_/g, " ").toUpperCase() === cat);
        dataPoint[`Vendor ${index + 1} (${report.company_name})`] = key ? report.score_breakdown[key].pct : 0;
      });
      return dataPoint;
    });
  };

  const radarData = buildRadarData();
  const colors = ["#3b82f6", "#ef4444", "#10b981"]; // Blue, Red, Green

  return (
    <div className="min-h-screen bg-black text-white p-6 md:p-12 font-sans selection:bg-blue-500/30">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => window.location.href = "/"} className="p-2 bg-neutral-900 border border-neutral-800 rounded-lg hover:bg-neutral-800 text-neutral-400">
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-3xl font-black tracking-tight flex items-center gap-3">
                <GitCompare className="text-blue-500" /> Multi-Vendor Comparison
              </h1>
              <p className="text-neutral-400 mt-1">Procurement Due Diligence Simulator</p>
            </div>
          </div>
        </div>

        {/* Input Section */}
        <div className="bg-neutral-900 border border-neutral-800 p-6 rounded-2xl shadow-2xl">
          <h3 className="text-sm font-bold text-neutral-400 mb-4 uppercase">Enter Vendor URLs</h3>
          <div className="flex flex-col md:flex-row gap-4 mb-4">
            {urls.map((url, i) => (
              <div key={i} className="flex-1 relative group">
                <input
                  type="text"
                  placeholder={`https://vendor${i + 1}.com`}
                  value={url}
                  onChange={(e) => updateUrl(i, e.target.value)}
                  disabled={isComparing || jobIds.length > 0}
                  className="w-full bg-black border border-neutral-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-blue-500 transition-all disabled:opacity-50"
                />
                {i >= 2 && !isComparing && jobIds.length === 0 && (
                  <button onClick={() => removeUrl(i)} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-500 hover:text-red-500">
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            ))}
            {urls.length < 3 && !isComparing && jobIds.length === 0 && (
              <button
                onClick={addUrl}
                className="flex items-center justify-center gap-2 px-6 bg-neutral-800 border border-neutral-700 rounded-xl hover:bg-neutral-700 transition-all"
              >
                <Plus size={18} /> Add
              </button>
            )}
          </div>

          {jobIds.length === 0 && (
            <button
              onClick={startComparison}
              disabled={urls.filter(u => u.trim() !== "").length < 2}
              className="w-full py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-bold transition-all disabled:opacity-50 disabled:hover:bg-blue-600 flex items-center justify-center gap-2"
            >
              <GitCompare size={20} /> Compare Vendors
            </button>
          )}
        </div>

        {/* Loading State */}
        {isComparing && (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {reports.map((report, i) => (
              <div key={i} className="bg-neutral-900 border border-neutral-800 p-6 rounded-2xl animate-pulse">
                <div className="flex items-center gap-3 mb-4">
                  <Activity className="text-blue-500 animate-spin" size={24} />
                  <span className="font-bold text-neutral-300">Investigating Vendor {i + 1}...</span>
                </div>
                <div className="space-y-2">
                  {(report?.progress_steps || []).slice(-3).map((step: string, j: number) => (
                    <p key={j} className="text-xs text-neutral-500">{step}</p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Results Comparison */}
        {!isComparing && reports.length > 0 && reports.every(r => r.status === "complete") && (
          <AnimatePresence>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-8">

              {/* Radar Chart Panel */}
              <div className="bg-neutral-900 border border-neutral-800 rounded-3xl p-8 flex flex-col md:flex-row items-center gap-8 shadow-2xl">
                <div className="flex-1 w-full h-[400px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                      <PolarGrid stroke="#333" />
                      <PolarAngleAxis dataKey="category" tick={{ fill: '#888', fontSize: 10 }} />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fill: '#555' }} />
                      <Tooltip contentStyle={{ backgroundColor: '#111', borderColor: '#333' }} />
                      <Legend wrapperStyle={{ paddingTop: '20px' }} />
                      {reports.map((r, i) => (
                        <Radar
                          key={i}
                          name={`Vendor ${i + 1} (${r.company_name})`}
                          dataKey={`Vendor ${i + 1} (${r.company_name})`}
                          stroke={colors[i]}
                          fill={colors[i]}
                          fillOpacity={0.3}
                        />
                      ))}
                    </RadarChart>
                  </ResponsiveContainer>
                </div>

                <div className="flex-1 space-y-6">
                  <h3 className="text-2xl font-black flex items-center gap-2">
                    <ShieldAlert className="text-blue-500" /> Comparison Verdict
                  </h3>
                  <div className="space-y-4">
                    {reports.map((r, i) => (
                      <div key={i} className="bg-black border border-neutral-800 p-4 rounded-xl flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: colors[i] }}></div>
                            <span className="font-bold text-lg">{r.company_name}</span>
                          </div>
                          <span className="text-xs text-neutral-500 uppercase tracking-widest font-bold">
                            Tier {r.tier} Entity
                          </span>
                        </div>
                        <div className="text-right">
                          <div className={`text-2xl font-black ${r.trust_score >= 75 ? 'text-green-500' :
                              r.trust_score >= 55 ? 'text-yellow-500' : 'text-red-500'
                            }`}>
                            {r.trust_score}/100
                          </div>
                          <span className="text-xs font-bold px-2 py-1 bg-neutral-900 border border-neutral-800 rounded mt-1 inline-block">
                            {r.legitimacy_verdict.replace(/_/g, " ")}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Side-by-side Red Flags & Signals */}
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {reports.map((r, i) => (
                  <div key={i} className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 flex flex-col h-full">
                    <h4 className="font-bold text-xl mb-6 flex items-center gap-2 border-b border-neutral-800 pb-4" style={{ color: colors[i] }}>
                      Vendor {i + 1}: {r.company_name}
                    </h4>

                    <div className="flex-1 space-y-6">
                      {/* AI Reasoning */}
                      <div className="bg-black p-4 rounded-xl border border-neutral-800 text-sm text-neutral-300 leading-relaxed relative">
                        <div className="absolute top-0 left-0 w-1 h-full bg-blue-500/50 rounded-l-xl"></div>
                        <span className="font-semibold text-blue-400 mr-2">AI Summary:</span>
                        {r.ai_reasoning}
                      </div>

                      {/* Red Flags */}
                      <div>
                        <h5 className="text-xs font-bold text-red-500 uppercase mb-3 flex items-center gap-2">
                          <AlertTriangle size={14} /> Red Flags
                        </h5>
                        <ul className="space-y-2">
                          {r.red_flags.length === 0 ? (
                            <li className="text-xs text-neutral-600">No red flags detected.</li>
                          ) : (
                            r.red_flags.slice(0, 3).map((flag: string, idx: number) => (
                              <li key={idx} className="text-xs text-red-400 flex gap-2">
                                <span>•</span> <span>{flag}</span>
                              </li>
                            ))
                          )}
                        </ul>
                      </div>

                      {/* Legitimacy Signals */}
                      <div>
                        <h5 className="text-xs font-bold text-green-500 uppercase mb-3 flex items-center gap-2">
                          <CheckCircle size={14} /> Legitimacy Signals
                        </h5>
                        <ul className="space-y-2">
                          {r.legitimacy_signals.slice(0, 3).map((sig: string, idx: number) => (
                            <li key={idx} className="text-xs text-green-400 flex gap-2">
                              <span>✓</span> <span>{sig}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    <button
                      onClick={() => window.open(`http://localhost:8000/api/export/${r.job_id}`)}
                      className="mt-6 w-full py-3 bg-neutral-800 hover:bg-neutral-700 text-sm font-bold rounded-xl transition-colors"
                    >
                      Download Full Report
                    </button>
                  </div>
                ))}
              </div>

            </motion.div>
          </AnimatePresence>
        )}

      </div>
    </div>
  );
}
