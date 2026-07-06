# F1 + Core Builder (CB): Architecture, Prompts & Build Roadmap

**Purpose:** One package. F1 refines any raw idea into a battle-tested Build Spec. CB takes that spec and ships a working app — with human consent gates, a UI preview stage, and a self-improving feedback loop. You prompt once per phase, not a hundred times per app.

---

## Part 0 — The One Decision That Makes Everything Work

F1 and CB must communicate through a **structured contract**, not loose prose. F1's final output is a machine-readable **Build Spec** (`buildspec.json` + `CLAUDE.md`). CB refuses to start without one. This contract is what kills repetitive prompting: every downstream agent reads the spec instead of asking you again.

```
IDEA ──▶ [ F1 FRAMEWORK ] ──▶ buildspec.json + CLAUDE.md ──▶ [ CB ENGINE ] ──▶ Shipped App
              │                                                    │
        Pitstops (learning loop)                        Consent → Preview → Build → Feedback loop
```

---

## Part 1 — F1 Framework (Idea Refinery)

### 1.1 What F1 is

A web app with a chat-first interface plus filters (sector, problem type, target user, monetization intent, build complexity). Behind the chat sits an **Orchestrator** that spawns specialist agents on demand as the conversation progresses — exactly the "create one whenever necessary" behavior you described.

### 1.2 Agent roster

| Agent | Job | Suggested model |
|---|---|---|
| **Orchestrator / Interface Agent** | Runs the chat, decides which specialist to spawn, gives on-the-fly tips, manages pitstops | claude-sonnet-4-6 (fast, agentic) |
| **Research Agent** | Market landscape, competitors, best-in-class references, domain constraints (e.g., SEBI rules for an FNO app, DPDP/child-safety norms for a school app) | claude-sonnet-4-6 + web search tool |
| **Repo Scout** | Finds recent GitHub repos similar to the idea, summarizes what's reusable, flags licenses | claude-haiku-4-5 + GitHub API/search |
| **Business Analyst Agent** | Finds *missing* business points: revenue model gaps, unit economics, compliance, GTM, edge cases the user hasn't thought of | claude-opus-4-8 (deep reasoning) |
| **Tech Stack Advisor** | Picks LLMs, frameworks, DBs, hosting; justifies each choice against the idea's constraints | claude-sonnet-4-6 |
| **Prompt Architect** | Compiles everything into the final Build Spec + the master prompt for CB | claude-opus-4-8 (highest-stakes output) |
| **Pitstop Agent** | At checkpoints, reviews the session, writes "lessons" to a learning store, proposes UI/flow improvements to F1 itself | claude-sonnet-4-6 |

Spawn rule of thumb: Orchestrator always on; Research + Repo Scout fire in parallel early; Business Analyst after the idea is stated; Tech Advisor mid-way; Prompt Architect only at the end. Haiku for cheap high-volume scanning, Opus-class for judgment-heavy synthesis.

### 1.3 The Pitstop mechanic (F1's learning loop)

A pitstop fires at fixed stages (after Discovery, after Research, before Spec) and on triggers (user confusion, contradictory requirements). Each pitstop does three things:

1. **Summarize & confirm** — shows the user "here's where your idea stands," gets a yes/no.
2. **Log a lesson** — writes to a `lessons` table: what questions worked, what the user corrected, which sector patterns emerged.
3. **Evolve** — periodically (say every 10 sessions) a maintenance agent reads `lessons` and proposes concrete changes: new filter options in the UI, better default questions per sector, updated reference lists. You approve; it ships. This is how F1 "learns from experience" without any model fine-tuning.

### 1.4 F1 pipeline stages

1. **Intake** — filters + free-text idea → Orchestrator classifies sector/complexity.
2. **Discovery** — structured Socratic questioning (max ~8 questions, batched, never one-at-a-time nagging).
3. **Research burst** — Research Agent + Repo Scout run in parallel; results streamed into chat as cards.
4. **Gap analysis** — Business Analyst lists missing business points, risks, compliance items. *Pitstop.*
5. **Tech shaping** — Stack Advisor proposes architecture + model choices with rationale.
6. **Spec compilation** — Prompt Architect emits `buildspec.json` + `CLAUDE.md` + a human-readable summary. *Final pitstop: user signs off.*

### 1.5 Build Spec schema (the F1→CB contract)

```json
{
  "meta": { "idea_name": "", "sector": "", "version": "1.0", "date": "" },
  "problem": { "statement": "", "target_users": [], "jobs_to_be_done": [] },
  "solution": { "core_features_mvp": [], "features_v2": [], "explicit_non_goals": [] },
  "business": { "model": "", "compliance": [], "risks": [], "open_questions": [] },
  "references": { "similar_repos": [{"url": "", "reusable": "", "license": ""}], "best_in_class": [] },
  "tech": {
    "frontend": "", "backend": "", "database": "", "auth": "", "hosting": "",
    "llms": [{"task": "", "model": "", "why": ""}]
  },
  "ui": { "style_direction": "", "key_screens": [], "user_flows": [] },
  "acceptance_criteria": [ "Given/When/Then statements CB must satisfy" ],
  "build_prompt": "The master prompt Prompt Architect writes for CB"
}
```

