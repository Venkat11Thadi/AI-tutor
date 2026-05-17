import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  Clock3,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  Trash2,
  Zap,
} from "lucide-react";
import { runTutorPipeline } from "./lib/tutorApi";

const STORAGE_KEY = "socraticcs_sessions_v1";

const WELCOME_MESSAGE = {
  role: "assistant",
  content:
    "Welcome to SocraticCS. I am your AI tutor for programming and computer science. My job is to help you discover the answer, not simply hand it over. Ask a CS question or share a problem you are stuck on, and I will guide you with focused hints.",
  hint_level: 0,
  intent: "welcome",
  timestamp: new Date().toISOString(),
};

function createSession() {
  return {
    id: crypto.randomUUID(),
    title: "New Session",
    topic: "CS/Programming",
    messages: [],
    hint_count: 0,
    understanding_score: 0,
    jailbreak_threshold: 70,
    status: "active",
    struggle_areas: [],
    concepts_mastered: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function normalizeStoredSession(session) {
  return {
    ...createSession(),
    ...session,
    jailbreak_threshold: clampJailbreakThreshold(session?.jailbreak_threshold ?? 70),
  };
}

function clampJailbreakThreshold(value) {
  return Math.min(90, Math.max(70, Number(value) || 70));
}

function formatTime(value) {
  if (!value) return "";
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function relativeTime(value) {
  if (!value) return "just now";
  const diff = Date.now() - new Date(value).getTime();
  const minutes = Math.max(1, Math.round(diff / 60000));
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.round(hours / 24);
  return `${days} days ago`;
}

function titleFromMessage(message) {
  const cleaned = message.trim().replace(/\s+/g, " ");
  if (!cleaned) return "New Session";
  return cleaned.length > 34 ? `${cleaned.slice(0, 34)}...` : cleaned;
}

function normalizeSessionFromApi(previous, updatedState, firstUserMessage) {
  return {
    ...previous,
    ...updatedState,
    id: previous.id,
    title:
      previous.title === "New Session" && firstUserMessage
        ? titleFromMessage(firstUserMessage)
        : previous.title,
    jailbreak_threshold: clampJailbreakThreshold(updatedState.jailbreak_threshold),
    updated_at: new Date().toISOString(),
  };
}

function App() {
  const [sessions, setSessions] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return [createSession()];
    try {
      const parsed = JSON.parse(saved);
      return Array.isArray(parsed) && parsed.length
        ? parsed.map(normalizeStoredSession)
        : [createSession()];
    } catch {
      return [createSession()];
    }
  });
  const [activeId, setActiveId] = useState(() => sessions[0]?.id);
  const [view, setView] = useState("chat");
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  const activeSession = sessions.find((session) => session.id === activeId) || sessions[0];
  const visibleMessages = activeSession.messages.length
    ? activeSession.messages
    : [WELCOME_MESSAGE];

  const stats = useMemo(() => {
    const completed = sessions.filter((session) => session.status === "completed").length;
    const totalHints = sessions.reduce((sum, session) => sum + (session.hint_count || 0), 0);
    const avgUnderstanding = sessions.length
      ? Math.round(
          sessions.reduce((sum, session) => sum + (session.understanding_score || 0), 0) /
            sessions.length
        )
      : 0;
    const topics = sessions.reduce((acc, session) => {
      const topic = session.topic || "CS/Programming";
      acc[topic] = (acc[topic] || 0) + 1;
      return acc;
    }, {});
    return { completed, totalHints, avgUnderstanding, topics };
  }, [sessions]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeSession.messages.length, isSending]);

  function updateActiveSession(updater) {
    setSessions((current) =>
      current.map((session) => (session.id === activeSession.id ? updater(session) : session))
    );
  }

  function startNewSession() {
    const session = createSession();
    setSessions((current) => [session, ...current]);
    setActiveId(session.id);
    setView("chat");
    setDraft("");
    setError("");
  }

  function deleteSession(sessionId) {
    setSessions((current) => {
      const next = current.filter((session) => session.id !== sessionId);
      if (!next.length) {
        const replacement = createSession();
        setActiveId(replacement.id);
        setView("chat");
        return [replacement];
      }
      if (sessionId === activeId) {
        setActiveId(next[0].id);
        setView("chat");
      }
      return next;
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending) return;

    const userMessage = {
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };
    const sessionForApi = {
      ...activeSession,
      messages: [...activeSession.messages, userMessage],
    };

    setDraft("");
    setError("");
    setIsSending(true);
    updateActiveSession((session) => ({
      ...session,
      title: session.title === "New Session" ? titleFromMessage(message) : session.title,
      messages: [...session.messages, userMessage],
      updated_at: new Date().toISOString(),
    }));

    try {
      const result = await runTutorPipeline({
        userMessage: message,
        sessionState: sessionForApi,
      });

      setSessions((current) =>
        current.map((session) =>
          session.id === activeSession.id
            ? normalizeSessionFromApi(session, result.updatedState, message)
            : session
        )
      );
    } catch (err) {
      setSessions((current) =>
        current.map((session) => {
          if (session.id !== activeSession.id) return session;
          return {
            ...session,
            messages: session.messages.filter(
              (item) => item.timestamp !== userMessage.timestamp
            ),
          };
        })
      );
      setDraft(message);
      setError(err.message || "Could not reach the tutor API.");
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" type="button" onClick={() => setView("chat")}>
          <span className="brand-mark">
            <BrainCircuit size={24} />
          </span>
          <span>
            <strong>SocraticCS</strong>
            <small>AI Tutor</small>
          </span>
        </button>

        <nav className="nav-stack" aria-label="Main navigation">
          <button className={view === "chat" ? "nav-item active" : "nav-item"} onClick={startNewSession}>
            <Plus size={19} />
            New Session
          </button>
          <button
            className={view === "dashboard" ? "nav-item active" : "nav-item"}
            onClick={() => setView("dashboard")}
          >
            <BarChart3 size={19} />
            Progress Dashboard
          </button>
        </nav>

        <section className="recent-list" aria-label="Recent sessions">
          <p className="section-label">Recent Sessions</p>
          {sessions.slice(0, 8).map((session) => (
            <div
              className={session.id === activeSession.id ? "session-row selected" : "session-row"}
              key={session.id}
            >
              <button
                className="session-open"
                type="button"
                onClick={() => {
                  setActiveId(session.id);
                  setView("chat");
                }}
              >
                <MessageSquare size={17} />
                <span>
                  <strong>{session.title}</strong>
                  <small>{session.topic || "CS/Programming"} - {relativeTime(session.updated_at)}</small>
                </span>
              </button>
              <button
                className="icon-button danger"
                type="button"
                aria-label={`Delete ${session.title}`}
                onClick={() => deleteSession(session.id)}
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </section>
      </aside>

      <main className="main-panel">
        {view === "chat" ? (
          <ChatView
            session={activeSession}
            messages={visibleMessages}
            draft={draft}
            setDraft={setDraft}
            handleSubmit={handleSubmit}
            handleKeyDown={handleKeyDown}
            isSending={isSending}
            error={error}
            messagesEndRef={messagesEndRef}
          />
        ) : (
          <Dashboard
            sessions={sessions}
            stats={stats}
            startNewSession={startNewSession}
            deleteSession={deleteSession}
          />
        )}
      </main>
    </div>
  );
}

function ChatView({
  session,
  messages,
  draft,
  setDraft,
  handleSubmit,
  handleKeyDown,
  isSending,
  error,
  messagesEndRef,
}) {
  return (
    <div className="chat-view">
      <header className="topbar">
        <div className="title-row">
          <Sparkles size={22} />
          <div>
            <h1>{session.title}</h1>
            <p>{session.topic || "CS/Programming"}</p>
          </div>
        </div>
        <div className="topbar-tools">
          <div className="score-pill">
            <TrendingUp size={18} />
            <span>Understanding</span>
            <strong>{session.understanding_score || 0}%</strong>
            <small>{session.hint_count || 0} hints</small>
            <div className="mini-progress">
              <span style={{ width: `${session.understanding_score || 0}%` }} />
            </div>
          </div>
        </div>
      </header>

      <section className="message-stage" aria-label="Tutor conversation">
        {messages.map((message, index) => (
          <MessageBubble key={`${message.timestamp || "message"}-${index}`} message={message} />
        ))}
        {isSending && (
          <div className="message-line assistant">
            <div className="avatar">
              <BrainCircuit size={21} />
            </div>
            <div className="bubble thinking">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </section>

      <footer className="composer-wrap">
        {error && <div className="error-banner">{error}</div>}
        <form className="composer" onSubmit={handleSubmit}>
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What CS concept are you working on? Ask your question..."
            rows={3}
          />
          <div className="composer-actions">
            <span>Enter to send - Shift+Enter for newline</span>
            <button className="send-button" type="submit" disabled={!draft.trim() || isSending}>
              <Send size={21} />
            </button>
          </div>
        </form>
      </footer>
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <article className={isUser ? "message-line user" : "message-line assistant"}>
      {!isUser && (
        <div className="avatar">
          <BrainCircuit size={21} />
        </div>
      )}
      <div>
        <div className="bubble">
          <p>{message.content}</p>
          {!isUser && message.intent && message.intent !== "welcome" && (
            <div className="bubble-meta">
              <span className={`intent-tag ${message.intent}`}>{message.intent}</span>
              <span className="hint-tag">hint {message.hint_level ?? 0}</span>
            </div>
          )}
        </div>
        <time>{formatTime(message.timestamp)}</time>
      </div>
    </article>
  );
}

function Dashboard({ sessions, stats, startNewSession, deleteSession }) {
  const recent = [...sessions].sort(
    (a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
  );
  const reviewAreas = [...new Set(sessions.flatMap((session) => session.struggle_areas || []))];
  const mastered = [...new Set(sessions.flatMap((session) => session.concepts_mastered || []))];

  return (
    <div className="dashboard-view">
      <header className="dashboard-header">
        <div className="brand-inline">
          <span className="brand-mark">
            <BrainCircuit size={24} />
          </span>
          <strong>SocraticCS</strong>
          <span>/</span>
          <p>Progress Dashboard</p>
        </div>
        <button className="primary-action" type="button" onClick={startNewSession}>
          <Plus size={19} />
          New Session
        </button>
      </header>

      <section className="stat-grid" aria-label="Learning stats">
        <StatCard label="Total Sessions" value={sessions.length} icon={<MessageSquare />} tone="teal" />
        <StatCard label="Completed" value={stats.completed} icon={<Target />} tone="green" />
        <StatCard label="Avg Understanding" value={`${stats.avgUnderstanding}%`} icon={<TrendingUp />} tone="amber" />
        <StatCard label="Total Hints Used" value={stats.totalHints} icon={<Zap />} tone="violet" />
      </section>

      <section className="dashboard-grid">
        <Panel title="Understanding Score Trend" icon={<TrendingUp size={22} />}>
          <div className="bar-chart">
            {recent.slice(0, 6).map((session, index) => (
              <div className="bar-item" key={session.id}>
                <span className="bar-track">
                  <span style={{ height: `${Math.max(session.understanding_score || 0, 3)}%` }} />
                </span>
                <small>S{index + 1}</small>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Topics Studied" icon={<BookOpen size={22} />}>
          <div className="topic-list">
            {Object.entries(stats.topics).map(([topic, count]) => (
              <div className="topic-row" key={topic}>
                <span>{topic}</span>
                <div>
                  <span style={{ width: `${Math.min(count * 30, 100)}%` }} />
                </div>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Areas to Review" icon={<Target size={22} />} danger>
          <TagList values={reviewAreas} empty="No review areas yet." tone="review" />
        </Panel>

        <Panel title="Concepts Mastered" icon={<Zap size={22} />}>
          <TagList values={mastered} empty="Mastered concepts will appear here." tone="mastered" />
        </Panel>
      </section>

      <section className="recent-panel">
        <div className="panel-title">
          <Clock3 size={22} />
          <h2>Recent Sessions</h2>
        </div>
        {recent.map((session) => (
          <div className="dashboard-session" key={session.id}>
            <MessageSquare size={21} />
            <div>
              <strong>{session.title}</strong>
              <span>{session.topic || "CS/Programming"} - {relativeTime(session.updated_at)}</span>
            </div>
            <div className="session-progress">
              <span style={{ width: `${session.understanding_score || 0}%` }} />
            </div>
            <strong>{session.understanding_score || 0}%</strong>
            <em>{session.status}</em>
            <button
              className="icon-button danger"
              type="button"
              aria-label={`Delete ${session.title}`}
              onClick={() => deleteSession(session.id)}
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </section>
    </div>
  );
}

function StatCard({ label, value, icon, tone }) {
  return (
    <div className={`stat-card ${tone}`}>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
      {icon}
    </div>
  );
}

function Panel({ title, icon, children, danger = false }) {
  return (
    <section className={danger ? "panel danger" : "panel"}>
      <div className="panel-title">
        {icon}
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function TagList({ values, empty, tone }) {
  if (!values.length) return <p className="empty-copy">{empty}</p>;
  return (
    <div className={`tag-list ${tone}`}>
      {values.map((value) => (
        <span key={value}>{value}</span>
      ))}
    </div>
  );
}

export default App;
