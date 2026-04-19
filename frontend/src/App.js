import React, { useState, useRef, useCallback, useEffect } from "react";
import {
  AlertTriangle, Shield, TrendingUp, TrendingDown, Minus,
  Search, Plus, X, ChevronDown, ChevronUp, Zap, Brain,
  Globe, BarChart2, CheckCircle, XCircle, AlertCircle,
  RefreshCw, ExternalLink, Eye, Radio, Loader, Settings,
  FileText, Activity, Target, Info
} from "lucide-react";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line,
} from "recharts";
import "./App.css";

// ── Constants ─────────────────────────────────────────────────────────────────
const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const RISK_COLORS = {
  critical: "#ff2d55",
  high: "#ff9500",
  medium: "#ffcc00",
  low: "#34c759",
};

const SENTIMENT_COLORS = {
  positive: "#34c759",
  neutral: "#636366",
  negative: "#ff3b30",
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function RiskBadge({ level }) {
  const colors = { critical: "badge-critical", high: "badge-high", medium: "badge-medium", low: "badge-low" };
  return <span className={`badge ${colors[level] || "badge-low"}`}>{level?.toUpperCase()}</span>;
}

function SentimentIcon({ sentiment }) {
  if (sentiment === "positive") return <TrendingUp size={14} color="#34c759" />;
  if (sentiment === "negative") return <TrendingDown size={14} color="#ff3b30" />;
  return <Minus size={14} color="#636366" />;
}

function CredibilityBar({ score }) {
  const color = score >= 80 ? "#34c759" : score >= 60 ? "#ffcc00" : "#ff3b30";
  return (
    <div className="cred-bar-container" title={`Credibility: ${score}/100`}>
      <div className="cred-bar-fill" style={{ width: `${score}%`, background: color }} />
    </div>
  );
}

function StageIndicator({ stages, currentStage }) {
  const stageList = ["planning", "scraping", "source_analysis", "sentiment", "risk", "synthesis"];
  return (
    <div className="stage-indicator">
      {stageList.map((s) => (
        <div key={s} className={`stage-dot ${currentStage === s ? "active" : stages.includes(s) ? "done" : ""}`}>
          <div className="dot" />
          <span>{s.replace("_", " ")}</span>
        </div>
      ))}
    </div>
  );
}

// ── API Config Panel ──────────────────────────────────────────────────────────
function ApiConfigPanel({ config, onChange }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="api-config-panel">
      <button className="config-toggle" onClick={() => setExpanded(!expanded)}>
        <Settings size={14} />
        <span>API Configuration</span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {expanded && (
        <div className="config-fields">
          <div className="config-note">
            <Info size={12} /> Free-tier optimized: requests are batched and rate-limited
          </div>
          {[
            { key: "gemini_api_key", label: "Gemini API Key *", placeholder: "AIza...", required: true },
            { key: "finnhub_api_key", label: "Finnhub API Key", placeholder: "optional — market signals" },
            { key: "news_api_key", label: "NewsAPI Key", placeholder: "optional — structured news" },
            { key: "fact_check_api_key", label: "Fact Check API Key", placeholder: "optional — Google FC API" },
          ].map(({ key, label, placeholder, required }) => (
            <div key={key} className="config-field">
              <label>{label}</label>
              <input
                type="password"
                placeholder={placeholder}
                value={config[key] || ""}
                onChange={(e) => onChange({ ...config, [key]: e.target.value })}
                className={required && !config[key] ? "input-required" : ""}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Article Card ─────────────────────────────────────────────────────────────
function ArticleCard({ article, index }) {
  const [expanded, setExpanded] = useState(false);
  const sentiment = article.sentiment || "neutral";

  return (
    <div className={`article-card sentiment-border-${sentiment}`}>
      <div className="article-header" onClick={() => setExpanded(!expanded)}>
        <div className="article-meta">
          <span className="article-source">{article.source}</span>
          <SentimentIcon sentiment={sentiment} />
          {article.scrape_method === "crawl4ai" && (
            <span className="scrape-badge">crawl4ai</span>
          )}
        </div>
        <h4 className="article-title">{article.title}</h4>
        <span className="expand-btn">{expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</span>
      </div>
      {expanded && (
        <div className="article-body">
          <p className="article-desc">{article.description}</p>
          {article.content && article.content !== article.description && (
            <p className="article-content">{article.content.slice(0, 600)}...</p>
          )}
          <a href={article.url} target="_blank" rel="noopener noreferrer" className="article-link">
            <ExternalLink size={12} /> Read full article
          </a>
        </div>
      )}
    </div>
  );
}

// ── Risk Dashboard ────────────────────────────────────────────────────────────
function RiskDashboard({ risk }) {
  if (!risk) return null;

  const radarData = [
    { subject: "Keywords", value: risk.components?.keyword_risk || 0, max: 40 },
    { subject: "Sentiment", value: risk.components?.sentiment_risk || 0, max: 20 },
    { subject: "Credibility", value: risk.components?.credibility_risk || 0, max: 20 },
    { subject: "Market", value: risk.components?.market_risk || 0, max: 20 },
  ].map(d => ({ ...d, normalized: Math.round((d.value / d.max) * 100) }));

  return (
    <div className="risk-dashboard">
      <div className="risk-header">
        <div className="risk-score-circle" style={{ borderColor: RISK_COLORS[risk.overall_risk] }}>
          <span className="risk-score-num">{risk.risk_score}</span>
          <span className="risk-score-label">/ 100</span>
        </div>
        <div className="risk-info">
          <RiskBadge level={risk.overall_risk} />
          <p className="risk-method">{risk.methodology}</p>
          {risk.components?.geopolitical_multiplier > 1 && (
            <span className="geo-amp">
              ×{risk.components.geopolitical_multiplier} geo amplifier
            </span>
          )}
        </div>
      </div>

      <div className="risk-charts">
        <ResponsiveContainer width="100%" height={200}>
          <RadarChart data={radarData}>
            <PolarGrid stroke="#2c2c2e" />
            <PolarAngleAxis dataKey="subject" tick={{ fill: "#8e8e93", fontSize: 11 }} />
            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
            <Radar name="Risk" dataKey="normalized" stroke={RISK_COLORS[risk.overall_risk]}
              fill={RISK_COLORS[risk.overall_risk]} fillOpacity={0.25} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {risk.risk_factors?.length > 0 && (
        <div className="risk-factors">
          <h5>Risk Factors</h5>
          {risk.risk_factors.map((f, i) => (
            <div key={i} className="risk-factor">
              <AlertTriangle size={12} color="#ff9500" /> {f}
            </div>
          ))}
        </div>
      )}

      {risk.recommendations?.length > 0 && (
        <div className="recommendations">
          <h5>Recommendations</h5>
          {risk.recommendations.map((r, i) => (
            <div key={i} className="recommendation">
              <Target size={12} color="#0a84ff" /> {r}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Sentiment Panel ───────────────────────────────────────────────────────────
function SentimentPanel({ sentiment }) {
  if (!sentiment?.summary) return null;
  const { summary, results } = sentiment;

  const pieData = [
    { name: "Positive", value: summary.positive_pct * 100, color: "#34c759" },
    { name: "Neutral", value: summary.neutral_pct * 100, color: "#636366" },
    { name: "Negative", value: summary.negative_pct * 100, color: "#ff3b30" },
  ].filter(d => d.value > 0);

  const trendData = results?.slice(0, 15).map((r, i) => ({
    idx: i + 1,
    score: r.score,
    label: r.title?.slice(0, 30),
  })) || [];

  return (
    <div className="sentiment-panel">
      <div className="sentiment-overview">
        <div className="sentiment-score" style={{ color: SENTIMENT_COLORS[summary.overall] }}>
          {summary.overall?.toUpperCase()}
        </div>
        <div className="sentiment-avg">Avg score: {summary.average_score?.toFixed(3)}</div>
        {summary.trend && (
          <div className={`sentiment-trend trend-${summary.trend}`}>
            {summary.trend === "improving" ? "↑" : summary.trend === "deteriorating" ? "↓" : "→"} {summary.trend}
          </div>
        )}
      </div>

      <div className="sentiment-charts">
        <div className="sent-pie">
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={60}
                dataKey="value" paddingAngle={3}>
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => `${v.toFixed(1)}%`} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {trendData.length > 3 && (
          <div className="sent-trend">
            <ResponsiveContainer width="100%" height={140}>
              <LineChart data={trendData}>
                <XAxis dataKey="idx" tick={{ fontSize: 10 }} />
                <YAxis domain={[-1, 1]} tick={{ fontSize: 10 }} />
                <Tooltip formatter={(v) => v.toFixed(3)} />
                <Line type="monotone" dataKey="score" stroke="#0a84ff" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {summary.top_emotions && Object.keys(summary.top_emotions).length > 0 && (
        <div className="emotions">
          <h5>Dominant Emotions</h5>
          {Object.entries(summary.top_emotions).map(([emotion, strength]) => (
            <div key={emotion} className="emotion-bar">
              <span>{emotion}</span>
              <div className="emo-bar-track">
                <div className="emo-bar-fill" style={{ width: `${Math.min(strength * 100, 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Source Profiles ───────────────────────────────────────────────────────────
function SourceProfiles({ profiles }) {
  if (!profiles || Object.keys(profiles).length === 0) return null;

  return (
    <div className="source-profiles">
      {Object.entries(profiles).map(([domain, profile]) => (
        <div key={domain} className="source-card">
          <div className="source-name">{domain}</div>
          <CredibilityBar score={profile.credibility_score || 50} />
          <div className="source-meta">
            <span className="lean-badge">{profile.lean_label}</span>
            <span className="type-badge">{profile.source_type}</span>
            <span className={`fc-badge fc-${profile.fact_check_rating}`}>{profile.fact_check_rating}</span>
          </div>
          {profile.warnings?.length > 0 && (
            <div className="source-warnings">
              {profile.warnings.map((w, i) => (
                <div key={i} className="source-warning">⚠ {w}</div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Synthesis Panel ───────────────────────────────────────────────────────────
function SynthesisPanel({ synthesis }) {
  if (!synthesis) return null;

  return (
    <div className="synthesis-panel">
      <div className="synthesis-confidence">
        <span>Gemini Confidence:</span>
        <span className={`confidence-badge conf-${synthesis.confidence?.toLowerCase()}`}>
          {synthesis.confidence}
        </span>
      </div>

      {synthesis.executive_summary && (
        <div className="exec-summary">
          <h5>Executive Summary</h5>
          <p>{synthesis.executive_summary}</p>
        </div>
      )}

      {synthesis.key_findings?.length > 0 && (
        <div className="findings">
          <h5>Key Findings</h5>
          {synthesis.key_findings.map((f, i) => (
            <div key={i} className="finding-item">
              <CheckCircle size={12} color="#34c759" /> {f}
            </div>
          ))}
        </div>
      )}

      {synthesis.contradictions?.length > 0 && (
        <div className="contradictions">
          <h5>Contradictions Detected</h5>
          {synthesis.contradictions.map((c, i) => (
            <div key={i} className="contradiction-item">
              <AlertCircle size={12} color="#ff9500" /> {c}
            </div>
          ))}
        </div>
      )}

      {synthesis.narrative_patterns?.length > 0 && (
        <div className="patterns">
          <h5>Narrative Patterns</h5>
          {synthesis.narrative_patterns.map((p, i) => (
            <div key={i} className="pattern-item">
              <Eye size={12} color="#bf5af2" /> {p}
            </div>
          ))}
        </div>
      )}

      {synthesis.analyst_note && (
        <div className="analyst-note">
          <Brain size={14} /> <em>{synthesis.analyst_note}</em>
        </div>
      )}
    </div>
  );
}

// ── Fact Check Panel ──────────────────────────────────────────────────────────
function FactCheckPanel({ results }) {
  if (!results || results.length === 0) return null;

  return (
    <div className="fact-check-panel">
      {results.map((r, i) => (
        <div key={i} className="fc-item">
          <div className="fc-verdict">
            {r.verified === true ? <CheckCircle size={14} color="#34c759" /> :
             r.verified === false ? <XCircle size={14} color="#ff3b30" /> :
             <AlertCircle size={14} color="#ff9500" />}
            <span className="fc-rating">{r.rating || r.plausibility_label || "unknown"}</span>
            {r.fact_checker && <span className="fc-source">via {r.fact_checker}</span>}
          </div>
          <p className="fc-claim">{r.claim}</p>
          {r.red_flags?.map((flag, j) => (
            <div key={j} className="fc-flag">⚑ {flag}</div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ── Progress Stream ───────────────────────────────────────────────────────────
function ProgressStream({ events }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events]);

  return (
    <div className="progress-stream" ref={ref}>
      {events.map((e, i) => (
        <div key={i} className={`stream-event type-${e.type}`}>
          <span className="event-stage">{e.stage || e.type}</span>
          <span className="event-msg">{e.message || JSON.stringify(e).slice(0, 80)}</span>
          {e.count !== undefined && <span className="event-count">+{e.count}</span>}
        </div>
      ))}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [queries, setQueries] = useState([""]);
  const [apiConfig, setApiConfig] = useState({
    gemini_api_key: "",
    finnhub_api_key: "",
    news_api_key: "",
    fact_check_api_key: "",
  });
  const [loading, setLoading] = useState(false);
  const [streamEvents, setStreamEvents] = useState([]);
  const [completedStages, setCompletedStages] = useState([]);
  const [currentStage, setCurrentStage] = useState("");
  const [report, setReport] = useState(null);
  const [activeTab, setActiveTab] = useState("synthesis");
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  const addQuery = () => setQueries([...queries, ""]);
  const removeQuery = (i) => setQueries(queries.filter((_, idx) => idx !== i));
  const updateQuery = (i, val) => {
    const q = [...queries];
    q[i] = val;
    setQueries(q);
  };

  const runAnalysis = useCallback(async () => {
    const validQueries = queries.filter(q => q.trim());
    if (!validQueries.length) { setError("Add at least one query"); return; }
    if (!apiConfig.gemini_api_key) { setError("Gemini API key is required"); return; }

    setLoading(true);
    setError("");
    setReport(null);
    setStreamEvents([]);
    setCompletedStages([]);
    setCurrentStage("planning");

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch(`${API_BASE}/analyze/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          queries: validQueries,
          depth: "standard",
          ...apiConfig,
        }),
        signal: controller.signal,
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            setStreamEvents(prev => [...prev.slice(-50), event]); // Keep last 50

            if (event.type === "stage" && event.stage) {
              setCurrentStage(event.stage);
              setCompletedStages(prev => [...new Set([...prev, event.stage])]);
            }

            if (event.type === "final_report") {
              setReport(event);
              setActiveTab("synthesis");
            }

            if (event.type === "error") {
              setError(event.message);
            }
          } catch {}
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err.message || "Analysis failed. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  }, [queries, apiConfig]);

  const stopAnalysis = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  const tabs = [
    { id: "synthesis", label: "Intelligence", icon: Brain },
    { id: "articles", label: "Articles", icon: FileText },
    { id: "risk", label: "Risk", icon: Shield },
    { id: "sentiment", label: "Sentiment", icon: Activity },
    { id: "sources", label: "Sources", icon: Globe },
    { id: "factcheck", label: "Fact Check", icon: CheckCircle },
    { id: "stream", label: "Live Feed", icon: Radio },
  ];

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <Zap size={22} className="logo-icon" />
            <div>
              <h1>NewsIntel</h1>
              <p>Gemini-Powered Intelligence Platform</p>
            </div>
          </div>
          {report && (
            <div className="header-stats">
              <div className="stat"><span>{report.articles_analyzed}</span><small>articles</small></div>
              <div className="stat"><span>{Object.keys(report.source_profiles || {}).length}</span><small>sources</small></div>
              <RiskBadge level={report.risk?.overall_risk} />
            </div>
          )}
        </div>
      </header>

      {/* Query Panel */}
      <div className="query-panel">
        <div className="query-inner">
          <div className="query-list">
            {queries.map((q, i) => (
              <div key={i} className="query-row">
                <Search size={14} className="query-icon" />
                <input
                  className="query-input"
                  placeholder={`Query ${i + 1} — e.g. "TSLA earnings miss 2025"`}
                  value={q}
                  onChange={(e) => updateQuery(i, e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && runAnalysis()}
                />
                {queries.length > 1 && (
                  <button className="remove-query" onClick={() => removeQuery(i)}>
                    <X size={12} />
                  </button>
                )}
              </div>
            ))}
            <button className="add-query-btn" onClick={addQuery} disabled={queries.length >= 5}>
              <Plus size={14} /> Add query {queries.length >= 5 && "(max 5)"}
            </button>
          </div>

          <ApiConfigPanel config={apiConfig} onChange={setApiConfig} />

          {error && <div className="error-banner"><AlertTriangle size={14} /> {error}</div>}

          <div className="action-row">
            {!loading ? (
              <button className="run-btn" onClick={runAnalysis}>
                <Brain size={16} /> Run Intelligence Analysis
              </button>
            ) : (
              <>
                <button className="stop-btn" onClick={stopAnalysis}>
                  <X size={14} /> Stop
                </button>
                <div className="loading-indicator">
                  <Loader size={14} className="spin" /> Analyzing...
                </div>
              </>
            )}
          </div>

          {(loading || completedStages.length > 0) && (
            <StageIndicator stages={completedStages} currentStage={currentStage} />
          )}
        </div>
      </div>

      {/* Results */}
      {(report || streamEvents.length > 0) && (
        <div className="results-panel">
          <div className="tab-bar">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                className={`tab ${activeTab === id ? "active" : ""}`}
                onClick={() => setActiveTab(id)}
              >
                <Icon size={13} /> {label}
              </button>
            ))}
          </div>

          <div className="tab-content">
            {activeTab === "synthesis" && <SynthesisPanel synthesis={report?.synthesis} />}
            {activeTab === "articles" && (
              <div className="articles-list">
                {report?.articles?.map((a, i) => <ArticleCard key={i} article={a} index={i} />) || (
                  <p className="empty">Articles will appear here after analysis completes.</p>
                )}
              </div>
            )}
            {activeTab === "risk" && <RiskDashboard risk={report?.risk} />}
            {activeTab === "sentiment" && <SentimentPanel sentiment={report?.sentiment} />}
            {activeTab === "sources" && <SourceProfiles profiles={report?.source_profiles} />}
            {activeTab === "factcheck" && <FactCheckPanel results={report?.fact_check} />}
            {activeTab === "stream" && <ProgressStream events={streamEvents} />}
          </div>
        </div>
      )}

      {!report && !loading && streamEvents.length === 0 && (
        <div className="empty-state">
          <Brain size={48} className="empty-icon" />
          <h2>News Intelligence Platform</h2>
          <p>Enter search queries, configure your API keys, and run analysis.<br />
          Gemini orchestrates scraping → sentiment → risk → synthesis.</p>
          <div className="feature-chips">
            {["crawl4ai Scraping", "Gemini AI Synthesis", "Risk Engine", "Sentiment Analysis",
              "Source Credibility", "Fact Checking", "Market Signals"].map(f => (
              <span key={f} className="chip">{f}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
