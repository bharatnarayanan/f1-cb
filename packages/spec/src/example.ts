import type { BuildSpec } from "./index";

/**
 * A minimal but fully-valid BuildSpec, used by both apps' placeholder pages
 * and by tests, so there's always one known-good example to compare against.
 */
export const exampleBuildSpec: BuildSpec = {
  meta: {
    idea_name: "Example Idea",
    sector: "unknown",
    version: "0.0.1",
    date: "2026-07-07",
  },
  problem: {
    statement: "unknown — replace once F1's Discovery stage exists",
    target_users: [],
    jobs_to_be_done: [],
  },
  solution: {
    core_features_mvp: [],
    features_v2: [],
    explicit_non_goals: [],
  },
  business: {
    model: "unknown",
    compliance: [],
    risks: [],
    open_questions: [],
  },
  references: {
    similar_repos: [],
    best_in_class: [],
  },
  tech: {
    frontend: "Next.js",
    backend: "unknown",
    database: "unknown",
    auth: "unknown",
    hosting: "unknown",
    llms: [],
  },
  ui: {
    style_direction: "unknown",
    key_screens: [],
    user_flows: [],
  },
  acceptance_criteria: [],
  build_prompt: "unknown — F1's Prompt Architect has not run yet",
};
