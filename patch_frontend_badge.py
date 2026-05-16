import sys

with open("frontend/app/page.tsx", "r", encoding="utf-8") as f:
    page_content = f.read()

# Add the verdict property to the Report type
page_content = page_content.replace(
    '  red_flags: string[];',
    '  red_flags: string[];\n  legitimacy_signals?: string[];\n  legitimacy_verdict?: string;\n  ai_reasoning?: string;'
)

# Insert verdict colors logic before returning the TSX (before `return (\n    <main`)
verdict_colors = """
  const verdictColors: Record<string, string> = {
    LEGITIMATE: "bg-green-500/20 text-green-400 border-green-500/30",
    LIKELY_LEGITIMATE: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    UNCERTAIN: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    LIKELY_FRAUDULENT: "bg-orange-500/20 text-orange-400 border-orange-500/30",
    FRAUDULENT: "bg-red-500/20 text-red-400 border-red-500/30",
  };
"""

page_content = page_content.replace(
    '  return (\n    <main',
    verdict_colors + '\n  return (\n    <main'
)

# Find where to put the badge. Near ScoreBreakdown.
# I'll just put it above the ScoreBreakdown component.
badge_ui = """                  {/* Verdict Badge */}
                  {report.legitimacy_verdict && (
                    <div className="flex items-center gap-3 mb-4">
                      <span className="text-sm text-neutral-400 font-semibold uppercase">AI Verdict:</span>
                      <span className={`px-4 py-1.5 rounded-full text-xs font-bold border ${verdictColors[report.legitimacy_verdict] || verdictColors.UNCERTAIN}`}>
                        {report.legitimacy_verdict.replace(/_/g, " ")}
                      </span>
                    </div>
                  )}

                  {/* Score Breakdown Section */}"""

page_content = page_content.replace(
    '{/* Score Breakdown Section */}',
    badge_ui
)

with open("frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(page_content)
