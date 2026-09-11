import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  reactStrictMode: true,
  // This is a self-contained offline export, not a rolling server deployment.
  // A stable id keeps tracked output reproducible and lets content-hashed chunks
  // carry the cache identity instead of rewriting every exported route.
  generateBuildId: async () => "waveform-docs-v1",
  images: { unoptimized: true },
  turbopack: {
    root: process.cwd(),
  },
  // Keep Next's own type gate enabled in addition to the explicit `npm run check` gate.
  typescript: { ignoreBuildErrors: false },
};

export default nextConfig;
