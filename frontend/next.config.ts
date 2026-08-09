import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    // Canonicals, the sitemap and robots.txt are built from this. Defaulting it
    // keeps local development working; getting it wrong in production publishes
    // wrong canonical URLs, which is worse than publishing none.
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  },
  // `/discussions` and `/discussions/` are different URLs to a crawler. Next's
  // default is already no-slash; pinning it means the decision survives a
  // config someone copies from another project.
  trailingSlash: false,
};

export default nextConfig;
