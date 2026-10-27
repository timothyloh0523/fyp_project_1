"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type OptionItem = { label: string; option: string; is_correct?: boolean; explanation?: string };
type Stats = { curr_streak: number; best_streak: number; total_score: number; total_attempts: number };
type ChatResponse = {
  thread_id: string;
  response: string;
  tutor_response: string;
  probe_question: string | null;
  awaiting_eval: boolean;
  options_list: OptionItem[];
  user_stats: Stats;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USER_ID = "default_user";

async function postChat(threadId: string | null, prompt: string): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, thread_id: threadId, prompt }),
  });
  if (!response.ok) throw new Error("The tutor could not be reached.");
  return response.json();
}

export default function Home() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [question, setQuestion] = useState("");
  const [options, setOptions] = useState<OptionItem[]>([]);
  const [probeQuestion, setProbeQuestion] = useState<string | null>(null);
  const [probeFeedback, setProbeFeedback] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_URL}/api/stats/${USER_ID}`)
      .then((r) => r.ok ? r.json() : null)
      .then(setStats).catch(() => undefined);
  }, []);

  const canSubmit = useMemo(() => selected.length > 0 && !loading, [selected, loading]);

  async function send(prompt: string, displayText: string) {
    setLoading(true); setError("");
    setMessages((current) => [...current, { role: "user", content: displayText }]);
    try {
      const result = await postChat(threadId, prompt);
      setThreadId(result.thread_id);
      setOptions(result.options_list ?? []);
      setProbeQuestion(result.probe_question);
      setProbeFeedback(null);
      setSelected([]);
      setStats(result.user_stats);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: result.tutor_response || result.response,
        },
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const value = question.trim(); if (!value || loading) return;
    setQuestion(""); await send(value, value);
  }

  async function submitOptions() {
    if (!canSubmit) return;
    setLoading(true);
    setError("");
    try {
      const result = await postChat(threadId, `/a ${selected.join(", ")}`);
      setThreadId(result.thread_id);
      setOptions([]);
      setSelected([]);
      setProbeFeedback(result.response);
      setStats(result.user_stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">
            LEARNLOOP / LINEAR ALGEBRA
          </p>
          <h1>
            LearnLoop tutor
          </h1>
        </div>
        <div className="stats">
          Score <strong>{stats?.total_score ?? 0}</strong> · Streak <strong>{stats?.curr_streak ?? 0}</strong>
        </div>
      </header>
      <div className="workspace">
        <section className="chat-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">
                CONVERSATION
              </p>
              <h2>
                Ask anything
              </h2>
            </div>
            <span className="status-dot">
              ● online
            </span>
          </div>
          <div className="messages">
            {
              messages.length === 0 &&
              <div className="empty-state">
                <span>
                  ✦
                </span>
                <h3>
                  What would you like to understand?
                </h3>
                <p>
                  Ask a question about linear algebra and work through it with your tutor.
                </p>
              </div>
            }
            {
              messages.map((message, index) =>
                <div className={`message ${message.role}`} key={`${index}-${message.content}`}>
                  <span className="message-label">
                    {message.role === "user" ? "YOU" : "TUTOR"}
                  </span>
                  <p>
                    {message.content}
                  </p>
                </div>
              )}
            {
              loading &&
              <div className="message assistant">
                <span className="message-label">
                  TUTOR
                </span>
                <p className="typing">
                  Thinking…
                </p>
              </div>
            }
          </div>
          <form className="composer"
            onSubmit={submitQuestion}
          >
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question…"
              aria-label="Ask the tutor a question"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!question.trim() || loading}
            >
              Send ↗
            </button>
          </form>
        </section>
        <aside className="probe-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">
                QUICK CHECK
              </p>
              <h2>
                Show your thinking
              </h2>
            </div>
            <span className="check-icon">
              ✓
            </span>
          </div>
          {options.length > 0 ? (
            <>
              <p className="probe-copy">
                {probeQuestion}
              </p>
              <p className="hint">Select all that apply
              </p>
              <div className="options">
                {options.map((item) =>
                  <button
                    className={`option ${selected.includes(item.label) ? "selected" : ""}`}
                    key={item.label}
                    onClick={() =>
                      setSelected((current) =>
                        current.includes(item.label)
                          ? current.filter((value) => value !== item.label)
                          : [...current, item.label])
                    }
                  >
                    <span className="option-key">
                      {item.label}
                    </span>
                    <span>
                      {item.option}
                    </span>
                    <span className="option-check">
                      {selected.includes(item.label) ? "✓" : ""}
                    </span>
                  </button>
                )}
              </div>
              <button
                className="submit-options"
                onClick={submitOptions}
                disabled={!canSubmit}
              >
                Submit selection <span>→</span>
              </button>
            </>
          ) : (
            <div className="probe-empty">
              <span>☷</span>
              <p className={probeFeedback ? "probe-feedback" : undefined}>
                {probeFeedback ?? "Your next check-in will appear here after you ask a question."}
              </p>
            </div>
          )}
        </aside>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </main>
  );
}
