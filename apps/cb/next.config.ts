import path from "node:path";
import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

// Next.js only auto-loads .env.local from this app's own folder. The repo
// keeps one shared .env.local at the monorepo root instead, so both apps
// read the same Anthropic/Supabase config — load it explicitly here.
// Next's own bootstrap already calls loadEnvConfig once against this app's
// (empty) directory and caches the result process-wide, so a plain call
// here would just return that stale cache — force a reload.
loadEnvConfig(path.join(__dirname, "../.."), process.env.NODE_ENV !== "production", console, true);

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
