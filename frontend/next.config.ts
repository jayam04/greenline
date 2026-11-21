import type { NextConfig } from "next";

const NETWORTH_URL = process.env.NETWORTH_URL || "http://localhost:8000";

const resolveCommunityDestination = () => {
  const raw = process.env.COMMUNITY_URL || "http://localhost:8002/api/v1/community/:path*";
  if (raw.includes(":path*")) return raw;
  const stripped = raw.replace(/\/+$/, "");
  if (stripped.endsWith("/api/v1/community")) {
    return `${stripped}/:path*`;
  }
  return `${stripped}/api/v1/community/:path*`;
};

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
        source: "/api/v1/community/:path*",
        destination: resolveCommunityDestination(),
      },
      {
        source: "/api/v1/:path*",
        destination: `${NETWORTH_URL}/api/v1/:path*`,
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
