import type { NextConfig } from 'next'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/investigate',
        destination: `${API_URL}/api/investigate`,
      },
      {
        source: '/api/report/:path*',
        destination: `${API_URL}/api/report/:path*`,
      },
      {
        source: '/api/chat',
        destination: `${API_URL}/api/chat`,
      },
      {
        source: '/api/export/:path*',
        destination: `${API_URL}/api/export/:path*`,
      },
      {
        source: '/api/status/:path*',
        destination: `${API_URL}/api/status/:path*`,
      },
      {
        source: '/api/history',
        destination: `${API_URL}/api/history`,
      },
    ]
  },
}

export default nextConfig
