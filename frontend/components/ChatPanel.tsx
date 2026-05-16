"use client";
import { useState, useRef, useEffect } from "react";

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
}

const QUICK = [
  "Why is this company risky?",
  "Summarise red flags",
  "Is the address real?",
  "How old is this company?",
  "What do employees say?",
];

export default function ChatPanel({ jobId, companyName, trustScore, riskLevel }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "ai",
      text: `Hello! I am ShadowTrace AI. I've analysed ${companyName || "this company"} and detected a trust score of ${trustScore ?? "N/A"}/100. How can I help you investigate further?`,
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
    setMessages((m) => [...m, { role: "user", text: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, message: userMsg }),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }

      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          role: "ai",
          text: data.answer || data.response || "No response received.",
          confidence: data.confidence,
          citations: data.citations,
          guardrail: data.guardrail_triggered,
          disclaimer: data.disclaimer,
        },
      ]);
    } catch (err: any) {
      setMessages((m) => [
        ...m,
        {
          role: "ai",
          text: `Connection error: ${err.message}. Check that the backend is running on port 8000.`,
          confidence: 0,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  const riskColor = riskLevel === "LOW" ? "#1D9E75" : riskLevel === "HIGH" ? "#E24B4A" : "#EF9F27";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 400 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0.75rem 1rem", borderBottom: "0.5px solid rgba(255,255,255,0.08)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>AI Investigator</span>
          <span style={{ fontSize: 11, background: "rgba(29,158,117,0.15)", color: "#1D9E75", padding: "2px 8px", borderRadius: 10 }}>● Live</span>
        </div>
        {trustScore !== undefined && (
          <span style={{ fontSize: 11, color: riskColor, fontWeight: 500 }}>
            {trustScore}/100 — {riskLevel}
          </span>
        )}
      </div>

      {/* Disclaimer banner */}
      <div style={{ padding: "6px 1rem", background: "rgba(255,255,255,0.03)", borderBottom: "0.5px solid rgba(255,255,255,0.05)", fontSize: 11, color: "#666" }}>
        AI answers based on investigation data only.
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "1rem", display: "flex", flexDirection: "column", gap: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: m.role === "user" ? "flex-end" : "flex-start" }}>
            {m.role === "ai" && (
              <span style={{ fontSize: 10, color: "#555", marginBottom: 4 }}>SHADOWTRACE AI</span>
            )}
            <div style={{
              maxWidth: "85%",
              padding: "0.6rem 0.85rem",
              borderRadius: m.role === "user" ? "12px 12px 2px 12px" : "2px 12px 12px 12px",
              background: m.role === "user" ? "#185FA5" : m.guardrail ? "rgba(226,75,74,0.1)" : "rgba(255,255,255,0.05)",
              border: m.guardrail ? "0.5px solid rgba(226,75,74,0.3)" : "0.5px solid rgba(255,255,255,0.08)",
              fontSize: 13,
              lineHeight: 1.6,
              color: m.role === "user" ? "#fff" : "var(--color-text-primary, #eee)",
            }}>
              {m.guardrail && <span style={{ fontSize: 10, color: "#E24B4A", display: "block", marginBottom: 4 }}>Guardrail triggered</span>}
              {m.text}
            </div>

            {/* Citations */}
            {m.citations && m.citations.length > 0 && (
              <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                {m.citations.map((c, ci) => (
                  <span key={ci} style={{ fontSize: 10, background: "rgba(255,255,255,0.06)", padding: "2px 7px", borderRadius: 8, color: "#888" }}>
                    {c.source}
                  </span>
                ))}
              </div>
            )}

            {/* Confidence bar */}
            {m.role === "ai" && m.confidence !== undefined && m.confidence < 1 && (
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
                <span style={{ fontSize: 10, color: "#555" }}>confidence</span>
                <div style={{ width: 60, height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${Math.round(m.confidence * 100)}%`, background: m.confidence > 0.6 ? "#1D9E75" : "#E24B4A", borderRadius: 2 }} />
                </div>
                <span style={{ fontSize: 10, color: "#555" }}>{Math.round(m.confidence * 100)}%</span>
              </div>
            )}

            {m.disclaimer && (
              <div style={{ fontSize: 10, color: "#555", marginTop: 3 }}>{m.disclaimer}</div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
            <div style={{ padding: "0.6rem 0.85rem", borderRadius: "2px 12px 12px 12px", background: "rgba(255,255,255,0.05)", border: "0.5px solid rgba(255,255,255,0.08)" }}>
              <span style={{ fontSize: 13, color: "#666" }}>Analysing</span>
              <span style={{ animation: "dots 1.2s infinite", fontSize: 13, color: "#666" }}>...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick buttons */}
      <div style={{ padding: "0.5rem 1rem", display: "flex", gap: 6, overflowX: "auto", borderTop: "0.5px solid rgba(255,255,255,0.06)" }}>
        {QUICK.map((q) => (
          <button
            key={q}
            onClick={() => send(q)}
            disabled={loading}
            style={{ flexShrink: 0, fontSize: 11, padding: "4px 10px", borderRadius: 20, border: "0.5px solid rgba(255,255,255,0.12)", background: "transparent", color: "#aaa", cursor: "pointer", whiteSpace: "nowrap" }}
          >
            {q}
          </button>
        ))}
      </div>

      {/* Input */}
      <div style={{ display: "flex", gap: 8, padding: "0.75rem 1rem", borderTop: "0.5px solid rgba(255,255,255,0.08)" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          placeholder="Ask about company claims, risks, or inconsistencies..."
          disabled={loading}
          style={{ flex: 1, fontSize: 13, padding: "8px 12px", borderRadius: 8, border: "0.5px solid rgba(255,255,255,0.12)", background: "rgba(255,255,255,0.04)", color: "inherit", outline: "none" }}
        />
        <button
          onClick={() => send(input)}
          disabled={loading || !input.trim()}
          style={{ padding: "8px 16px", borderRadius: 8, border: "none", background: loading || !input.trim() ? "rgba(255,255,255,0.06)" : "#185FA5", color: "#fff", cursor: loading || !input.trim() ? "not-allowed" : "pointer", fontSize: 13, fontWeight: 500 }}
        >
          Send
        </button>
      </div>

      <style>{`@keyframes dots{0%,100%{opacity:0}50%{opacity:1}}`}</style>
    </div>
  );
}