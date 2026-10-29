import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone", poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${process.env.ASA_API_ORIGIN || "http://127.0.0.1:8127"}/api/v1/:path*` }];
  },
};
export default config;
