/**
 * Placeholder for the Supabase client (Part 5 "Store" row; tables defined in
 * /db/schema.sql: sessions, specs, lessons). Deliberately not implemented in
 * Phase 0 — this throws instead of silently doing nothing, so anything that
 * tries to persist a session/spec/lesson fails loudly and obviously.
 *
 * To activate:
 *   1. npm install @supabase/supabase-js --workspace @f1-cb/agents
 *   2. Run db/schema.sql against a Supabase project.
 *   3. Set NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY /
 *      SUPABASE_SERVICE_ROLE_KEY in .env.local (see .env.example).
 *   4. Replace the body below with:
 *        import { createClient } from "@supabase/supabase-js";
 *        return createClient(url, key);
 */
export function getDb(): never {
  throw new Error(
    "Supabase is not connected yet (Phase 0 placeholder). See packages/agents/src/db.ts for activation steps."
  );
}
