import type Anthropic from "@anthropic-ai/sdk";
import {
  BUILD_SPEC_JSON_SCHEMA,
  BuildSpecSchema,
  type BuildSpec,
  type DiscoveryState,
} from "@f1-cb/spec";
import { getAnthropicClient, SPEC_COMPILER_MODEL } from "./client";
import { loadPrompt } from "./loadPrompt";
import type { ChatMessage } from "./discoveryAgent";

export type CompileResult =
  | { ok: true; buildSpec: BuildSpec; claudeMd: string }
  | { ok: false; error: string };

/**
 * F1's Prompt Architect (roadmap Part 3.3 / Part 1.4 step 6), scoped to
 * Phase 1: no Research/Business/Tech Advisor input exists yet, so most
 * `business`/`references`/`tech` fields will legitimately read "unknown —
 * <reason>" until Phase 2 wires those specialists in. `acceptance_criteria`
 * still has to be real Given/When/Then statements covering the MVP
 * features the founder actually described.
 */
export async function compileBuildSpec(
  messages: ChatMessage[],
  state: DiscoveryState
): Promise<CompileResult> {
  const client = getAnthropicClient();
  const systemPrompt = loadPrompt("prompt-architect");

  const transcript = messages
    .map((m) => `${m.role === "user" ? "Founder" : "Orchestrator"}: ${m.content}`)
    .join("\n\n");

  const specResponse = await client.messages.create({
    model: SPEC_COMPILER_MODEL,
    max_tokens: 8192,
    system: systemPrompt,
    tool_choice: { type: "tool", name: "emit_build_spec" },
    tools: [
      {
        name: "emit_build_spec",
        description:
          "Emit the final buildspec.json. Every field must be filled or explicitly marked 'unknown' with a one-line reason.",
        input_schema: BUILD_SPEC_JSON_SCHEMA as unknown as Anthropic.Tool.InputSchema,
      },
    ],
    messages: [
      {
        role: "user",
        content: `Discovery state (structured):\n${JSON.stringify(state, null, 2)}\n\nFull transcript:\n${transcript}`,
      },
    ],
  });

  const toolUse = specResponse.content.find(
    (block): block is Anthropic.ToolUseBlock => block.type === "tool_use"
  );
  if (!toolUse) {
    return { ok: false, error: "Prompt Architect did not return a structured spec." };
  }

  const parsed = BuildSpecSchema.safeParse(toolUse.input);
  if (!parsed.success) {
    return { ok: false, error: `Spec failed validation: ${parsed.error.message}` };
  }

  const claudeMdResponse = await client.messages.create({
    model: SPEC_COMPILER_MODEL,
    max_tokens: 4096,
    system:
      "Write the CLAUDE.md operating file described in your instructions, for the project " +
      "whose buildspec.json follows. Output only the Markdown file contents, no commentary.",
    messages: [
      { role: "user", content: JSON.stringify(parsed.data, null, 2) },
    ],
  });
  const claudeMd = claudeMdResponse.content
    .filter((block): block is Anthropic.TextBlock => block.type === "text")
    .map((block) => block.text)
    .join("\n");

  return { ok: true, buildSpec: parsed.data, claudeMd };
}
