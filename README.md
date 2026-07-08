# F1 + CB

F1 refines a raw idea into a Build Spec. CB takes that spec and ships a
working app, with human consent gates along the way. See
[F1-CB-roadmap.md](./F1-CB-roadmap.md) for the full architecture and
[CLAUDE.md](./CLAUDE.md) for the condensed operating notes Claude Code reads.

**Phase 1 status:** F1's core loop is real — chat UI, Orchestrator, Discovery
stage, and spec compilation. No specialist agents (Research, Business
Analyst, Tech Advisor) yet, no database, and CB (`apps/cb`) is still a
placeholder page.

## Structure

```
apps/f1/          Next.js app — F1's chat UI, Orchestrator, spec compilation
apps/cb/          Next.js app — core builder (placeholder page only, Phase 3+)
packages/spec/    Zod schema for buildspec.json (+ hand-written JSON Schema mirrors)
packages/agents/  F1's live agents on the Claude API (@anthropic-ai/sdk)
prompts/          The 5 master system prompts, as versioned .md files
db/schema.sql     Postgres schema (sessions, specs, lessons) — NOT yet connected
.env.example      Placeholder env vars (Claude API key + Supabase, unfilled)
CLAUDE.md         Operating notes for Claude Code in this repo
```

## Setup

```bash
npm install
cp .env.example .env.local
# then put your Anthropic API key in .env.local:
#   ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```bash
npm run dev:f1     # http://localhost:3000 — F1's chat UI
```

## Verify it works

```bash
npm run typecheck   # all packages + both apps typecheck clean
npm run build        # all packages + both apps build clean
```

Then open `http://localhost:3000`, describe a raw idea in the chat, and
answer the Orchestrator's questions. Once it has enough (idea name, sector,
problem, target users, jobs to be done, MVP features), a "ready to compile"
panel appears — confirm it and the Prompt Architect emits a
`buildspec.json` and `CLAUDE.md` on screen.

Without `ANTHROPIC_API_KEY` set, the chat still loads but sending a message
returns a clear "ANTHROPIC_API_KEY is not set" error instead of failing
silently.

## What's intentionally not here yet

- Supabase is **not connected**. `db/schema.sql` defines the tables
  (`sessions`, `specs`, `lessons`) later phases will need, and `.env.example`
  lists the variables to fill in. `packages/agents/src/db.ts` throws a clear
  "not connected yet" error rather than pretending to work. This means chat
  history is lost on refresh — nothing persists yet.
- No Research Agent, Repo Scout, Business Analyst, or Tech Advisor — Phase 2.
  Compiled specs will have "unknown" in most `business`/`references`/`tech`
  fields until those exist.
- No CB consent gates (Consent/Preview/Build/Feedback) — Phase 3+.

## Next step

Feed the roadmap's Phase 2 instructions (Part 6) to Claude Code once you're
ready to add F1's specialist agents (Research, Repo Scout, Business Analyst,
Tech Advisor) and pitstop logging.
