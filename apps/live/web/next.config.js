/** @type {import('next').NextConfig} */
// The browser only ever talks to this site's own address: /api/* is proxied to the
// FastAPI backend, so privacy browsers and ad blockers don't block cross-port calls.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL || "http://localhost:8001";
// Live HLS from MediaMTX (the ATEM feed), served under this site's /hls/
const MEDIAMTX_INTERNAL_URL = process.env.MEDIAMTX_INTERNAL_URL || "http://localhost:8888";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  skipTrailingSlashRedirect: true, // keep /api/v1/wallet/ intact for FastAPI
  async rewrites() {
    return [
      // keep a trailing slash (FastAPI routes like /api/v1/wallet/ need it)
      { source: "/api/:path*/", destination: `${API_INTERNAL_URL}/api/:path*/` },
      { source: "/api/:path*", destination: `${API_INTERNAL_URL}/api/:path*` },
      { source: "/hls/:path*", destination: `${MEDIAMTX_INTERNAL_URL}/:path*` },
    ];
  },
};
module.exports = nextConfig;
