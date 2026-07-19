import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

/**
 * Lazily-constructed singleton Supabase client, using the service-role key
 * (server-only — this file must never be imported into client components).
 * Tables: sessions, specs, lessons — schema in /db/schema.sql.
 *
 * Fails loudly instead of silently no-op-ing if env vars are missing,
 * continuing the pattern established when this file was a Phase 0 stub.
 */
export function getDb(): SupabaseClient {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
        "SUPABASE_SERVICE_ROLE_KEY in .env.local (see .env.example), and make " +
        "sure db/schema.sql has been run against that Supabase project."
    );
  }
  if (!client) {
    client = createClient(url, key, { auth: { persistSession: false } });
  }
  return client;
}
