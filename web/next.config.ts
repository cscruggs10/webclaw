import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // /api/v1 is proxied by src/app/api/v1/[...path]/route.ts so the upstream
  // URL is read from API_INTERNAL_URL on each request. A rewrite here would
  // freeze the Railway private URL into the image at build time.
};

export default nextConfig;
