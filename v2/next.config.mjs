import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Pin the workspace root to this directory. An orphan package-lock.json
  // sits in ~/Documents, and Next otherwise infers *that* as the root, which
  // misroots module tracing and can produce "Cannot find module './NNN.js'"
  // against a stale .next cache.
  outputFileTracingRoot: dirname(fileURLToPath(import.meta.url)),

  // In development the Python API runs as a separate uvicorn process.
  // On Vercel, /api/* is served by the Python function, so no rewrite.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
  },
};

export default nextConfig;
