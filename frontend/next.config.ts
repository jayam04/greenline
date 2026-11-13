import type { NextConfig } from "next";

const NETWORTH_URL = process.env.NETWORTH_URL || "http://localhost:8001";
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/portfolio/:path*",
        destination: `${NETWORTH_URL}/api/v1/portfolio/:path*`,
      },
      {
        source: "/api/v1/snapshots/:path*",
        destination: `${NETWORTH_URL}/api/v1/snapshots/:path*`,
      },
      {
        source: "/api/v1/:path*",
        destination: `${BACKEND_URL}/api/v1/:path*`,
      },
    ];
  },
  async redirects() {
    return [
      {
        source: "/holdings",
        destination: "/investments/holdings",
        permanent: true,
      },
      {
        source: "/transactions",
        destination: "/investments/transactions",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
