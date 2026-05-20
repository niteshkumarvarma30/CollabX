import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownUp,
  BadgeAlert,
  BarChart3,
  Camera,
  CheckCircle2,
  Crown,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function formatPercent(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function getCallbackError() {
  const params = new URLSearchParams(window.location.search);
  return params.get("error") || params.get("message") || "";
}

function getFriendlyError(message) {
  if (!message) return null;

  if (message.includes("Invalid Scopes")) {
    return {
      title: "Meta app permissions are not ready",
      body:
        "This App ID has not been configured for the Instagram/Page permissions yet. The app owner must add or get approval for the requested permissions in Meta Developer Dashboard.",
      action: "After that is done, reconnect with permissions.",
    };
  }

  if (message.includes("0 Facebook Pages") || message.includes("No Facebook Pages")) {
    return {
      title: "No Page was returned by Meta",
      body: message,
      action: "Use Reconnect with permissions.",
    };
  }

  if (message.includes("No Instagram Business or Creator")) {
    return {
      title: "Instagram account is not connected to the Page",
      body:
        "The selected Facebook Page must be linked to an Instagram Business or Creator account before insights are available.",
      action: "Connect the account in Meta Business Suite, then reconnect.",
    };
  }

  return {
    title: "Connection needs attention",
    body: message,
    action: "Reconnect and review the Meta settings screen.",
  };
}

function Spinner() {
  return <span className="spinner" aria-label="Loading" />;
}

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(getCallbackError());
  const [sortDesc, setSortDesc] = useState(true);

  const sortedPosts = useMemo(() => {
    const posts = dashboard?.posts || [];
    return [...posts].sort((a, b) => {
      const diff = Number(a.engagement_rate || 0) - Number(b.engagement_rate || 0);
      return sortDesc ? -diff : diff;
    });
  }, [dashboard, sortDesc]);

  const topPostId = useMemo(() => {
    if (!dashboard?.posts?.length) return null;
    return dashboard.posts.reduce((best, post) =>
      Number(post.engagement_rate || 0) > Number(best.engagement_rate || 0) ? post : best
    ).id;
  }, [dashboard]);

  async function fetchData({ silent = false } = {}) {
    setLoading(true);
    if (!silent) setError("");
    try {
      const token = localStorage.getItem("session_token");
      const headers = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/fetch-data`, {
        headers,
        credentials: "omit",
      });
      const payload = await response.json();
      if (!response.ok) {
        if (silent && response.status === 401) return;
        throw new Error(payload.detail || "Unable to fetch Instagram insights.");
      }
      setDashboard(payload);
      window.history.replaceState({}, "", "/");
    } catch (err) {
      setDashboard(null);
      if (!silent) setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("session_token");
    if (token) {
      localStorage.setItem("session_token", token);
    }

    if (params.get("connected") === "1" || token) {
      fetchData();
    } else {
      fetchData({ silent: true });
    }
  }, []);

  function connectInstagram() {
    window.location.href = `${API_BASE_URL}/login`;
  }

  function freshReconnect() {
    window.location.href = `${API_BASE_URL}/login?fresh=true`;
  }

  if (!dashboard) {
    const pageSelectionError = error.includes("0 Facebook Pages") || error.includes("No Facebook Pages");
    const friendlyError = getFriendlyError(error);

    return (
      <main className="landing">
        <section className="connect-panel wizard-panel glass-panel">
          <div className="brand-row">
            <Camera size={30} />
            <span>Instagram Insights Dashboard</span>
          </div>
          <h1>Connect Instagram analytics without sharing passwords or tokens</h1>
          <div className="wizard-grid">
            <article className="wizard-step active glass-panel">
              <ShieldCheck size={22} />
              <span>1</span>
              <strong>Start secure OAuth</strong>
              <p>You are redirected to Meta. The app never asks for your password.</p>
            </article>
            <article className="wizard-step glass-panel">
              <CheckCircle2 size={22} />
              <span>2</span>
              <strong>Approve Page access</strong>
              <p>Select the Facebook Page and its connected Instagram Business account.</p>
            </article>
            <article className="wizard-step glass-panel">
              <BarChart3 size={22} />
              <span>3</span>
              <strong>View insights</strong>
              <p>The dashboard loads posts, reach, likes, comments, and engagement.</p>
            </article>
          </div>
          <div className="button-row">
            <button className="primary-button" onClick={connectInstagram}>
              <Camera size={20} />
              Connect Instagram
            </button>
            <button className="secondary-button" onClick={freshReconnect}>
              <RefreshCw size={18} />
              Reconnect with permissions
            </button>
          </div>
          {loading && (
            <div className="status-line">
              <Spinner />
              Fetching insights
            </div>
          )}
          {error && (
            <div className="friendly-error">
              <div className="error-box">
                <BadgeAlert size={18} />
                <div>
                  <strong>{friendlyError.title}</strong>
                  <span>{friendlyError.body}</span>
                </div>
              </div>
              <p>{friendlyError.action}</p>
              {pageSelectionError && (
                <div className="reconnect-panel">
                  <button className="secondary-button" onClick={freshReconnect}>
                    <RefreshCw size={18} />
                    Reconnect with permissions
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      </main>
    );
  }

  return (
    <main className="dashboard">
      <header className="topbar glass-panel">
        <div>
          <div className="eyebrow">Connected account</div>
          <h1>@{dashboard.user.username || dashboard.user.ig_id}</h1>
        </div>
        <button className="ghost-button" onClick={fetchData} disabled={loading}>
          {loading ? <Spinner /> : <RefreshCw size={18} />}
          Refresh
        </button>
      </header>

      {error && (
        <div className="error-box dashboard-error">
          <BadgeAlert size={18} />
          <span>{error}</span>
        </div>
      )}

      <section className="summary-grid">
        <article className="metric-tile glass-panel">
          <BarChart3 size={22} />
          <span>Total posts</span>
          <strong>{dashboard.posts.length}</strong>
        </article>
        <article className="metric-tile glass-panel">
          <Camera size={22} />
          <span>Followers</span>
          <strong>{Number(dashboard.user.followers || 0).toLocaleString()}</strong>
        </article>
        <article className="metric-tile accent glass-panel">
          <Crown size={22} />
          <span>Top engagement</span>
          <strong>{formatPercent(sortedPosts[0]?.engagement_rate)}</strong>
        </article>
      </section>

      <section className="table-section">
        <div className="table-heading">
          <h2>Posts</h2>
          <button className="sort-button" onClick={() => setSortDesc((value) => !value)}>
            <ArrowDownUp size={17} />
            Engagement
          </button>
        </div>
        <div className="table-wrap glass-panel">
          <table>
            <thead>
              <tr>
                <th>Caption</th>
                <th>Reach</th>
                <th>Likes</th>
                <th>Comments</th>
                <th>Saved</th>
                <th>Shares</th>
                <th>Engagement rate</th>
              </tr>
            </thead>
            <tbody>
              {sortedPosts.map((post) => (
                <tr key={post.id} className={post.id === topPostId ? "top-post" : ""}>
                  <td>
                    <div className="caption-cell">
                      {post.id === topPostId && <span className="top-label">Top</span>}
                      <span>{post.caption || "No caption"}</span>
                    </div>
                  </td>
                  <td>{post.reach.toLocaleString()}</td>
                  <td>{post.likes.toLocaleString()}</td>
                  <td>{post.comments.toLocaleString()}</td>
                  <td>{post.saved.toLocaleString()}</td>
                  <td>{post.shares.toLocaleString()}</td>
                  <td className="rate">{formatPercent(post.engagement_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!sortedPosts.length && <div className="empty-state">No media returned for this account.</div>}
        </div>
      </section>

      {dashboard.warnings?.length > 0 && (
        <section className="warnings">
          <h2>Metric warnings</h2>
          {dashboard.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </section>
      )}
    </main>
  );
}

export default App;
