import sys

with open("frontend/app/page.tsx", "r", encoding="utf-8") as f:
    content = f.read()

before = content.split("{/* Sidebar */}")[0]
after = "              {/* Discovered Links Feedback */}" + content.split("{/* Discovered Links Feedback */}")[1]

form_content = """          {/* Sidebar */}
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

"""

new_content = before + form_content + after

with open("frontend/app/page.tsx", "w", encoding="utf-8") as f:
    f.write(new_content)
