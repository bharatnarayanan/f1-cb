import { exampleBuildSpec } from "@f1-cb/spec";

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-zinc-50 p-8 font-sans dark:bg-black">
      <h1 className="text-2xl font-semibold">CB — Core Builder</h1>
      <p className="max-w-md text-center text-sm text-zinc-500">
        Phase 0 placeholder. This app will run the four consent-gated stages
        — Consent, Preview, Build, Feedback — described in F1-CB-roadmap.md
        Part 2. It refuses to start without a valid <code>buildspec.json</code>{" "}
        from F1. Nothing beyond this page exists yet.
      </p>
      <pre className="max-w-lg overflow-x-auto rounded bg-zinc-900 p-4 text-xs text-zinc-100">
        {JSON.stringify(exampleBuildSpec.meta, null, 2)}
      </pre>
      <p className="text-xs text-zinc-400">
        ^ proves apps/cb can import the shared @f1-cb/spec schema.
      </p>
    </div>
  );
}
