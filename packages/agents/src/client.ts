import Anthropic from "@anthropic-ai/sdk";

let client: Anthropic | null = null;

/**
 * Lazily-constructed singleton. Throws with a clear message instead of
 * letting the SDK's own error surface first — Phase 0 established the
 * pattern of failing loudly rather than silently no-op-ing.
 */
export function getAnthropicClient(): Anthropic {
  if (!process.env.ANTHROPIC_API_KEY) {
    throw new Error(
      "ANTHROPIC_API_KEY is not set. Add it to .env.local before talking to any F1 agent."
    );
  }
  if (!client) {
    client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
  }
  return client;
}

/** Cost-efficient model for the high-volume, multi-turn Discovery chat. */
export const DISCOVERY_MODEL = "claude-haiku-4-5";

/** High-reasoning model for the one-shot, high-stakes spec compilation. */
export const SPEC_COMPILER_MODEL = "claude-opus-4-8";

/** Conversational model for CB's Consent Agent (roadmap Part 2.2). */
export const CONSENT_MODEL = "claude-sonnet-4-6";
