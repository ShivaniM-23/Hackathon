"use client"
import { useUser } from "../hooks/useUser"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { ShieldAlert } from "lucide-react"

export default function LoginPage() {
  const { user, loading, signIn } = useUser()
  const router = useRouter()

  useEffect(() => {
    if (!loading && user) router.push("/")
  }, [user, loading, router])

  return (
    <main className="min-h-screen bg-neutral-950 flex items-center justify-center p-4">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl p-10 w-full max-w-sm text-center">
        <div className="flex items-center justify-center gap-2 mb-8">
          <ShieldAlert className="text-blue-400" size={32} />
          <span className="text-2xl font-bold text-white">ShadowTrace AI</span>
        </div>
        <h1 className="text-xl font-bold text-white mb-2">Welcome back</h1>
        <p className="text-neutral-500 text-sm mb-8">
          Sign in to investigate companies and detect fraud
        </p>
        <button
          onClick={signIn}
          className="w-full flex items-center justify-center gap-3 bg-white text-gray-800 font-semibold py-3.5 px-6 rounded-xl hover:bg-gray-100 transition-all"
        >
          <svg width="20" height="20" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Continue with Google
        </button>
        <div className="mt-6 space-y-2 text-left">
          {["AI fraud detection","10+ sources scraped","Trust score in 60s","PDF export"].map(f => (
            <div key={f} className="flex items-center gap-2 text-xs text-neutral-500">
              <span className="text-blue-400">✓</span> {f}
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}
