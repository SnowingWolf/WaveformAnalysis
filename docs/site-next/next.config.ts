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
  // `npm run check` is the blocking TypeScript gate.  Keeping it separate
  // avoids Next's build worker re-running (and mutating) the checked config.
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