`acceptance_criteria` is the secret weapon — it lets CB's feedback agent *test its own work* instead of asking you.

---

## Part 2 — Core Builder (CB) Engine

### 2.1 CB pipeline — four gates, human consent at each

**Gate 1: Workflow Consent (Consent Agent).** Reads the Build Spec, restates the plan in plain language, raises any references or workflow concerns, discusses tradeoffs with you in chat. **Nothing builds until you type "approved."** Approval is recorded into the spec (`consent: {approved_by, timestamp, notes}`).

**Gate 2: UI Preview (Preview Agent).** Generates a clickable mock (static Next.js/React pages or v0-style renders) of key screens *before* any backend exists. You do cosmetic + functional edits here — cheap to change now, expensive later. Edits are written back into `buildspec.json → ui`. Second consent checkpoint.

**Gate 3: Build (Builder = Claude Code).** Claude Code runs headless/agentically against the repo, driven entirely by `CLAUDE.md` + the spec. It works feature-by-feature against `acceptance_criteria`, committing per feature. You watch, you don't prompt.

**Gate 4: Feedback Loop (Feedback Agent).** You give feedback in natural language ("the dashboard feels cramped, and login should support OTP"). The Feedback Agent (a) interprets it, (b) checks it against the spec, (c) **proposes 2–3 additional improvements of its own** that are consistent with your feedback, (d) shows you the combined change list, and only after your nod re-renders/rebuilds. Every accepted change updates the spec, so the spec is always the single source of truth.

### 2.2 CB agent roster

| Agent | Model | Notes |
|---|---|---|
| Consent Agent | claude-sonnet-4-6 | Conversational, cites spec sections |
| Preview Agent | claude-sonnet-4-6 | Generates UI code for mocks |
| Builder | Claude Code (Opus/Sonnet per task) | The heavy lifter; runs in your repo |
| Feedback Agent | claude-opus-4-8 | Needs judgment: interpret vague feedback, propose sensible extras |
| QA/Verifier Agent | claude-haiku-4-5 or sonnet | Runs tests + checks acceptance criteria after each build cycle |

---

## Part 3 — The Master Prompts

These are drop-in system prompts. Keep them in your repo under `/prompts/` so they're versioned.

### 3.1 F1 Orchestrator

```
You are the F1 Orchestrator — the interface agent of an idea-refinement framework.
Your mission: take the user's raw idea through Intake → Discovery → Research →
Gap Analysis → Tech Shaping → Spec Compilation, ending in a Build Spec.

Rules:
- Batch your questions (max 4 at a time). Never interrogate one question per turn.
- Spawn specialist agents via the provided tools when their stage arrives; run
  Research and Repo Scout in parallel.
- Offer one concrete tip or reference in every substantive reply ("on the fly" value).
- At each PITSTOP: summarize the idea's current state in ≤150 words, ask for
  confirmation, and log a lesson via the log_lesson tool.
- Never advance a stage without user confirmation at the pitstop.
- Track state in the session object; never ask for information already given.
- Your final act: call the Prompt Architect and deliver buildspec.json + CLAUDE.md.
Tone: sharp co-founder, not a form-filler.
```

### 3.2 Business Analyst Agent

```
You are a ruthless business analyst. Input: the current idea state JSON.
Output: (1) the 5–10 business points the user has NOT considered — monetization
gaps, compliance (be jurisdiction-specific), unit economics, cold-start problems,
retention risks; (2) for each, a one-line mitigation; (3) 3 open questions the
user must answer before build. Do not restate what the user already knows.
Be specific to the sector — generic advice is failure.
```

### 3.3 Prompt Architect (F1's final stage)

```
You compile the entire session into two artifacts:
1. buildspec.json — strictly following the provided schema. Every field filled
   or explicitly marked "unknown" with a reason. acceptance_criteria must be
   testable Given/When/Then statements covering every MVP feature.
2. CLAUDE.md — the operating file for Claude Code containing: project overview,
   stack decisions with rationale, coding conventions, folder structure, what
   NOT to do (explicit_non_goals), and how to verify work (test commands).
Then write build_prompt: a single self-sufficient instruction for the CB engine
that requires zero clarifying questions. If you cannot make it self-sufficient,
list what's missing and send the session back to the Orchestrator instead.
```

### 3.4 CB Consent Agent

```
You are the Consent Agent of the Core Builder. Input: buildspec.json.
1. Restate the build plan in plain language: what will be built, in what order,
   with which stack, and what will NOT be built.
2. Surface any spec items marked "unknown" or any risks — resolve them in
   conversation with the human.
3. Discuss workflow preferences (branch strategy, deploy target, review cadence).
4. You are FORBIDDEN from triggering the Builder until the human explicitly
   says "approved". Record consent into the spec before handoff.
```

### 3.5 CB Feedback Agent

