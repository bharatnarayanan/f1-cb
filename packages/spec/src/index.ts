import { z } from "zod";

/**
 * The Build Spec is the sole contract between F1 (idea refinery) and CB
 * (Core Builder). See F1-CB-roadmap.md Part 1.5 for the source schema.
 * CB must refuse to start work on a spec that fails this validation.
 */

export const LlmChoiceSchema = z.object({
  task: z.string(),
  model: z.string(),
  why: z.string(),
});

export const SimilarRepoSchema = z.object({
  url: z.string(),
  reusable: z.string(),
  license: z.string(),
});

export const ConsentSchema = z.object({
  approved_by: z.string(),
  timestamp: z.string(),
  notes: z.string().optional(),
});

export const BuildSpecSchema = z.object({
  meta: z.object({
    idea_name: z.string(),
    sector: z.string(),
    version: z.string(),
    date: z.string(),
  }),
  problem: z.object({
    statement: z.string(),
    target_users: z.array(z.string()),
    jobs_to_be_done: z.array(z.string()),
  }),
  solution: z.object({
    core_features_mvp: z.array(z.string()),
    features_v2: z.array(z.string()),
    explicit_non_goals: z.array(z.string()),
  }),
  business: z.object({
    model: z.string(),
    compliance: z.array(z.string()),
    risks: z.array(z.string()),
    open_questions: z.array(z.string()),
  }),
  references: z.object({
    similar_repos: z.array(SimilarRepoSchema),
    best_in_class: z.array(z.string()),
  }),
  tech: z.object({
    frontend: z.string(),
    backend: z.string(),
    database: z.string(),
    auth: z.string(),
    hosting: z.string(),
    llms: z.array(LlmChoiceSchema),
  }),
  ui: z.object({
    style_direction: z.string(),
    key_screens: z.array(z.string()),
    user_flows: z.array(z.string()),
  }),
  acceptance_criteria: z.array(z.string()),
  build_prompt: z.string(),
  // Populated by CB's Consent Agent (Gate 1) once a human types "approved".
  // Absent on specs fresh out of F1.
  consent: ConsentSchema.optional(),
});

/**
 * Hand-written JSON Schema mirror of BuildSpecSchema, for use as an
 * Anthropic tool `input_schema` (see DISCOVERY_STATE_JSON_SCHEMA in
 * discovery.ts for why this isn't generated from the Zod schema).
 */
export const BUILD_SPEC_JSON_SCHEMA = {
  type: "object",
  properties: {
    meta: {
      type: "object",
      properties: {
        idea_name: { type: "string" },
        sector: { type: "string" },
        version: { type: "string" },
        date: { type: "string" },
      },
      required: ["idea_name", "sector", "version", "date"],
    },
    problem: {
      type: "object",
      properties: {
        statement: { type: "string" },
        target_users: { type: "array", items: { type: "string" } },
        jobs_to_be_done: { type: "array", items: { type: "string" } },
      },
      required: ["statement", "target_users", "jobs_to_be_done"],
    },
    solution: {
      type: "object",
      properties: {
        core_features_mvp: { type: "array", items: { type: "string" } },
        features_v2: { type: "array", items: { type: "string" } },
        explicit_non_goals: { type: "array", items: { type: "string" } },
      },
      required: ["core_features_mvp", "features_v2", "explicit_non_goals"],
    },
    business: {
      type: "object",
      properties: {
        model: { type: "string" },
        compliance: { type: "array", items: { type: "string" } },
        risks: { type: "array", items: { type: "string" } },
        open_questions: { type: "array", items: { type: "string" } },
      },
      required: ["model", "compliance", "risks", "open_questions"],
    },
    references: {
      type: "object",
      properties: {
        similar_repos: {
          type: "array",
          items: {
            type: "object",
            properties: {
              url: { type: "string" },
              reusable: { type: "string" },
              license: { type: "string" },
            },
            required: ["url", "reusable", "license"],
          },
        },
        best_in_class: { type: "array", items: { type: "string" } },
      },
      required: ["similar_repos", "best_in_class"],
    },
    tech: {
      type: "object",
      properties: {
        frontend: { type: "string" },
        backend: { type: "string" },
        database: { type: "string" },
        auth: { type: "string" },
        hosting: { type: "string" },
        llms: {
          type: "array",
          items: {
            type: "object",
            properties: {
              task: { type: "string" },
              model: { type: "string" },
              why: { type: "string" },
            },
            required: ["task", "model", "why"],
          },
        },
      },
      required: ["frontend", "backend", "database", "auth", "hosting", "llms"],
    },
    ui: {
      type: "object",
      properties: {
        style_direction: { type: "string" },
        key_screens: { type: "array", items: { type: "string" } },
        user_flows: { type: "array", items: { type: "string" } },
      },
      required: ["style_direction", "key_screens", "user_flows"],
    },
    acceptance_criteria: { type: "array", items: { type: "string" } },
    build_prompt: { type: "string" },
  },
  required: [
    "meta",
    "problem",
    "solution",
    "business",
    "references",
    "tech",
    "ui",
    "acceptance_criteria",
    "build_prompt",
  ],
} as const;

export type BuildSpec = z.infer<typeof BuildSpecSchema>;
export type LlmChoice = z.infer<typeof LlmChoiceSchema>;
export type SimilarRepo = z.infer<typeof SimilarRepoSchema>;
export type Consent = z.infer<typeof ConsentSchema>;

/**
 * Validates an unknown value as a BuildSpec. Throws a ZodError with a
 * readable path/message list on failure — CB's Gate 1 should catch this
 * and refuse to proceed rather than guessing at missing fields.
 */
export function parseBuildSpec(input: unknown): BuildSpec {
  return BuildSpecSchema.parse(input);
}

export function safeParseBuildSpec(input: unknown) {
  return BuildSpecSchema.safeParse(input);
}

export { exampleBuildSpec } from "./example";

export {
  DiscoveryStateSchema,
  DISCOVERY_STATE_JSON_SCHEMA,
  emptyDiscoveryState,
  type DiscoveryState,
} from "./discovery";
