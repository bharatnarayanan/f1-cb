import { NextResponse } from "next/server";
import { getSpecById } from "@f1-cb/agents";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const specId = searchParams.get("specId");
  if (!specId) {
    return NextResponse.json({ ok: false, error: "specId query param is required" }, { status: 400 });
  }

  try {
    const result = await getSpecById(specId);
    if (!result) {
      return NextResponse.json(
        { ok: false, error: `No spec found for id ${specId}` },
        { status: 404 }
      );
    }
    return NextResponse.json({ ok: true, buildSpec: result.buildSpec, sessionId: result.sessionId });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
