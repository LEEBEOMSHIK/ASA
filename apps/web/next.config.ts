import type { NextConfig } from "next";

const config: NextConfig = {
  devIndicators: { position: "top-right" },
  output: "standalone", poweredByHeader: false,
  experimental: { proxyClientMaxBodySize: "28mb" },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${process.env.ASA_API_ORIGIN || "http://127.0.0.1:8127"}/api/v1/:path*` }];
  },
};
export default config;
