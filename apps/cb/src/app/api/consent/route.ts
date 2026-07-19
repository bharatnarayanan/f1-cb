import { NextResponse } from "next/server";
import { getSpecById, recordConsent, runConsentTurn, type ChatMessage } from "@f1-cb/agents";

/**
 * CB Gate 1 (roadmap Part 2.1 / 3.4). The route never decides approval
 * itself — it defers entirely to runConsentTurn's tool-forced decision, and
 * only calls recordConsent when that decision says approved.
 */
export async function POST(request: Request) {
  const body = await request.json();
  const specId: string = body?.specId ?? "";
  const history: ChatMessage[] = Array.isArray(body?.history) ? body.history : [];
  const userMessage: string = body?.userMessage ?? "";
  const approvedBy: string = typeof body?.approvedBy === "string" ? body.approvedBy : "";

  if (!specId) {
    return NextResponse.json({ error: "specId is required" }, { status: 400 });
  }
  if (!userMessage.trim()) {
    return NextResponse.json({ error: "userMessage is required" }, { status: 400 });
  }

  try {
    const existing = await getSpecById(specId);
    if (!existing) {
      return NextResponse.json({ error: `No spec found for id ${specId}` }, { status: 404 });
    }
    if (existing.buildSpec.consent) {
      return NextResponse.json(
        { error: "This spec already has recorded consent." },
        { status: 409 }
      );
    }

    const result = await runConsentTurn(existing.buildSpec, history, userMessage);

    let consentRecorded = false;
    let recordError: string | undefined;
    if (result.approved) {
      if (!approvedBy.trim()) {
        recordError = "Approval detected, but no name was given to record as approved_by.";
      } else {
        await recordConsent(specId, {
          approved_by: approvedBy.trim(),
          timestamp: new Date().toISOString(),
          notes: result.notes,
        });
        consentRecorded = true;
      }
    }

    return NextResponse.json({ ...result, consentRecorded, recordError });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