```
You are the Feedback Agent. Input: human feedback + buildspec.json + current build.
Process:
1. Interpret the feedback into concrete change items (file/feature level).
2. Check each against acceptance_criteria — flag conflicts instead of silently breaking things.
3. Propose 2–3 additional improvements of your own that are small, consistent
   with the feedback's intent, and clearly labeled "proposed, not requested".
4. Present the combined change list for approval. On approval: update
   buildspec.json (bump version), then hand the delta to the Builder.
Never rebuild from scratch when a delta suffices.
```

---

## Part 4 — Killing Repetitive Prompting (Loop Engineering)

This is your "vibecoding / context coding" layer, made systematic:

1. **CLAUDE.md as persistent context.** Claude Code automatically reads `CLAUDE.md` in the repo. F1 writes it once; every Claude Code session starts fully briefed. You never re-explain the project. Docs: https://docs.claude.com/en/docs/claude-code/overview
2. **Spec-driven loops.** The Builder's loop is: pick next unmet acceptance criterion → implement → run tests → self-verify → commit → next. The loop terminates on criteria, not on your patience.
3. **Verifier closes the loop.** QA Agent runs the test suite + criteria checklist after every cycle. Failures go back to the Builder automatically — you only see green builds or genuine blockers.
4. **Feedback compiles into spec.** Because every change updates `buildspec.json`, context never rots. "Prompting" becomes "editing a living spec," which is one interaction, not twenty.
5. **Sub-agent delegation.** In Claude Code, define custom subagents (e.g., `ui-polisher`, `test-writer`) so specialized work doesn't pollute the main context window.
6. **Session memory for F1.** Store sessions + lessons in Postgres; embed past specs so F1 can say "this resembles your school-app spec from March — reuse its auth pattern?"

---

## Part 5 — Recommended Stack for F1 + CB Themselves

| Layer | Choice | Why |
|---|---|---|
| Frontend (F1 UI + CB console) | Next.js 15 + Tailwind + shadcn/ui | Fast, and Claude Code is excellent at it |
| Agent backend | Claude Agent SDK (TypeScript or Python) | Native orchestration, tool use, subagents, MCP support |
| Model access | Claude API (`claude-opus-4-8`, `claude-sonnet-4-6`, `claude-haiku-4-5`) | Mix per agent as in the tables above |
| Research tools | Anthropic web search tool + GitHub REST/Search API | Powers Research Agent + Repo Scout |
| Store | Postgres (Supabase) + pgvector | Sessions, specs, lessons, embeddings for the learning loop |
| Build execution | Claude Code (headless mode) in a sandboxed container per project | The CB Builder |
| Preview hosting | Vercel preview deploys | Gate-2 clickable mocks with shareable URLs |
| Queue/events | Inngest or a simple job table | Pitstop triggers, parallel agent runs |

Verify current model names/pricing at https://docs.claude.com/en/api/overview before you lock choices — they evolve.

---

## Part 6 — Phased Build Plan (each phase = one Claude Code run)

**Phase 0 — Skeleton (1–2 days).** Monorepo (`apps/f1`, `apps/cb`, `packages/spec`, `packages/agents`, `prompts/`). Define the Build Spec schema as a Zod/JSON-Schema package — shared by both apps. Write the root `CLAUDE.md`.

**Phase 1 — F1 core loop (week 1).** Chat UI + Orchestrator + Discovery stage + spec compilation (no research agents yet). Milestone: raw idea in → valid `buildspec.json` out.

**Phase 2 — F1 specialists (week 2).** Research Agent (web search), Repo Scout (GitHub API), Business Analyst, Tech Advisor, parallel execution, streaming result cards. Pitstop logging to Postgres.

**Phase 3 — CB Gates 1–3 (week 3).** Consent Agent chat, Preview Agent generating mock screens to a Vercel preview, Builder integration: spawn Claude Code headless against a fresh repo seeded with the spec's `CLAUDE.md`. Milestone: approved spec → deployed MVP with zero mid-build prompts.

**Phase 4 — Feedback + QA loop (week 4).** Feedback Agent with self-proposals, QA/Verifier running acceptance criteria, spec versioning, delta rebuilds.

**Phase 5 — Evolution layer (ongoing).** Maintenance agent that mines `lessons` and opens PRs against F1's own UI/prompts. Sector filter presets learned from usage. Cross-project memory ("reuse auth from spec #12").

**Stitching:** one dashboard, two tabs (Refine / Build), one shared spec store. A "Send to CB" button on F1's final pitstop is the entire integration — because the contract carries everything.

---

## Part 7 — Your First Prompt (to start Phase 0 in Claude Code)

```
Read this roadmap file. Create the monorepo skeleton exactly as Phase 0 describes:
apps/f1 (Next.js), apps/cb (Next.js), packages/spec (Zod schema for buildspec.json
matching the schema in Part 1.5), packages/agents (Claude Agent SDK setup with a
stub Orchestrator), prompts/ (the five master prompts from Part 3 as .md files),
and a root CLAUDE.md encoding the conventions in Part 4. Set up Postgres via
Supabase with tables: sessions, specs, lessons. Verify everything compiles and
write a README with run instructions. Do not build UI beyond a placeholder page.
```

Ship Phase 0, then feed each subsequent phase as a single prompt. The system you're building is the reason you'll never need to prompt in fragments again.
