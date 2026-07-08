"use client";

import { useState } from "react";
import { emptyDiscoveryState, type BuildSpec, type DiscoveryState } from "@f1-cb/spec";

type ChatMessage = { role: "user" | "assistant"; content: string };

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [state, setState] = useState<DiscoveryState>(emptyDiscoveryState);
  const [error, setError] = useState<string | null>(null);

  const [compiling, setCompiling] = useState(false);
  const [compiled, setCompiled] = useState<{ buildSpec: BuildSpec; claudeMd: string } | null>(
    null
  );

  async function sendMessage() {
    const userMessage = input.trim();
    if (!userMessage || sending) return;
    setError(null);
    setSending(true);
    setInput("");
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ history: messages, userMessage }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Chat request failed");
      setMessages(data.messages);
      setState(data.state);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSending(false);
    }
  }

  async function compileSpec() {
    setCompiling(true);
    setError(null);
    try {
      const res = await fetch("/api/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, state }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error ?? "Compilation failed");
      setCompiled({ buildSpec: data.buildSpec, claudeMd: data.claudeMd });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setCompiling(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-6 font-sans">
      <header>
        <h1 className="text-2xl font-semibold">F1 — Idea Refinery</h1>
        <p className="text-sm text-zinc-500">
          Tell the Orchestrator your idea. Once it has enough to work with, you&apos;ll get a
          chance to review before it compiles a Build Spec for the Core Builder.
        </p>
      </header>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
          {error.includes("ANTHROPIC_API_KEY") && (
            <p className="mt-1 text-xs">
              Add your key to <code>.env.local</code> at the repo root, then restart{" "}
              <code>npm run dev:f1</code>.
            </p>
          )}
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-6 md:grid-cols-3">
        <section className="flex flex-col gap-3 md:col-span-2">
          <div className="flex-1 space-y-3 overflow-y-auto rounded border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            {messages.length === 0 && (
              <p className="text-sm text-zinc-400">
                Start by describing your idea in a sentence or two.
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-auto max-w-[80%] rounded-lg bg-zinc-900 px-3 py-2 text-sm text-white dark:bg-zinc-100 dark:text-black"
                    : "mr-auto max-w-[80%] rounded-lg bg-zinc-100 px-3 py-2 text-sm dark:bg-zinc-800"
                }
              >
                {m.content}
              </div>
            ))}
            {sending && <p className="text-sm text-zinc-400">Orchestrator is thinking…</p>}
          </div>
          <div className="flex gap-2">
            <textarea
              className="flex-1 rounded border border-zinc-300 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Describe your idea…"
            />
            <button
              onClick={sendMessage}
              disabled={sending || !input.trim()}
              className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-black"
            >
              Send
            </button>
          </div>
        </section>

        <aside className="flex flex-col gap-4">
          <div className="rounded border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="mb-2 font-medium">Idea so far</h2>
            <dl className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
              <div>
                <dt className="inline font-medium">Name: </dt>
                <dd className="inline">{state.idea_name ?? "—"}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Sector: </dt>
                <dd className="inline">{state.sector ?? "—"}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Problem: </dt>
                <dd className="inline">{state.problem_statement ?? "—"}</dd>
              </div>
              <div>
                <dt className="inline font-medium">MVP features: </dt>
                <dd className="inline">{state.core_features_mvp.length}</dd>
              </div>
            </dl>
            {state.missing_fields.length > 0 && (
              <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                Still need: {state.missing_fields.join(", ")}
              </p>
            )}
          </div>

          {state.ready_to_compile && !compiled && (
            <div className="rounded border border-emerald-300 bg-emerald-50 p-4 text-sm dark:border-emerald-900 dark:bg-emerald-950">
              <h2 className="mb-1 font-medium">Pitstop: ready to compile</h2>
              <p className="mb-3 text-xs text-zinc-600 dark:text-zinc-400">
                The Orchestrator has enough to draft a Build Spec. Review the summary on the
                left, then confirm.
              </p>
              <button
                onClick={compileSpec}
                disabled={compiling}
                className="w-full rounded bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-40"
              >
                {compiling ? "Compiling…" : "Looks right — compile spec"}
              </button>
            </div>
          )}
        </aside>
      </div>

      {compiled && (
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="mb-2 font-medium">buildspec.json</h2>
            <pre className="max-h-96 overflow-auto rounded bg-zinc-900 p-3 text-xs text-zinc-100">
              {JSON.stringify(compiled.buildSpec, null, 2)}
            </pre>
          </div>
          <div className="rounded border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="mb-2 font-medium">CLAUDE.md</h2>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-zinc-900 p-3 text-xs text-zinc-100">
              {compiled.claudeMd}
            </pre>
          </div>
          <div className="md:col-span-2">
            <button
              disabled
              title="CB isn't built yet — this lands in Phase 3"
              className="rounded border border-zinc-300 px-4 py-2 text-sm text-zinc-400 dark:border-zinc-700"
            >
              Send to CB (not built yet)
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
