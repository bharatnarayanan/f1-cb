"use client";

import { useState } from "react";
import type { BuildSpec } from "@f1-cb/spec";

type ChatMessage = { role: "user" | "assistant"; content: string };

type Consented = { approvedBy: string; timestamp: string; notes: string };

export default function Home() {
  const [specIdInput, setSpecIdInput] = useState("");
  const [loadingSpec, setLoadingSpec] = useState(false);
  const [buildSpec, setBuildSpec] = useState<BuildSpec | null>(null);
  const [specId, setSpecId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [approvedByName, setApprovedByName] = useState("");
  const [consented, setConsented] = useState<Consented | null>(null);

  async function loadSpec() {
    const id = specIdInput.trim();
    if (!id || loadingSpec) return;
    setError(null);
    setLoadingSpec(true);
    try {
      const res = await fetch(`/api/load-spec?specId=${encodeURIComponent(id)}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error ?? "Failed to load spec");
      setBuildSpec(data.buildSpec);
      setSpecId(id);
      setMessages([]);
      setConsented(
        data.buildSpec.consent
          ? {
              approvedBy: data.buildSpec.consent.approved_by,
              timestamp: data.buildSpec.consent.timestamp,
              notes: data.buildSpec.consent.notes ?? "",
            }
          : null
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBuildSpec(null);
      setSpecId(null);
    } finally {
      setLoadingSpec(false);
    }
  }

  async function sendMessage() {
    const userMessage = input.trim();
    if (!userMessage || sending || !specId || consented) return;
    setError(null);
    setSending(true);
    setInput("");
    try {
      const res = await fetch("/api/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specId, history: messages, userMessage, approvedBy: approvedByName }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setMessages(data.messages);
      if (data.consentRecorded) {
        setConsented({
          approvedBy: approvedByName.trim(),
          timestamp: new Date().toISOString(),
          notes: data.notes ?? "",
        });
      } else if (data.approved && data.recordError) {
        setError(data.recordError);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSending(false);
    }
  }

  if (!buildSpec) {
    return (
      <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 p-6 font-sans">
        <header>
          <h1 className="text-2xl font-semibold">CB — Core Builder</h1>
          <p className="text-sm text-zinc-500">
            Gate 1: Consent. Paste the spec id F1 gave you after &quot;Send to CB&quot;.
          </p>
        </header>
        {error && (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}
        <div className="flex gap-2">
          <input
            className="flex-1 rounded border border-zinc-300 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            value={specIdInput}
            onChange={(e) => setSpecIdInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadSpec()}
            placeholder="spec id from F1"
          />
          <button
            onClick={loadSpec}
            disabled={loadingSpec || !specIdInput.trim()}
            className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-black"
          >
            {loadingSpec ? "Loading…" : "Load spec"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col gap-6 p-6 font-sans">
      <header>
        <h1 className="text-2xl font-semibold">CB — Core Builder</h1>
        <p className="text-sm text-zinc-500">
          Gate 1: Consent Agent for <span className="font-medium">{buildSpec.meta.idea_name}</span>.
          Nothing builds until you type explicit approval.
        </p>
      </header>

      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
          {error.includes("ANTHROPIC_API_KEY") && (
            <p className="mt-1 text-xs">
              Add your key to <code>.env.local</code> at the repo root, then restart{" "}
              <code>npm run dev:cb</code>.
            </p>
          )}
        </div>
      )}

      {consented && (
        <div className="rounded border border-emerald-300 bg-emerald-50 p-4 text-sm dark:border-emerald-900 dark:bg-emerald-950">
          <p className="font-medium">Approved by {consented.approvedBy}</p>
          <p className="text-xs text-zinc-600 dark:text-zinc-400">{consented.timestamp}</p>
          {consented.notes && <p className="mt-1 text-xs">{consented.notes}</p>}
          <p className="mt-2 text-xs text-zinc-500">
            Recorded on the spec. Gate 2 (Preview) and the Builder aren&apos;t built yet.
          </p>
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-6 md:grid-cols-3">
        <section className="flex flex-col gap-3 md:col-span-2">
          <div className="flex-1 space-y-3 overflow-y-auto rounded border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
            {messages.length === 0 && (
              <p className="text-sm text-zinc-400">
                Ask the Consent Agent anything about the plan, or say you&apos;re ready.
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
            {sending && <p className="text-sm text-zinc-400">Consent Agent is thinking…</p>}
          </div>
          {!consented && (
            <>
              <input
                className="rounded border border-zinc-300 p-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                value={approvedByName}
                onChange={(e) => setApprovedByName(e.target.value)}
                placeholder="Your name (recorded as approved_by once you approve)"
              />
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
                  placeholder="Discuss the plan, or type your explicit approval when ready…"
                />
                <button
                  onClick={sendMessage}
                  disabled={sending || !input.trim()}
                  className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:bg-zinc-100 dark:text-black"
                >
                  Send
                </button>
              </div>
            </>
          )}
        </section>

        <aside className="flex flex-col gap-4">
          <div className="rounded border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="mb-2 font-medium">Plan summary</h2>
            <dl className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
              <div>
                <dt className="inline font-medium">Sector: </dt>
                <dd className="inline">{buildSpec.meta.sector}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Problem: </dt>
                <dd className="inline">{buildSpec.problem.statement}</dd>
              </div>
              <div>
                <dt className="inline font-medium">Stack: </dt>
                <dd className="inline">
                  {buildSpec.tech.frontend} / {buildSpec.tech.backend}
                </dd>
              </div>
            </dl>
            <h3 className="mb-1 mt-3 text-xs font-medium">MVP features</h3>
            <ul className="list-disc space-y-0.5 pl-4 text-xs text-zinc-600 dark:text-zinc-400">
              {buildSpec.solution.core_features_mvp.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
            {buildSpec.business.risks.length > 0 && (
              <>
                <h3 className="mb-1 mt-3 text-xs font-medium text-amber-600 dark:text-amber-400">
                  Risks
                </h3>
                <ul className="list-disc space-y-0.5 pl-4 text-xs text-amber-600 dark:text-amber-400">
                  {buildSpec.business.risks.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
