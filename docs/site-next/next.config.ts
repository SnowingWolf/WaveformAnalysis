import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  reactStrictMode: true,
  images: { unoptimized: true },
  turbopack: {
    root: process.cwd(),
  },
  // `npm run check` is the blocking TypeScript gate.  Keeping it separate
  // avoids Next's build worker re-running (and mutating) the checked config.
  typescript: { ignoreBuildErrors: true },
};

export default nextConfig;
