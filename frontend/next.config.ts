import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained .next/standalone server for container/CDN deploys.
  output: "standalone",
};

export default nextConfig;
