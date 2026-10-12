import type { NextConfig } from "next";

const backend = (process.env.MEDIHUB_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const legacyPages = ["/operations", "/devices", "/mappings", "/api-setup", "/help", "/healthz", "/metrics"];

const nextConfig: NextConfig = {
  allowedDevOrigins: ["*.e2b.app"],
  poweredByHeader: false,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
      ...legacyPages.map((path) => ({ source: path, destination: `${backend}${path}` })),
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default nextConfig;
