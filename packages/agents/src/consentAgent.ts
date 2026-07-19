import type Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import type { BuildSpec } from "@f1-cb/spec";
import { getAnthropicClient, CONSENT_MODEL } from "./client";
import { loadPrompt } from "./loadPrompt";
import type { ChatMessage } from "./discoveryAgent";

export type ConsentTurnResult = {
  reply: string;
  messages: ChatMessage[];
  approved: boolean;
  notes: string;
};

const ConsentDecisionSchema = z.object({
  approved: z.boolean(),
  notes: z.string(),
});

const CONSENT_DECISION_JSON_SCHEMA = {
  type: "object",
  properties: {
    approved: { type: "boolean" },
    notes: { type: "string" },
  },
  required: ["approved", "notes"],
} as const;

const DECISION_SYSTEM = `You read a conversation between a founder and the Core Builder's
Consent Agent about a buildspec.json. Decide whether the founder's LATEST
message just gave clear, explicit approval to proceed with the build (e.g.
contains "approved", "I approve", or an unambiguous equivalent). General
enthusiasm, a question, or "looks good so far" is NOT enough on its own —
only set approved to true when the human unambiguously signed off. Summarize
any conditions, open risks, or caveats the founder attached in notes (empty
string if none).`;

/**
 * Runs one turn of CB's Gate 1 (roadmap Part 3.4 / Part 2.1): the Consent
 * Agent restates the plan, surfaces unknowns/risks, and is FORBIDDEN from
 * treating anything short of explicit approval as consent. Mirrors F1's
 * discoveryAgent pattern — one conversational call, one tool-forced
 * extraction call — so "did they approve?" doesn't rely on brittle string
 * matching in the API route.
 */
export async function runConsentTurn(
  buildSpec: BuildSpec,
  history: ChatMessage[],
  userMessage: string
): Promise<ConsentTurnResult> {
  const client = getAnthropicClient();
  const messages: ChatMessage[] = [...history, { role: "user", content: userMessage }];

  const system = `${loadPrompt("consent-agent")}\n\nbuildspec.json:\n${JSON.stringify(
    buildSpec,
    null,
    2
  )}`;

  const chatResponse = await client.messages.create({
    model: CONSENT_MODEL,
    max_tokens: 1024,
    system,
    messages,
  });
  const reply = chatResponse.content
    .filter((block): block is Anthropic.TextBlock => block.type === "text")
    .map((block) => block.text)
    .join("\n");

  const updatedMessages: ChatMessage[] = [...messages, { role: "assistant", content: reply }];

  const transcript = updatedMessages
    .map((m) => `${m.role === "user" ? "Founder" : "Consent Agent"}: ${m.content}`)
    .join("\n\n");

  const extraction = await client.messages.create({
    model: CONSENT_MODEL,
    max_tokens: 512,
    system: DECISION_SYSTEM,
    tool_choice: { type: "tool", name: "record_consent_decision" },
    tools: [
      {
        name: "record_consent_decision",
        description: "Record whether the founder's latest message gave explicit approval to build.",
        input_schema: CONSENT_DECISION_JSON_SCHEMA as unknown as Anthropic.Tool.InputSchema,
      },
    ],
    messages: [{ role: "user", content: transcript }],
  });

  const toolUse = extraction.content.find(
    (block): block is Anthropic.ToolUseBlock => block.type === "tool_use"
  );
  const parsed = toolUse ? ConsentDecisionSchema.safeParse(toolUse.input) : null;
  const decision = parsed?.success ? parsed.data : { approved: false, notes: "" };

  return { reply, messages: updatedMessages, approved: decision.approved, notes: decision.notes };
}
