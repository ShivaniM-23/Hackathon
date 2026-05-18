"use client"
import { useSyncExternalStore, useState, useEffect } from "react"

interface User {
  name: string
  email: string
  image: string
}

let cachedCookie = ""
let cachedUser: User | null = null

function subscribe() {
  return () => {}
}

function readUserCookie(): User | null {
  try {
    const userCookie = document.cookie
      .split(";")
      .find(c => c.trim().startsWith("user="))
      ?.trim() ?? ""

    if (userCookie === cachedCookie) return cachedUser

    cachedCookie = userCookie
    if (!userCookie) {
      cachedUser = null
      return cachedUser
    }

    const val = decodeURIComponent(userCookie.split("=")[1])
    cachedUser = JSON.parse(val)
    return cachedUser
  } catch {
    cachedUser = null
    return null
  }
}

export function useUser() {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const user = useSyncExternalStore(subscribe, readUserCookie, () => null)
  const loading = !mounted

  const signIn = () => {
    window.location.href = "/api/google-auth?action=login"
  }

  const signOut = () => {
    window.location.href = "/api/google-auth?action=logout"
  }

  return { user, loading, signIn, signOut }
}
