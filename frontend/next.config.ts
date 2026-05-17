import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  allowedDevOrigins: ['192.168.1.113'],
  async rewrites() {
    return [
      {
        source: '/api/investigate',
        destination: 'http://localhost:8000/api/investigate',
      },
      {
        source: '/api/report/:path*',
        destination: 'http://localhost:8000/api/report/:path*',
      },
      {
        source: '/api/chat',
        destination: 'http://localhost:8000/api/chat',
      },
      {
        source: '/api/export/:path*',
        destination: 'http://localhost:8000/api/export/:path*',
      },
      {
        source: '/api/status/:path*',
        destination: 'http://localhost:8000/api/status/:path*',
      },
    ]
  },
}

export default nextConfig
