import { NextResponse } from "next/server";
import { runDiscoveryTurn, type ChatMessage } from "@f1-cb/agents";

export async function POST(request: Request) {
  const body = await request.json();
  const history: ChatMessage[] = Array.isArray(body?.history) ? body.history : [];
  const userMessage: string = body?.userMessage ?? "";

  if (!userMessage.trim()) {
    return NextResponse.json({ error: "userMessage is required" }, { status: 400 });
  }

  try {
    const result = await runDiscoveryTurn(history, userMessage);
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
