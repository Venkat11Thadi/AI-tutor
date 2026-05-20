import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  Clock3,
  Eye,
  EyeOff,
  Key,
  LogOut,
  MessageSquare,
  Plus,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  Trash2,
  Zap,
} from "lucide-react";
import {
  createSession as createRemoteSession,
  deleteSession as deleteRemoteSession,
  fetchSessions,
  getCurrentUser,
  login,
  register,
  runTutorPipeline,
} from "./lib/tutorApi";

const AUTH_TOKEN_KEY = "socraticcs_auth_token_v1";

const WELCOME_MESSAGE = {
  role: "assistant",
  content:
    "Welcome to Zephyr Assist. I am your AI tutor for programming and computer science. My job is to help you discover the answer, not simply hand it over. Ask a CS question or share a problem you are stuck on, and I will guide you with focused hints.",
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

function normalizeSession(session) {
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
  const [token, setToken] = useState(() => localStorage.getItem(AUTH_TOKEN_KEY) || "");
  const [user, setUser] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [view, setView] = useState(() =>
    localStorage.getItem("socraticcs_groq_api_key") ? "chat" : "settings"
  );
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(Boolean(token));
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ email: "", password: "" });
  const [authError, setAuthError] = useState("");
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);

  const activeSession = sessions.find((session) => session.id === activeId) || sessions[0];
  const visibleMessages = activeSession?.messages?.length
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
    if (!token) {
      setIsLoadingSessions(false);
      return;
    }

    let ignore = false;
    async function loadAccount() {
      setIsLoadingSessions(true);
      try {
        const [profile, remoteSessions] = await Promise.all([
          getCurrentUser(token),
          fetchSessions(token),
        ]);
        if (ignore) return;
        let nextSessions = remoteSessions.map(normalizeSession);
        if (!nextSessions.length) {
          const created = await createRemoteSession(token);
          if (ignore) return;
          nextSessions = [normalizeSession(created)];
        }
        setUser(profile);
        setSessions(nextSessions);
        setActiveId(nextSessions[0]?.id || "");
        setError("");
        if (!localStorage.getItem("socraticcs_groq_api_key")) {
          setView("settings");
        }
      } catch (err) {
        if (ignore) return;
        localStorage.removeItem(AUTH_TOKEN_KEY);
        setToken("");
        setUser(null);
        setSessions([]);
        setActiveId("");
        setAuthError(err.message || "Please sign in again.");
      } finally {
        if (!ignore) setIsLoadingSessions(false);
      }
    }

    loadAccount();
    return () => {
      ignore = true;
    };
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeSession?.messages?.length, isSending]);

  function updateActiveSession(updater) {
    setSessions((current) =>
      current.map((session) => (session.id === activeSession?.id ? updater(session) : session))
    );
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    setAuthError("");
    setIsAuthLoading(true);
    try {
      const action = authMode === "register" ? register : login;
      const result = await action(authForm);
      localStorage.setItem(AUTH_TOKEN_KEY, result.access_token);
      setToken(result.access_token);
      setUser(result.user);
      setAuthForm({ email: "", password: "" });
      if (!localStorage.getItem("socraticcs_groq_api_key")) {
        setView("settings");
      } else {
        setView("chat");
      }
    } catch (err) {
      setAuthError(err.message || "Authentication failed.");
    } finally {
      setIsAuthLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    setToken("");
    setUser(null);
    setSessions([]);
    setActiveId("");
    setDraft("");
    setError("");
  }

  async function startNewSession() {
    if (!token) return;
    if (!localStorage.getItem("socraticcs_groq_api_key")) {
      setView("settings");
      setError("Please configure your Groq API Key first.");
      return;
    }
    setError("");
    try {
      const session = normalizeSession(await createRemoteSession(token));
      setSessions((current) => [session, ...current]);
      setActiveId(session.id);
      setView("chat");
      setDraft("");
    } catch (err) {
      setError(err.message || "Could not create a session.");
    }
  }

  async function deleteSession(sessionId) {
    if (!token) return;
    const previousSessions = sessions;
    await deleteRemoteSession(token, sessionId).catch((err) => {
      setError(err.message || "Could not delete the session.");
      throw err;
    });

    setSessions((current) => {
      const next = current.filter((session) => session.id !== sessionId);
      if (sessionId === activeId) {
        setActiveId(next[0]?.id || "");
        setView("chat");
      }
      return next;
    });

    if (previousSessions.length === 1) {
      const replacement = normalizeSession(await createRemoteSession(token));
      setSessions([replacement]);
      setActiveId(replacement.id);
      setView("chat");
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending || !activeSession || !token) return;

    if (!localStorage.getItem("socraticcs_groq_api_key")) {
      setView("settings");
      setError("Please configure your Groq API Key first.");
      return;
    }

    const userMessage = {
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
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
        sessionId: activeSession.id,
        token,
      });

      setSessions((current) =>
        current.map((session) =>
          session.id === activeSession.id
            ? normalizeSession(result.session || normalizeSessionFromApi(session, result.updatedState, message))
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
      if (err.message && (err.message.includes("Groq API key") || err.message.includes("api_key") || err.message.includes("API Key") || err.message.includes("API key"))) {
        setView("settings");
      }
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

  if (token && isLoadingSessions && !user) {
    return (
      <div className="app-shell loading-shell">
        <div className="loading-panel">
          <span className="brand-mark">
            <BrainCircuit size={24} />
          </span>
          <strong>Loading your Zephyr Assist workspace...</strong>
        </div>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <AuthView
        mode={authMode}
        setMode={setAuthMode}
        form={authForm}
        setForm={setAuthForm}
        error={authError}
        isLoading={isAuthLoading}
        onSubmit={handleAuthSubmit}
      />
    );
  }

  if (isLoadingSessions || !activeSession) {
    return (
      <div className="app-shell loading-shell">
        <div className="loading-panel">
          <span className="brand-mark">
            <BrainCircuit size={24} />
          </span>
          <strong>Loading your Zephyr Assist workspace...</strong>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" type="button" onClick={() => setView("chat")}>
          <span className="brand-mark">
            <BrainCircuit size={24} />
          </span>
          <span>
            <strong>Zephyr Assist</strong>
            <small>AI Tutor</small>
          </span>
        </button>
        <div className="user-panel">
          <span>{user.email}</span>
          <button className="icon-button" type="button" aria-label="Sign out" onClick={handleLogout}>
            <LogOut size={16} />
          </button>
        </div>

        <nav className="nav-stack" aria-label="Main navigation">
          <button 
            className={view === "chat" ? "nav-item active" : "nav-item"} 
            onClick={() => {
              if (!localStorage.getItem("socraticcs_groq_api_key")) {
                setView("settings");
                setError("Please configure your Groq API Key first.");
              } else {
                startNewSession();
              }
            }}
          >
            <Plus size={19} />
            New Session
          </button>
          <button
            className={view === "dashboard" ? "nav-item active" : "nav-item"}
            onClick={() => {
              if (!localStorage.getItem("socraticcs_groq_api_key")) {
                setView("settings");
                setError("Please configure your Groq API Key first.");
              } else {
                setView("dashboard");
              }
            }}
          >
            <BarChart3 size={19} />
            Progress Dashboard
          </button>
          <button
            className={view === "settings" ? "nav-item active" : "nav-item"}
            onClick={() => setView("settings")}
          >
            <Key size={19} />
            API Settings
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
                  if (!localStorage.getItem("socraticcs_groq_api_key")) {
                    setView("settings");
                    setError("Please configure your Groq API Key first.");
                  } else {
                    setActiveId(session.id);
                    setView("chat");
                  }
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
        ) : view === "dashboard" ? (
          <Dashboard
            sessions={sessions}
            stats={stats}
            startNewSession={startNewSession}
            deleteSession={deleteSession}
          />
        ) : (
          <SettingsView onKeySaved={() => setView("chat")} />
        )}
      </main>
    </div>
  );
}

function AuthView({ mode, setMode, form, setForm, error, isLoading, onSubmit }) {
  const isRegistering = mode === "register";
  const [showPassword, setShowPassword] = useState(false);

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <div className="brand auth-brand">
          <span className="brand-mark">
            <BrainCircuit size={24} />
          </span>
          <span>
            <strong>Zephyr Assist</strong>
            <small>AI Tutor</small>
          </span>
        </div>

        <div className="auth-copy">
          <h1>{isRegistering ? "Create your account" : "Welcome back"}</h1>
          <p>{isRegistering ? "Save every session as you learn." : "Continue from your saved sessions."}</p>
        </div>

        <form className="auth-form" onSubmit={onSubmit}>
          {error && <div className="error-banner">{error}</div>}
          <label>
            <span>Email</span>
            <input
              type="email"
              value={form.email}
              onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              autoComplete="email"
              required
            />
          </label>
          <label>
            <span>Password</span>
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                autoComplete={isRegistering ? "new-password" : "current-password"}
                minLength={8}
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          <button className="primary-action auth-submit" type="submit" disabled={isLoading}>
            {isLoading ? "Working..." : isRegistering ? "Register" : "Login"}
          </button>
        </form>

        <button
          className="auth-switch"
          type="button"
          onClick={() => setMode(isRegistering ? "login" : "register")}
        >
          {isRegistering ? "Already have an account? Login" : "Need an account? Register"}
        </button>
      </section>
    </main>
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
  const status = getAssistantStatus(message);
  return (
    <article className={isUser ? "message-line user" : "message-line assistant"}>
      {!isUser && (
        <div className="avatar">
          <BrainCircuit size={21} />
        </div>
      )}
      <div>
        {!isUser && status && (
          <div className="message-badges">
            <span className={`status-badge ${status.className}`}>{status.label}</span>
            <span className="hint-badge">hint {message.hint_level ?? 0}/5</span>
          </div>
        )}
        <div className="bubble">
          <p>{message.content}</p>
        </div>
        <time>{formatTime(message.timestamp)}</time>
      </div>
    </article>
  );
}

function getAssistantStatus(message) {
  if (!message.intent || message.intent === "welcome") return null;
  if (message.learning_state === "mastered" || message.strategy === "celebrate") {
    return { label: "Mastered!", className: "mastered" };
  }
  if (message.strategy === "unlocked_answer") {
    return { label: "Unlocked", className: "unlocked" };
  }
  const labels = {
    learning: "Learning",
    confusion: "Confusion",
    jailbreak: "Jailbreak",
  };
  return {
    label: labels[message.intent] || message.intent,
    className: message.intent,
  };
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
          <strong>Zephyr Assist</strong>
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

function SettingsView({ onKeySaved }) {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem("socraticcs_groq_api_key") || "");
  const [showKey, setShowKey] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  function handleSave(e) {
    e.preventDefault();
    const trimmed = apiKey.trim();
    if (trimmed) {
      localStorage.setItem("socraticcs_groq_api_key", trimmed);
      setSaveSuccess(true);
      setTimeout(() => {
        setSaveSuccess(false);
        if (onKeySaved) {
          onKeySaved();
        }
      }, 1000);
    }
  }

  function handleClear() {
    localStorage.removeItem("socraticcs_groq_api_key");
    setApiKey("");
    setSaveSuccess(false);
  }

  return (
    <div className="settings-view">
      <header className="dashboard-header">
        <div className="brand-inline">
          <span className="brand-mark">
            <Key size={24} />
          </span>
          <strong>Zephyr Assist</strong>
          <span>/</span>
          <p>API Settings</p>
        </div>
      </header>

      <div className="settings-content">
        <section className="settings-card">
          <h2>Groq API Configuration</h2>
          <p className="settings-description">
            To use this tutoring workspace, you need a Groq API Key. 
            If you are running the application without a pre-configured server-side key, or if you want to use your own quota, enter your key below.
            You can generate or retrieve your key from the{" "}
            <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer" className="settings-link">
              Groq Console
            </a>.
          </p>

          {!localStorage.getItem("socraticcs_groq_api_key") && (
            <div className="warning-banner">
              <strong>Notice:</strong> Please enter a valid Groq API Key to enable chat sessions.
            </div>
          )}

          <form onSubmit={handleSave} className="settings-form">
            <label className="settings-label">
              <span>Groq API Key</span>
              <div className="password-field">
                <input
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="gsk_..."
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowKey(!showKey)}
                  aria-label={showKey ? "Hide key" : "Show key"}
                >
                  {showKey ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </label>

            {saveSuccess && (
              <div className="success-banner">
                API Key saved successfully!
              </div>
            )}

            <div className="settings-actions">
              <button type="submit" className="primary-action">
                Save Key
              </button>
              {localStorage.getItem("socraticcs_groq_api_key") && (
                <button type="button" onClick={handleClear} className="secondary-action">
                  Clear Key
                </button>
              )}
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default App;
