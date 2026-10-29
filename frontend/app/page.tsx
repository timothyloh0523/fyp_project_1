"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type OptionItem = { label: string; option: string; is_correct?: boolean; explanation?: string };
type Stats = { curr_streak: number; best_streak: number; total_score: number; total_attempts: number; weekly_score: number };
type GoalType = "weekly_score" | "weekly_win_rate" | "weekly_attempts";
type UserGoal = { goal_type: GoalType; number: number; period: "week"; enabled: boolean };
type ChatResponse = {
  thread_id: string;
  response: string;
  tutor_response: string;
  probe_question: string | null;
  awaiting_eval: boolean;
  options_list: OptionItem[];
  user_stats: Stats;
  score?: number;
  weekly_score?: number;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const USER_ID = "default_user";
const DEFAULT_GOAL: UserGoal = { goal_type: "weekly_score", number: 10, period: "week", enabled: true };
const GOAL_LABELS: Record<GoalType, string> = {
  weekly_score: "Correct answers this week",
  weekly_win_rate: "Weekly win rate",
  weekly_attempts: "Questions attempted this week",
};

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
  const [goal, setGoal] = useState<UserGoal>(DEFAULT_GOAL);
  const [weeklyCorrect, setWeeklyCorrect] = useState(0);
  const [showGoalEditor, setShowGoalEditor] = useState(false);
  const [goalDraft, setGoalDraft] = useState(String(DEFAULT_GOAL.number));

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/api/stats/${USER_ID}`).then((response) => response.ok ? response.json() : null),
      fetch(`${API_URL}/api/users/${USER_ID}`).then((response) => response.ok ? response.json() : null),
    ]).then(([userStats, profile]) => {
      if (userStats) {
        setStats(userStats);
        setWeeklyCorrect(userStats.weekly_score ?? 0);
      }
      const savedGoal = profile?.goals?.[0] as UserGoal | undefined;
      const currentGoal = savedGoal ?? DEFAULT_GOAL;
      setGoal(currentGoal);
      setGoalDraft(String(currentGoal.number));
    }).catch(() => undefined);
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
      setWeeklyCorrect(result.weekly_score ?? result.user_stats.weekly_score ?? 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function saveGoal(event: FormEvent) {
    event.preventDefault();
    const target = Math.max(1, Number.parseInt(goalDraft, 10) || DEFAULT_GOAL.number);
    const nextGoal: UserGoal = { goal_type: "weekly_score", number: target, period: "week", enabled: true };
    const response = await fetch(`${API_URL}/api/users/${USER_ID}/goals`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify([nextGoal]),
    });
    if (response.ok) {
      setGoal(nextGoal);
      setShowGoalEditor(false);
    } else {
      setError("Could not save your weekly goal.");
    }
  }

  const progress = Math.min(100, Math.round((weeklyCorrect / goal.number) * 100));

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
        <section className="user-stats-card header-user-stats" aria-label="User stats">
          <div className="user-stats-heading">
            <div>
              <p className="eyebrow">YOUR PROGRESS</p>
              <h2>User stats</h2>
            </div>
            <span className="stats-badge">✦</span>
          </div>
          <div className="lifetime-stats">
            <div><span>Lifetime score</span><strong>{stats?.total_score ?? 0}</strong></div>
            <div><span>Streak</span><strong>{stats?.curr_streak ?? 0}</strong></div>
          </div>
          <div className="weekly-goal">
            <div className="goal-title">
              <span>{GOAL_LABELS[goal.goal_type]}</span>
              <strong>{weeklyCorrect} / {goal.number}</strong>
            </div>
            <div className="progress-track"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
            <div className="goal-footer"><span>{progress}% complete</span><button onClick={() => setShowGoalEditor(true)}>Set goal</button></div>
          </div>
        </section>
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
        <div className="right-rail">
          <section className="user-stats-card" aria-label="User stats">
            <div className="user-stats-heading">
              <div>
                <p className="eyebrow">YOUR PROGRESS</p>
                <h2>User stats</h2>
              </div>
              <span className="stats-badge">✦</span>
            </div>
            <div className="lifetime-stats">
              <div><span>Lifetime score</span><strong>{stats?.total_score ?? 0}</strong></div>
              <div><span>Streak</span><strong>{stats?.curr_streak ?? 0}</strong></div>
            </div>
            <div className="weekly-goal">
              <div className="goal-title">
                <span>{GOAL_LABELS[goal.goal_type]}</span>
                <strong>{weeklyCorrect} / {goal.number}</strong>
              </div>
              <div className="progress-track"><div className="progress-fill" style={{ width: `${progress}%` }} /></div>
              <div className="goal-footer"><span>{progress}% complete</span><button onClick={() => setShowGoalEditor(true)}>Set goal</button></div>
            </div>
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
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {showGoalEditor && (
        <div className="modal-backdrop" role="presentation" onClick={() => setShowGoalEditor(false)}>
          <form className="goal-modal" onSubmit={saveGoal} onClick={(event) => event.stopPropagation()}>
            <p className="eyebrow">WEEKLY GOAL</p>
            <h2>Choose your target</h2>
            <label>
              Goal type
              <select value={goal.goal_type} disabled>
                <option value="weekly_score">Correct answers this week</option>
                <option value="weekly_win_rate">Weekly win rate (coming soon)</option>
                <option value="weekly_attempts">Questions attempted (coming soon)</option>
              </select>
            </label>
            <label>
              Correct answers
              <input type="number" min="1" value={goalDraft} onChange={(event) => setGoalDraft(event.target.value)} autoFocus />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={() => setShowGoalEditor(false)}>Cancel</button>
              <button type="submit">Save goal</button>
            </div>
          </form>
        </div>
      )}
    </main>
  );
}
