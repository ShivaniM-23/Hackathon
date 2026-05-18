import { NextRequest, NextResponse } from "next/server"

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID!
const REDIRECT_URI = "http://localhost:3000/api/google-auth/callback"

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const action = searchParams.get("action")

  if (action === "login") {
    const googleAuthUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth")
    googleAuthUrl.searchParams.set("client_id", GOOGLE_CLIENT_ID)
    googleAuthUrl.searchParams.set("redirect_uri", REDIRECT_URI)
    googleAuthUrl.searchParams.set("response_type", "code")
    googleAuthUrl.searchParams.set("scope", "openid email profile")
    googleAuthUrl.searchParams.set("access_type", "offline")
    return NextResponse.redirect(googleAuthUrl.toString())
  }

  if (action === "logout") {
    const res = NextResponse.redirect("http://localhost:3000/login")
    res.cookies.delete("user")
    return res
  }

  return NextResponse.json({ error: "Invalid action" }, { status: 400 })
}
