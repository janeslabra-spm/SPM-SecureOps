import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Next.js configuration for CellphoneMonitoring dashboard */
  reactStrictMode: true,
  output: "standalone",

  // Proxy API requests from the Next.js server to the backend container.
  // This allows the browser to call /api/* on port 3000 and have it forwarded
  // to the backend service, avoiding CORS and DNS issues.
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL ?? "http://backend:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/incidents/:path*",
        destination: `${backendUrl}/incidents/:path*`,
      },
      {
        source: "/incidents",
        destination: `${backendUrl}/incidents`,
      },
      {
        source: "/zones/:path*",
        destination: `${backendUrl}/zones/:path*`,
      },
      {
        source: "/stream/:path*",
        destination: `${backendUrl}/stream/:path*`,
      },
      {
        source: "/screenshots/:path*",
        destination: `${backendUrl}/screenshots/:path*`,
      },
    ];
  },
};

export default nextConfig;
