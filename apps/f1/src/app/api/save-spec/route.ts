import { NextResponse } from "next/server";
import { createSessionWithSpec } from "@f1-cb/agents";
import { safeParseBuildSpec } from "@f1-cb/spec";

/**
 * F1's side of the F1 -> CB handoff (roadmap Part 0). Persists a compiled
 * buildspec.json to Supabase (sessions + specs tables) so CB's Gate 1 can
 * load it by id — there's no other transport between the two apps yet.
 */
export async function POST(request: Request) {
  const body = await request.json();
  const parsed = safeParseBuildSpec(body?.buildSpec);
  if (!parsed.success) {
    return NextResponse.json(
      { ok: false, error: `Invalid buildSpec: ${parsed.error.message}` },
      { status: 400 }
    );
  }

  try {
    const { sessionId, specId } = await createSessionWithSpec(parsed.data);
    return NextResponse.json({ ok: true, sessionId, specId });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
