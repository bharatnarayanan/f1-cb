import { z } from "zod";

/**
 * Intermediate state the Orchestrator accumulates during F1's Discovery
 * stage (roadmap Part 1.4, step 2). Once `ready_to_compile` is true, this
 * gets handed to the Prompt Architect to produce a full BuildSpec.
 *
 * Deliberately narrower than BuildSpec: no research/business/tech-advisor
 * fields, since Phase 1 has no specialist agents yet (Part 6, Phase 1).
 */
export const DiscoveryStateSchema = z.object({
  idea_name: z.string().nullable(),
  sector: z.string().nullable(),
  problem_statement: z.string().nullable(),
  target_users: z.array(z.string()),
  jobs_to_be_done: z.array(z.string()),
  core_features_mvp: z.array(z.string()),
  features_v2: z.array(z.string()),
  explicit_non_goals: z.array(z.string()),
  business_model: z.string().nullable(),
  open_questions: z.array(z.string()),
  missing_fields: z.array(z.string()),
  ready_to_compile: z.boolean(),
});

export type DiscoveryState = z.infer<typeof DiscoveryStateSchema>;

/**
 * Hand-written JSON Schema mirror of DiscoveryStateSchema, for use as an
 * Anthropic tool `input_schema`. Kept separate from a Zod->JSON-Schema
 * converter deliberately: pulling one in created a zod v3/v4 nested-dependency
 * conflict (the Claude SDK depends on zod v4) that crashed `tsc`. This schema
 * is small enough to keep in sync by hand — update both together.
 */
export const DISCOVERY_STATE_JSON_SCHEMA = {
  type: "object",
  properties: {
    idea_name: { type: ["string", "null"] },
    sector: { type: ["string", "null"] },
    problem_statement: { type: ["string", "null"] },
    target_users: { type: "array", items: { type: "string" } },
    jobs_to_be_done: { type: "array", items: { type: "string" } },
    core_features_mvp: { type: "array", items: { type: "string" } },
    features_v2: { type: "array", items: { type: "string" } },
    explicit_non_goals: { type: "array", items: { type: "string" } },
    business_model: { type: ["string", "null"] },
    open_questions: { type: "array", items: { type: "string" } },
    missing_fields: { type: "array", items: { type: "string" } },
    ready_to_compile: { type: "boolean" },
  },
  required: [
    "idea_name",
    "sector",
    "problem_statement",
    "target_users",
    "jobs_to_be_done",
    "core_features_mvp",
    "features_v2",
    "explicit_non_goals",
    "business_model",
    "open_questions",
    "missing_fields",
    "ready_to_compile",
  ],
} as const;

export const emptyDiscoveryState: DiscoveryState = {
  idea_name: null,
  sector: null,
  problem_statement: null,
  target_users: [],
  jobs_to_be_done: [],
  core_features_mvp: [],
  features_v2: [],
  explicit_non_goals: [],
  business_model: null,
  open_questions: [],
  missing_fields: [
    "idea_name",
    "sector",
    "problem_statement",
    "target_users",
    "jobs_to_be_done",
    "core_features_mvp",
  ],
  ready_to_compile: false,
};
