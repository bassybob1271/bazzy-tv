/** @type {import('next').NextConfig} */
// The browser only ever talks to this site's own address: /api/* is proxied to the
// FastAPI backend, so privacy browsers and ad blockers don't block cross-port calls.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL || "http://localhost:8000";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  skipTrailingSlashRedirect: true, // keep /api/v1/wallet/ intact for FastAPI
  async rewrites() {
    return [
      // keep a trailing slash (FastAPI routes like /api/v1/wallet/ need it)
      { source: "/api/:path*/", destination: `${API_INTERNAL_URL}/api/:path*/` },
      { source: "/api/:path*", destination: `${API_INTERNAL_URL}/api/:path*` },
    ];
  },
};
module.exports = nextConfig;
