"use client";

import { useEffect, useRef, useState } from "react";
import { Bot, CornerDownLeft, MessageSquareText, Send, ShieldCheck } from "lucide-react";

interface Message {
  role: "user" | "ai";
  text: string;
  confidence?: number;
  citations?: { source: string }[];
  guardrail?: boolean;
  disclaimer?: string;
}

interface Props {
  jobId: string;
  companyName?: string;
  trustScore?: number;
  riskLevel?: string;
  apiUrl?: string;
}

const QUICK = [
  "What is the biggest risk?",
  "Summarise red flags",
  "Explain the score",
  "What evidence is strongest?",
];

function riskTone(riskLevel?: string) {
  if (riskLevel?.includes("LOW")) return "border-emerald-400/20 bg-emerald-400/10 text-emerald-200";
  if (riskLevel?.includes("HIGH")) return "border-red-400/20 bg-red-400/10 text-red-200";
  return "border-amber-400/20 bg-amber-400/10 text-amber-200";
}

export default function ChatPanel({ jobId, companyName, trustScore, riskLevel, apiUrl = "" }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "ai",
      text: `I have the ${companyName || "company"} report ready. Ask about risk, score, contradictions, reviews, or sources.`,
      confidence: 1,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || loading) return;

    const userMsg = text.trim();
    setInput("");
    setMessages((current) => [...current, { role: "user", text: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, message: userMsg }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);

      const data = await res.json();
      setMessages((current) => [
        ...current,
        {
          role: "ai",
          text: data.answer || data.response || "No response received.",
          confidence: data.confidence,
          citations: data.citations,
          guardrail: data.guardrail_triggered,
          disclaimer: data.disclaimer,
        },
      ]);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setMessages((current) => [
        ...current,
        {
          role: "ai",
          text: `Connection error: ${message}. Check that the backend is running on port 8000.`,
          confidence: 0,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b border-slate-800 bg-slate-950/60 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-cyan-400 text-slate-950 shadow-lg shadow-cyan-500/20">
              <Bot size={21} />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">AI Investigator</h2>
              <p className="text-xs text-slate-500">Grounded in this report</p>
            </div>
          </div>
          {trustScore !== undefined && (
            <div className={`rounded-lg border px-3 py-2 text-right ${riskTone(riskLevel)}`}>
              <p className="text-[10px] font-bold uppercase">Score</p>
              <p className="text-sm font-semibold">{trustScore}/100</p>
            </div>
          )}
        </div>
      </header>

      <div className="border-b border-slate-800 px-4 py-3">
        <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-400">
          <ShieldCheck size={14} className="shrink-0 text-cyan-300" />
          Answers use only the completed investigation dossier.
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((message, index) => (
          <div key={index} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[90%] ${message.role === "user" ? "text-right" : "text-left"}`}>
              {message.role === "ai" && (
                <div className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-500">
                  <MessageSquareText size={11} />
                  ShadowTrace
                </div>
              )}
              <div
                className={`rounded-lg border px-3 py-2 text-sm leading-6 ${
                  message.role === "user"
                    ? "border-cyan-400/20 bg-cyan-400 text-slate-950"
                    : message.guardrail
                      ? "border-red-400/25 bg-red-400/10 text-red-100"
                      : "border-slate-800 bg-slate-950 text-slate-200"
                }`}
              >
                {message.text}
              </div>

              {message.citations && message.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {message.citations.map((citation, citationIndex) => (
                    <span key={citationIndex} className="rounded-md border border-slate-800 bg-slate-950 px-2 py-1 text-[10px] text-slate-500">
                      {citation.source}
                    </span>
                  ))}
                </div>
              )}

              {message.role === "ai" && message.confidence !== undefined && message.confidence < 1 && (
                <div className="mt-2 flex items-center gap-2 text-[10px] text-slate-500">
                  <span>confidence</span>
                  <div className="h-1 w-16 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className={`h-full rounded-full ${message.confidence > 0.6 ? "bg-emerald-400" : "bg-red-400"}`}
                      style={{ width: `${Math.round(message.confidence * 100)}%` }}
                    />
                  </div>
                  <span>{Math.round(message.confidence * 100)}%</span>
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-sm text-slate-400">
              Analysing...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-800 p-3">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
          {QUICK.map((question) => (
            <button
              key={question}
              onClick={() => send(question)}
              disabled={loading}
              className="shrink-0 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-400 transition hover:border-cyan-400/40 hover:text-cyan-200 disabled:opacity-50"
            >
              {question}
            </button>
          ))}
        </div>

        <div className="flex gap-2">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && send(input)}
            placeholder="Ask a follow-up..."
            disabled={loading}
            className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-cyan-300"
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-cyan-400 text-slate-950 transition hover:bg-cyan-300 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
            aria-label="Send message"
            title="Send"
          >
            {input.trim() ? <Send size={17} /> : <CornerDownLeft size={17} />}
          </button>
        </div>
      </div>
    </div>
  );
}
