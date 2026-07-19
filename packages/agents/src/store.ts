import { BuildSpecSchema, type BuildSpec, type Consent } from "@f1-cb/spec";
import { getDb } from "./db";

export type StoredSpec = { specId: string; sessionId: string; buildSpec: BuildSpec };

/**
 * Persists a freshly-compiled buildspec.json (F1's Prompt Architect output)
 * as a new session + first spec version, per db/schema.sql. This is the
 * handoff point in the F1 -> CB contract: CB never reads a spec except by
 * id, fetched from here.
 */
export async function createSessionWithSpec(
  buildSpec: BuildSpec
): Promise<{ sessionId: string; specId: string }> {
  const db = getDb();

  const { data: session, error: sessionError } = await db
    .from("sessions")
    .insert({ stage: "spec_compilation", state: {} })
    .select("id")
    .single();
  if (sessionError || !session) {
    throw new Error(`Failed to create session: ${sessionError?.message ?? "unknown error"}`);
  }

  const { data: spec, error: specError } = await db
    .from("specs")
    .insert({ session_id: session.id, version: buildSpec.meta.version, spec: buildSpec })
    .select("id")
    .single();
  if (specError || !spec) {
    throw new Error(`Failed to save spec: ${specError?.message ?? "unknown error"}`);
  }

  return { sessionId: session.id as string, specId: spec.id as string };
}

/**
 * Fetches a spec by id and validates it against BuildSpecSchema before
 * returning it. CB's Gate 1 must refuse to proceed on a spec that fails
 * this — returning null (not found) is distinct from throwing (found but
 * corrupt/invalid), so callers can tell the two apart.
 */
export async function getSpecById(specId: string): Promise<StoredSpec | null> {
  const db = getDb();
  const { data, error } = await db
    .from("specs")
    .select("id, session_id, spec")
    .eq("id", specId)
    .maybeSingle();
  if (error) {
    throw new Error(`Failed to load spec ${specId}: ${error.message}`);
  }
  if (!data) return null;

  const parsed = BuildSpecSchema.safeParse(data.spec);
  if (!parsed.success) {
    throw new Error(`Stored spec ${specId} failed BuildSpec validation: ${parsed.error.message}`);
  }
  return { specId: data.id as string, sessionId: data.session_id as string, buildSpec: parsed.data };
}

/**
 * Records CB Gate 1 consent onto the spec (roadmap Part 2.1, Gate 1). The
 * Consent Agent must never call this itself off a heuristic string match —
 * it goes through runConsentTurn's tool-forced approval decision first.
 */
export async function recordConsent(specId: string, consent: Consent): Promise<void> {
  const existing = await getSpecById(specId);
  if (!existing) {
    throw new Error(`Cannot record consent: spec ${specId} not found`);
  }
  const updatedSpec: BuildSpec = { ...existing.buildSpec, consent };
  const db = getDb();
  const { error } = await db.from("specs").update({ spec: updatedSpec }).eq("id", specId);
  if (error) {
    throw new Error(`Failed to record consent on spec ${specId}: ${error.message}`);
  }
}
