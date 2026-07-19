-- Postgres schema for F1 + CB (Part 5: "Store" row, Part 1.3 pitstop lessons).
--
-- Connected. sessions/specs/lessons are live on this project's Supabase
-- instance; packages/agents/src/db.ts reads NEXT_PUBLIC_SUPABASE_URL /
-- SUPABASE_SERVICE_ROLE_KEY from .env.local to talk to it. To point this
-- repo at a different Supabase project later, run this file (plus the RLS
-- block at the bottom) against the new project and update .env.local.

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

-- All access goes through the server-side service-role key
-- (packages/agents/src/db.ts), which bypasses RLS — so this just blocks the
-- unused anon/publishable key from reading or writing these tables directly.
alter table sessions enable row level security;
alter table specs enable row level security;
alter table lessons enable row level security;
