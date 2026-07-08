# CLAUDE.md — F1 + CB

Operating file for Claude Code in this repo. Read F1-CB-roadmap.md first for
the full architecture; this file is the condensed, always-loaded version
(Part 4.1 of the roadmap).

## What this repo is

A monorepo containing two apps and two shared packages:

- `apps/f1` — the idea refinery. A real chat UI backed by the Orchestrator +
  Discovery stage: a founder describes an idea, the Orchestrator asks batched
  questions, and once enough is known a Prompt Architect compiles a validated
  `buildspec.json` + `CLAUDE.md` for the target project.
- `apps/cb` — the Core Builder. Consumes a `buildspec.json`, runs it through
  four consent gates (Consent, Preview, Build, Feedback), ships an app.
  Still a placeholder page — this is Phase 3+.
- `packages/spec` — the Zod schema for `buildspec.json`, plus a hand-written
  JSON-Schema mirror of it (`BUILD_SPEC_JSON_SCHEMA`) and of the intermediate
  `DiscoveryState` (`DISCOVERY_STATE_JSON_SCHEMA`) used as Claude tool
  `input_schema`s. The Zod schema is the **only** contract between F1 and CB;
  both apps import from `@f1-cb/spec`, never redefine it locally.
- `packages/agents` — F1's two live agents, calling the Claude API directly
  via `@anthropic-ai/sdk`:
  - `runDiscoveryTurn` — the Orchestrator's conversational reply plus a
    second, tool-forced call that extracts structured `DiscoveryState` from
    the transcript so the UI can track progress without asking the model to
    self-report JSON inline with its chat text.
  - `compileBuildSpec` — the Prompt Architect: one tool-forced call emits the
    full `buildspec.json`, a second plain-text call writes the project's
    `CLAUDE.md`.
- `prompts/` — the five master system prompts from roadmap Part 3, as
  versioned `.md` files. `packages/agents` loads these at runtime rather than
  inlining prompt text in code, so a non-engineer can edit agent behavior
  without touching TypeScript.

## Stack decisions (Part 5 of the roadmap, refined in Phase 1)

- Next.js 15+ / App Router / Tailwind / TypeScript for both apps.
- npm workspaces (not pnpm/turborepo) — this machine didn't have pnpm
  installed and a plain workspace is enough at this scale.
- **F1's conversational agents use the plain Claude API (`@anthropic-ai/sdk`),
  not the Claude Agent SDK.** The Agent SDK is Claude Code under the hood —
  built for coding agents with file/bash tools, not a founder-facing chat
  feature. It's the right tool for CB's Builder (Phase 3, Gate 3), not for
  F1's Orchestrator or Prompt Architect. `DISCOVERY_MODEL` (cost-efficient,
  for the high-volume multi-turn chat) and `SPEC_COMPILER_MODEL`
  (high-reasoning, for the one-shot structured spec) are set in
  `packages/agents/src/client.ts`.
- Structured output uses forced tool calls (`tool_choice: {type: "tool",
  name: ...}`) with hand-written JSON schemas in `packages/spec`, not a
  Zod-to-JSON-Schema converter — `zod-to-json-schema` pulled in a zod v4
  build that conflicted with the zod v3 used elsewhere and crashed `tsc`
  with an out-of-memory error. The hand-written schemas in
  `packages/spec/src/index.ts` and `discovery.ts` must be kept in sync with
  their Zod counterparts by hand.
- Zod for the spec schema (runtime validation + inferred TS types in one).
- Postgres via Supabase for `sessions` / `specs` / `lessons` — schema lives in
  `db/schema.sql` but **is not connected yet**. See "What's not built yet".

## Coding conventions

- Shared code goes in `packages/*`, never duplicated into both apps.
- Agent system prompts live only in `prompts/*.md`; code loads them via
  `loadPrompt()` from `@f1-cb/agents`, it never inlines prompt strings.
- Every package has a `typecheck` script; run it before considering work done.
- Keep placeholders explicit and loud (throw with a clear message) rather
  than silently no-op-ing — see `packages/agents/src/db.ts` for the pattern.

## Explicit non-goals for Phase 1

- No Research Agent, Repo Scout, Business Analyst, or Tech Advisor — that's
  Phase 2. Because of this, most `business`/`references`/`tech` fields in a
  compiled spec will read "unknown" until those specialists exist.
- No Supabase connection — schema is defined, nothing is wired up. Sessions
  and lessons are not persisted; refreshing the browser loses the chat.
- No CB gates (Consent/Preview/Build/Feedback) implemented — Phase 3+.
- No deployment/hosting setup — local-only.

## What's not built yet (and how to activate it later)

- **Supabase**: fill in `.env.local` from `.env.example`, run
  `db/schema.sql` against a Supabase project, then replace the stub in
  `packages/agents/src/db.ts` with a real `@supabase/supabase-js` client.
- **Research/Business/Tech specialist agents**: Phase 2 of the roadmap.

## How to verify work

```
npm install               # once, at repo root
npm run typecheck         # typechecks packages/spec, packages/agents, both apps
npm run build              # builds packages/spec, packages/agents, both apps
npm run dev:f1              # starts apps/f1 at localhost:3000 — the real chat UI
npm run dev:cb               # starts apps/cb at localhost:3000 (stop f1 first, or it'll pick another port)
```

Live testing the chat requires `ANTHROPIC_API_KEY` in `.env.local` (copy from
`.env.example`). Without it, `/api/chat` and `/api/compile` return a clear
"ANTHROPIC_API_KEY is not set" error instead of failing silently.
