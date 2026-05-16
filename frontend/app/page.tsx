"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Search, ShieldAlert, CheckCircle, AlertTriangle, XCircle, ArrowRight, MessageSquare, Send } from "lucide-react";
import { ReactFlow, Controls, Background } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

export default function Home() {
  const [url, setUrl] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [gst, setGst] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  
  // Chat state
  const [chatMessage, setChatMessage] = useState("");
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);

    try {
      const response = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url, linkedin_url: linkedin, gst_number: gst }),
      });
      
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("Analysis failed:", error);
      alert("Failed to connect to the backend. Is it running?");
    } finally {
      setLoading(false);
    }
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatMessage.trim()) return;
    
    const newUserMsg = chatMessage;
    setChatHistory(prev => [...prev, { role: "user", content: newUserMsg }]);
    setChatMessage("");
    setChatLoading(true);
    
    try {
      const response = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: newUserMsg, context: result?.extracted_data || {} }),
      });
      const data = await response.json();
      setChatHistory(prev => [...prev, { role: "assistant", content: data.reply }]);
    } catch (error) {
      console.error("Chat error:", error);
      setChatHistory(prev => [...prev, { role: "assistant", content: "Error connecting to AI assistant." }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-neutral-950 text-neutral-100 font-sans selection:bg-blue-500/30">
      <div className="max-w-6xl mx-auto px-6 py-12">
        
        {/* Header */}
        <header className="mb-16 text-center">
          <motion.div 
            initial={{ opacity: 0, y: -20 }} 
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-sm font-medium mb-6"
          >
            <ShieldAlert size={16} />
            ShadowTrace AI
          </motion.div>
          <motion.h1 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="text-4xl md:text-6xl font-bold tracking-tight mb-4"
          >
            Detect Scams <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">Before You Do</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-neutral-400 max-w-2xl mx-auto text-lg"
          >
            Enter a company's details. Our SLM-powered engine scrapes the web, extracts entities, and builds a truth-verified trust score in seconds.
          </motion.p>
        </header>

        <div className="grid md:grid-cols-12 gap-8 items-start">
          
          {/* Intake Form */}
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="md:col-span-4 bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl"
          >
            <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
              <Search className="text-neutral-400" size={20} />
              New Investigation
            </h2>
            <form onSubmit={handleAnalyze} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Company URL</label>
                <input 
                  type="url" 
                  required
                  placeholder="https://example.com"
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-neutral-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">LinkedIn URL (Optional)</label>
                <input 
                  type="url" 
                  placeholder="https://linkedin.com/company/..."
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-neutral-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  value={linkedin}
                  onChange={(e) => setLinkedin(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">GST / Reg Number (Optional)</label>
                <input 
                  type="text" 
                  placeholder="e.g. 29GGGGG1314R9Z6"
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2.5 text-neutral-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  value={gst}
                  onChange={(e) => setGst(e.target.value)}
                />
              </div>
              
              <button 
                type="submit" 
                disabled={loading}
                className="w-full mt-4 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-3 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full" />
                    Analyzing...
                  </span>
                ) : (
                  <>
                    Run Analysis <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>
          </motion.div>

          {/* Results Dashboard */}
          <div className="md:col-span-8 space-y-6">
            {!result && !loading && (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center border border-dashed border-neutral-800 rounded-2xl bg-neutral-900/50 text-neutral-500">
                <ShieldAlert size={48} className="mb-4 opacity-20" />
                <p>Submit a company to generate a trust score.</p>
              </div>
            )}

            {loading && (
              <div className="h-full min-h-[400px] flex flex-col items-center justify-center border border-neutral-800 rounded-2xl bg-neutral-900/50">
                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 2, ease: "linear" }} className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full mb-6" />
                <p className="text-neutral-400 animate-pulse">Webscraping & analyzing data via SLM...</p>
              </div>
            )}

            {result && (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                {/* Score Card */}
                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-8 flex items-center justify-between shadow-xl overflow-hidden relative">
                  <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl -mr-20 -mt-20"></div>
                  
                  <div>
                    <h3 className="text-neutral-400 font-medium mb-1">Trust Score</h3>
                    <div className="flex items-end gap-4">
                      <span className={`text-6xl font-bold ${
                        result.trust_score > 80 ? 'text-emerald-400' : 
                        result.trust_score > 50 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {result.trust_score}
                      </span>
                      <span className="text-xl text-neutral-500 pb-1">/ 100</span>
                    </div>
                  </div>

                  <div className="text-right">
                    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full font-bold ${
                      result.risk_level === 'LOW RISK' ? 'bg-emerald-500/10 text-emerald-400' : 
                      result.risk_level === 'MEDIUM RISK' ? 'bg-yellow-500/10 text-yellow-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                      {result.risk_level === 'LOW RISK' && <CheckCircle size={20} />}
                      {result.risk_level === 'MEDIUM RISK' && <AlertTriangle size={20} />}
                      {result.risk_level === 'HIGH RISK' && <XCircle size={20} />}
                      {result.risk_level}
                    </div>
                  </div>
                </div>

                {/* Contradiction Table */}
                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl">
                  <h3 className="text-lg font-semibold mb-4 border-b border-neutral-800 pb-4">Digital Footprint Consistency</h3>
                  
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="text-neutral-500 text-sm">
                          <th className="pb-3 font-medium">Claimed Value</th>
                          <th className="pb-3 font-medium">Actual Web Evidence</th>
                          <th className="pb-3 font-medium text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="text-sm">
                        {result.contradictions.map((item: any, i: number) => (
                          <tr key={i} className="border-t border-neutral-800/50">
                            <td className="py-4 text-neutral-300">{item.claim}</td>
                            <td className="py-4 text-neutral-400">{item.evidence}</td>
                            <td className="py-4 text-right">
                              <span className={`inline-flex px-2 py-1 rounded text-xs font-medium ${
                                item.status === 'GREEN' ? 'bg-emerald-500/10 text-emerald-400' :
                                item.status === 'AMBER' ? 'bg-yellow-500/10 text-yellow-400' :
                                'bg-red-500/10 text-red-400'
                              }`}>
                                {item.match ? 'MATCH' : 'MISMATCH'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Raw SLM Data */}
                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl">
                  <h3 className="text-lg font-semibold mb-4">Extracted Entities (SLM)</h3>
                  <pre className="bg-neutral-950 p-4 rounded-lg text-xs text-neutral-400 overflow-x-auto border border-neutral-800">
                    {JSON.stringify(result.extracted_data, null, 2)}
                  </pre>
                </div>

                {/* Phase 2: Graph Visualization */}
                {result.extracted_data?.graph && (
                  <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl h-[400px] flex flex-col">
                    <h3 className="text-lg font-semibold mb-4 border-b border-neutral-800 pb-4">Knowledge Graph</h3>
                    <div className="flex-1 bg-neutral-950 rounded-lg border border-neutral-800 overflow-hidden">
                      <ReactFlow 
                        nodes={result.extracted_data.graph.nodes || []} 
                        edges={result.extracted_data.graph.edges || []}
                        fitView
                        colorMode="dark"
                      >
                        <Background color="#334155" gap={16} />
                        <Controls />
                      </ReactFlow>
                    </div>
                  </div>
                )}

                {/* Phase 2: Conversational AI */}
                <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-6 shadow-xl flex flex-col h-[500px]">
                  <h3 className="text-lg font-semibold mb-4 border-b border-neutral-800 pb-4 flex items-center gap-2">
                    <MessageSquare size={20} className="text-blue-400" />
                    AI Investigator Chat
                  </h3>
                  
                  <div className="flex-1 overflow-y-auto space-y-4 mb-4 pr-2">
                    {chatHistory.length === 0 ? (
                      <div className="text-center text-neutral-500 mt-10">
                        Ask me anything about the company's digital footprint and risk factors.
                      </div>
                    ) : (
                      chatHistory.map((msg, i) => (
                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                            msg.role === 'user' 
                              ? 'bg-blue-600 text-white rounded-tr-sm' 
                              : 'bg-neutral-800 text-neutral-200 border border-neutral-700 rounded-tl-sm'
                          }`}>
                            {msg.content}
                          </div>
                        </div>
                      ))
                    )}
                    {chatLoading && (
                      <div className="flex justify-start">
                        <div className="bg-neutral-800 border border-neutral-700 text-neutral-400 rounded-2xl rounded-tl-sm px-4 py-3 text-sm flex gap-1">
                          <span className="animate-bounce">.</span>
                          <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>.</span>
                          <span className="animate-bounce" style={{ animationDelay: "0.4s" }}>.</span>
                        </div>
                      </div>
                    )}
                  </div>

                  <form onSubmit={handleChat} className="flex gap-2 relative">
                    <input 
                      type="text" 
                      value={chatMessage}
                      onChange={(e) => setChatMessage(e.target.value)}
                      placeholder="Ask about the risk factors..."
                      className="flex-1 bg-neutral-950 border border-neutral-800 rounded-xl px-4 py-3 text-neutral-100 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                      disabled={chatLoading}
                    />
                    <button 
                      type="submit" 
                      disabled={chatLoading || !chatMessage.trim()}
                      className="bg-blue-600 hover:bg-blue-500 text-white rounded-xl px-4 py-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Send size={18} />
                    </button>
                  </form>
                </div>

              </motion.div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
