import type Anthropic from "@anthropic-ai/sdk";
import {
  DISCOVERY_STATE_JSON_SCHEMA,
  DiscoveryStateSchema,
  emptyDiscoveryState,
  type DiscoveryState,
} from "@f1-cb/spec";
import { getAnthropicClient, DISCOVERY_MODEL } from "./client";
import { loadPrompt } from "./loadPrompt";

export type ChatMessage = { role: "user" | "assistant"; content: string };

export type DiscoveryTurnResult = {
  reply: string;
  messages: ChatMessage[];
  state: DiscoveryState;
};

const STATE_EXTRACTOR_SYSTEM = `You read a conversation between a founder and an idea-refinement
assistant (the Orchestrator). Extract the current state of the founder's
idea into the record_discovery_state tool. Only include information the
founder has actually stated — never invent details. Set ready_to_compile
to true only once idea_name, sector, problem_statement, target_users,
jobs_to_be_done, and core_features_mvp are all filled in. List anything
still missing in missing_fields.`;

/**
 * Runs one turn of F1's Discovery stage (roadmap Part 1.4, step 2):
 * 1. The Orchestrator replies conversationally, using the batched-questions
 *    rules from prompts/orchestrator.md.
 * 2. A second, tool-forced call extracts the current DiscoveryState from
 *    the full transcript so the UI (and eventual spec compilation) can
 *    track progress without the model having to self-report structured
 *    JSON inline with its chat reply.
 */
export async function runDiscoveryTurn(
  history: ChatMessage[],
  userMessage: string
): Promise<DiscoveryTurnResult> {
  const client = getAnthropicClient();
  const messages: ChatMessage[] = [...history, { role: "user", content: userMessage }];

  const orchestratorSystem = loadPrompt("orchestrator");
  const chatResponse = await client.messages.create({
    model: DISCOVERY_MODEL,
    max_tokens: 1024,
    system: orchestratorSystem,
    messages,
  });
  const reply = chatResponse.content
    .filter((block): block is Anthropic.TextBlock => block.type === "text")
    .map((block) => block.text)
    .join("\n");

  const updatedMessages: ChatMessage[] = [...messages, { role: "assistant", content: reply }];

  const transcript = updatedMessages
    .map((m) => `${m.role === "user" ? "Founder" : "Orchestrator"}: ${m.content}`)
    .join("\n\n");

  const extraction = await client.messages.create({
    model: DISCOVERY_MODEL,
    max_tokens: 1024,
    system: STATE_EXTRACTOR_SYSTEM,
    tool_choice: { type: "tool", name: "record_discovery_state" },
    tools: [
      {
        name: "record_discovery_state",
        description: "Record the founder's idea state extracted from the transcript so far.",
        input_schema: DISCOVERY_STATE_JSON_SCHEMA as unknown as Anthropic.Tool.InputSchema,
      },
    ],
    messages: [{ role: "user", content: transcript }],
  });

  const toolUse = extraction.content.find(
    (block): block is Anthropic.ToolUseBlock => block.type === "tool_use"
  );
  const parsed = toolUse ? DiscoveryStateSchema.safeParse(toolUse.input) : null;
  const state = parsed?.success ? parsed.data : emptyDiscoveryState;

  return { reply, messages: updatedMessages, state };
}
