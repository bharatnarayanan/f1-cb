import { NextResponse } from "next/server";
import { compileBuildSpec } from "@f1-cb/agents";
import { emptyDiscoveryState, type DiscoveryState } from "@f1-cb/spec";
import type { ChatMessage } from "@f1-cb/agents";

export async function POST(request: Request) {
  const body = await request.json();
  const messages: ChatMessage[] = Array.isArray(body?.messages) ? body.messages : [];
  const state: DiscoveryState = body?.state ?? emptyDiscoveryState;

  try {
    const result = await compileBuildSpec(messages, state);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
