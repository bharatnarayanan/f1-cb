-- Postgres schema for F1 + CB (Part 5: "Store" row, Part 1.3 pitstop lessons).
--
-- NOT CONNECTED YET. This file is a placeholder describing the tables Phase 1+
-- will need once Supabase is wired up. To activate:
--   1. Create a Supabase project.
--   2. Run this file against it (Supabase SQL editor, or `psql` / the CLI).
--   3. Fill in .env.local using .env.example as a guide.
--   4. Replace the stub in packages/agents/src/db.ts with a real client.

create extension if not exists "uuid-ossp";
create extension if not exists vector; -- pgvector, for embedding past specs (Part 4.6)

-- One row per F1 conversation (Intake -> Spec Compilation).
create table if not exists sessions (
  id uuid primary key default uuid_generate_v4(),
  user_id text,
  stage text not null default 'intake', -- intake | discovery | research | gap_analysis | tech_shaping | spec_compilation
  state jsonb not null default '{}'::jsonb, -- session object the Orchestrator tracks (Part 3.1)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Versioned buildspec.json snapshots (Part 1.5). One session can have many
-- versions as CB's Feedback Agent (Gate 4) bumps them.
create table if not exists specs (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid references sessions(id) on delete cascade,
  version text not null,
  spec jsonb not null, -- validated against packages/spec BuildSpecSchema before insert
  embedding vector(1536), -- for "this resembles your spec from March" (Part 4.6)
  created_at timestamptz not null default now()
);

-- Pitstop lessons (Part 1.3): what questions worked, what the user corrected,
-- which sector patterns emerged. A maintenance agent mines this periodically.
create table if not exists lessons (
  id uuid primary key default uuid_generate_v4(),
  session_id uuid references sessions(id) on delete set null,
  stage text not null,
  lesson text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
