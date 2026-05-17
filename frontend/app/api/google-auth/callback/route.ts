import { NextRequest, NextResponse } from "next/server"

const GOOGLE_CLIENT_ID = process.env.GOOGLE_CLIENT_ID!
const GOOGLE_CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET!
const REDIRECT_URI = "http://localhost:3000/api/google-auth/callback"

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const code = searchParams.get("code")

  if (!code) {
    return NextResponse.redirect("http://localhost:3000/login?error=no_code")
  }

  try {
    // Exchange code for tokens
    const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        code,
        client_id: GOOGLE_CLIENT_ID,
        client_secret: GOOGLE_CLIENT_SECRET,
        redirect_uri: REDIRECT_URI,
        grant_type: "authorization_code",
      }),
    })
    const tokens = await tokenRes.json()

    // Get user info
    const userRes = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    })
    const user = await userRes.json()

    // Store user in cookie
    const res = NextResponse.redirect("http://localhost:3000")
    res.cookies.set("user", JSON.stringify({
      name: user.name,
      email: user.email,
      image: user.picture,
    }), {
      httpOnly: false,
      maxAge: 60 * 60 * 24 * 7, // 7 days
      path: "/",
    })
    return res

  } catch (error) {
    return NextResponse.redirect("http://localhost:3000/login?error=auth_failed")
  }
}
