import { PROMPTS } from "./generated/prompts";

/**
 * Master prompts live in /prompts at the repo root (Part 3 of the roadmap).
 * Their text is baked into ./generated/prompts.ts at build time (see
 * scripts/build-prompts.js) rather than read from disk at request time —
 * a __dirname-relative read broke under Next.js, which rewrites __dirname
 * to a virtual placeholder for workspace packages it bundles.
 */
export function loadPrompt(name: string): string {
  const prompt = PROMPTS[name];
  if (!prompt) {
    throw new Error(
      `No prompt named "${name}" — checked generated/prompts.ts (built from /prompts/${name}.md).`
    );
  }
  return prompt;
}
