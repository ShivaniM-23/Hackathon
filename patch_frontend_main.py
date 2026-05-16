import sys
import re

# PATCH MAIN.PY
with open("backend/main.py", "r", encoding="utf-8") as f:
    main_content = f.read()

main_content = main_content.replace(
    '"red_flags": score_result.get("red_flags", []),',
    '"red_flags": score_result.get("red_flags", []),\n            "legitimacy_signals": score_result.get("legitimacy_signals", []),\n            "legitimacy_verdict": score_result.get("legitimacy_verdict", "UNCERTAIN"),\n            "ai_reasoning": dossier.get("ai_reasoning", ""),')

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(main_content)

# PATCH PAGE.TSX
with open("frontend/app/page.tsx", "r", encoding="utf-8") as f:
    page_content = f.read()

# Add legitimacy signals next to red flags
legit_ui = """                  {/* Legitimacy Signals */}
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
                  )}"""

page_content = page_content.replace(
    '{/* ContradictionTable Component */}',
    f'{legit_ui}\n\n                  {{/* ContradictionTable Component */}}'
)

with open("frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(page_content)
