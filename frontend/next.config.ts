import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const configuredUrl = process.env.BACKEND_URL?.trim();
    if (process.env.VERCEL === "1" && !configuredUrl) {
      throw new Error("Set BACKEND_URL to your public Render HTTPS origin in Vercel, then redeploy.");
    }
    const backendUrl = new URL(configuredUrl || "http://localhost:8000");
    if (
      !["http:", "https:"].includes(backendUrl.protocol) ||
      backendUrl.pathname !== "/" || backendUrl.search || backendUrl.hash ||
      backendUrl.username || backendUrl.password
    ) {
      throw new Error("BACKEND_URL must be an HTTP(S) origin without a path, query, or credentials.");
    }
    if (
      process.env.VERCEL === "1" &&
      (backendUrl.protocol !== "https:" ||
        ["localhost", "127.0.0.1", "0.0.0.0", "[::1]"].includes(backendUrl.hostname))
    ) {
      throw new Error("BACKEND_URL on Vercel must use your public Render HTTPS origin.");
    }
    return [{ source: "/api/:path*", destination: `${backendUrl.origin}/api/:path*` }];
  },
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
