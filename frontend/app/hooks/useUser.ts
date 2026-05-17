"use client"
import { useState, useEffect } from "react"

interface User {
  name: string
  email: string
  image: string
}

export function useUser() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    try {
      const cookies = document.cookie.split(";")
      const userCookie = cookies.find(c => c.trim().startsWith("user="))
      if (userCookie) {
        const val = decodeURIComponent(userCookie.split("=")[1])
        setUser(JSON.parse(val))
      }
    } catch (e) {}
    setLoading(false)
  }, [])

  const signIn = () => {
    window.location.href = "/api/google-auth?action=login"
  }

  const signOut = () => {
    window.location.href = "/api/google-auth?action=logout"
  }

  return { user, loading, signIn, signOut }
}
