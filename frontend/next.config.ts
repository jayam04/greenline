import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
