import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Globe, ShieldCheck, Sparkles, X, LoaderCircle, FileText, Link2, CalendarDays, TriangleAlert } from "lucide-react";
import { GradientBlurBgGrid } from "./components/ui/gradient-blur-bg";
import EvidenceGraph from "./components/ui/evidence-graph";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "./components/ui/prompt-input";
import { Button } from "./components/ui/button";
import { cn } from "./lib/utils";
import { Header } from "./components/ui/header";
import Finance from "./Pages/Finance.jsx";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

function SummaryTile({ label, value, icon: Icon }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white/75 px-4 py-3 shadow-sm">
      <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="text-sm font-medium text-stone-800">{value}</div>
    </div>
  );
}

function PreviewCard({ preview, claimText, onAnalyze, onCancel, isAnalyzing }) {
  const published = preview?.published_at ? new Date(preview.published_at).toLocaleString() : "Unknown";

  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.985 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="w-full overflow-hidden rounded-[28px] border border-stone-200/80 bg-white/85 shadow-2xl backdrop-blur-xl"
    >
      <div className="border-b border-stone-200 bg-gradient-to-r from-amber-50 via-white to-emerald-50 px-6 py-5">
        <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-amber-700">
          <Globe className="h-3.5 w-3.5" />
          Article Preview
        </div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900">
          {preview?.title || "Untitled article"}
        </h2>
        <p className="mt-3 text-sm leading-6 text-stone-600">{preview?.summary || preview?.snippet || "No summary available."}</p>
      </div>

      <div className="grid gap-3 border-b border-stone-200 bg-stone-50/80 px-6 py-5 md:grid-cols-3">
        <SummaryTile label="Source" value={preview?.domain || "Unknown"} icon={Link2} />
        <SummaryTile label="Published" value={published} icon={CalendarDays} />
        <SummaryTile label="Content Size" value={`${preview?.length || 0} chars`} icon={FileText} />
      </div>

      <div className="px-6 py-5">
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Prepared claim text</div>
        <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3 text-sm leading-6 text-stone-700">
          {claimText}
        </div>
      </div>

      <div className="px-6 pb-5">
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Scraped content</div>
        <div className="max-h-[34vh] overflow-y-auto rounded-2xl border border-stone-200 bg-white px-4 py-4 text-sm leading-7 text-stone-700">
          {preview?.content || preview?.snippet || "No readable content extracted."}
        </div>
      </div>

      <div className="flex flex-col gap-3 border-t border-stone-200 bg-stone-50/90 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-stone-500">
          Review the scraped article first, then decide if you want deeper verification.
        </div>
        <div className="flex gap-3">
          <Button
            variant="outline"
            className="rounded-full border-stone-300 bg-white px-5"
            onClick={onCancel}
            disabled={isAnalyzing}
          >
            Cancel
          </Button>
          <Button
            className="rounded-full bg-stone-900 px-5 text-white hover:bg-stone-800"
            onClick={onAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            More Analysis
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

function CredibilityRing({ score, bucket }) {
  const radius = 52;
  const stroke = 8;
  const normalizedRadius = radius - stroke / 2;
  const circumference = normalizedRadius * 2 * Math.PI;
  const safeScore = Math.max(0, Math.min(100, score || 0));
  const offset = circumference - (safeScore / 100) * circumference;

  const colorMap = {
    verified: "#10b981",
    likely_true: "#22d3ee",
    uncertain: "#f59e0b",
    likely_false: "#f97316",
    false: "#ef4444",
  };
  const ringColor = colorMap[bucket] || "#6366f1";

  return (
    <div className="flex flex-col items-center justify-center">
      <svg height={radius * 2} width={radius * 2}>
        <circle
          stroke="#e5e7eb"
          fill="transparent"
          strokeWidth={stroke}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
        />
        <circle
          stroke={ringColor}
          fill="transparent"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          r={normalizedRadius}
          cx={radius}
          cy={radius}
          style={{
            transition: "stroke-dashoffset 1s ease-out",
            transform: "rotate(-90deg)",
            transformOrigin: "50% 50%",
          }}
        />
        <text
          x="50%"
          y="46%"
          textAnchor="middle"
          dominantBaseline="central"
          className="text-2xl font-bold"
          fill="#1c1917"
          style={{ fontSize: "22px", fontWeight: 700 }}
        >
          {safeScore}
        </text>
        <text
          x="50%"
          y="64%"
          textAnchor="middle"
          dominantBaseline="central"
          fill="#78716c"
          style={{ fontSize: "10px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em" }}
        >
          {(bucket || "unknown").replaceAll("_", " ")}
        </text>
      </svg>
    </div>
  );
}

function AnalysisCard({ preview, analysis, onReset }) {
  const actions = analysis?.actions || [];
  const evidenceCount = analysis?.evidence_units?.length || 0;
  const meta = analysis?.meta || {};

  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.985 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="w-full overflow-hidden rounded-[28px] border border-stone-200/80 bg-white/85 shadow-2xl backdrop-blur-xl"
    >
      {/* ── Header: Title + Credibility Ring side by side ─────── */}
      <div className="border-b border-stone-200 bg-gradient-to-r from-emerald-50 via-white to-cyan-50 px-6 py-5">
        <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-700">
          <ShieldCheck className="h-3.5 w-3.5" />
          Analysis Complete
        </div>
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div className="flex-1">
            <h2 className="text-2xl font-semibold tracking-tight text-stone-900">{preview?.title || "Article analysis"}</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600 max-w-xl">{analysis?.explanation || "No explanation returned."}</p>
          </div>
          <CredibilityRing score={analysis?.credibility_score} bucket={analysis?.bucket} />
        </div>
      </div>

      {/* ── Summary Stats ────────────────────────────────────── */}
      <div className="grid gap-3 border-b border-stone-200 bg-stone-50/80 px-6 py-5 md:grid-cols-4">
        <SummaryTile label="P(true)" value={analysis?.p_true != null ? Number(analysis.p_true).toFixed(3) : "--"} icon={Sparkles} />
        <SummaryTile label="Evidence Units" value={String(evidenceCount)} icon={FileText} />
        <SummaryTile label="Source" value={preview?.domain || "Direct claim"} icon={Globe} />
        <SummaryTile
          label="Confidence Interval"
          value={analysis?.confidence_interval
            ? `[${analysis.confidence_interval[0]?.toFixed(2)}, ${analysis.confidence_interval[1]?.toFixed(2)}]`
            : "--"}
          icon={ShieldCheck}
        />
      </div>

      {/* ── Evidence + Actions side by side ───────────────────── */}
      <div className="grid gap-6 px-6 py-5 lg:grid-cols-[1.2fr_0.8fr]">
        {/* Evidence units list */}
        <div className="flex flex-col h-full">
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Evidence Units</div>
          <div className="max-h-[55vh] flex-1 overflow-y-auto rounded-3xl border border-stone-200/60 bg-stone-50/50 p-4 space-y-4 shadow-inner">
            {evidenceCount > 0 ? (
              (analysis.evidence_units || []).map((unit, index) => {
                // Ensure similarity is a real number
                const simScore = typeof unit.similarity === 'number' ? (unit.similarity * 100).toFixed(1) : null;
                const srcInitial = (unit.domain || unit.provenance || "?").charAt(0).toUpperCase();

                return (
                  <div key={`${unit.id || index}-${index}`} className="group relative rounded-2xl border border-stone-200/80 bg-white p-5 shadow-sm transition-all hover:shadow-md hover:border-violet-200">
                    <div className="flex items-start justify-between gap-4">
                      
                      <div className="flex items-center gap-3 overflow-hidden">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-stone-100 to-stone-200 text-xs font-bold text-stone-600 shadow-sm border border-stone-200 group-hover:from-violet-100 group-hover:to-indigo-50 group-hover:text-violet-700 transition-colors">
                          {srcInitial}
                        </div>
                        <div className="flex flex-col">
                          <div className="truncate text-sm font-semibold tracking-tight text-stone-800">
                            {unit.domain || unit.provenance || "Unknown source"}
                          </div>
                          {unit.url && (
                            <a href={unit.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 max-w-[200px] sm:max-w-xs truncate text-[11px] text-stone-400 hover:text-indigo-600 transition-colors">
                              {unit.url.replace(/^https?:\/\//, '')} <Link2 className="h-3 w-3" />
                            </a>
                          )}
                        </div>
                      </div>

                      {unit.polarity && (
                        <span className={cn(
                          "shrink-0 rounded-full px-3 py-1 text-[10px] font-extrabold uppercase tracking-widest",
                          unit.polarity === "support" ? "bg-emerald-100/80 text-emerald-700" :
                          unit.polarity === "contradict" ? "bg-red-100/80 text-red-700" :
                          "bg-stone-100 text-stone-600"
                        )}>
                          {unit.polarity}
                        </span>
                      )}
                    </div>
                    
                    <div className="relative mt-4 pl-4 border-l-2 border-stone-200 group-hover:border-violet-300 transition-colors">
                      <p className="text-[13px] leading-relaxed text-stone-600 italic line-clamp-3">
                        "{unit.raw_snippet || unit.snippet || "No snippet available."}"
                      </p>
                    </div>
                    
                    {simScore && (
                      <div className="mt-4 flex items-center justify-between border-t border-stone-100 pt-3 text-[11px] font-semibold text-stone-400">
                        <div className="flex items-center gap-1.5 uppercase tracking-widest text-stone-400">
                          <TriangleAlert className="h-3.5 w-3.5 group-hover:text-amber-500 transition-colors" />
                          Similarity Score
                        </div>
                        <span className="rounded-md bg-stone-100 px-2 py-0.5 text-stone-600 font-mono group-hover:bg-amber-50 group-hover:text-amber-700 transition-colors">
                          {simScore}%
                        </span>
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="flex h-40 flex-col items-center justify-center text-sm text-stone-400">
                <FileText className="mb-2 h-6 w-6 opacity-20" />
                No evidence units were returned.
              </div>
            )}
          </div>
        </div>

        {/* Actions + Pipeline metadata */}
        <div className="space-y-5">
          <div>
            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Recommended Actions</div>
            <div className="rounded-2xl border border-stone-200 bg-white p-4">
              {actions.length > 0 ? (
                <div className="space-y-3">
                  {actions.map((action, index) => (
                    <div key={`${action.type}-${action.reason}-${index}`} className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-3">
                      <div className="font-medium capitalize text-stone-800">{action.type?.replaceAll("_", " ")}</div>
                      <div className="mt-1 text-sm text-stone-600">{action.reason?.replaceAll("_", " ")}</div>
                      {action.detail ? <div className="mt-1 text-xs text-stone-500">{action.detail}</div> : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-stone-600">No follow-up actions returned.</div>
              )}
            </div>
          </div>

          {/* Pipeline metadata */}
          <div>
            <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Pipeline Info</div>
            <div className="rounded-2xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600 space-y-1">
              <div className="flex justify-between"><span>Searches</span><span className="font-medium text-stone-800">{meta.searches_performed ?? "—"}</span></div>
              <div className="flex justify-between"><span>Retries</span><span className="font-medium text-stone-800">{meta.retries ?? 0}</span></div>
              <div className="flex justify-between"><span>Elapsed</span><span className="font-medium text-stone-800">{meta.elapsed_ms ? `${meta.elapsed_ms}ms` : "—"}</span></div>
              {analysis?.risk_proxy != null && (
                <div className="flex justify-between"><span>Risk Proxy</span><span className="font-medium text-stone-800">{analysis.risk_proxy}</span></div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Evidence Graph ────────────────────────────────────── */}
      <div className="border-t border-stone-200 px-6 py-5">
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Evidence Graph</div>
        <EvidenceGraph analysis={analysis} />
      </div>

      {/* ── Raw JSON Output ─────────────────────────────────────
      <div className="border-t border-stone-200 px-6 py-5">
        <details className="group">
          <summary className="cursor-pointer mb-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500 hover:text-stone-700 list-none flex items-center justify-between">
            <span>Raw JSON Data</span>
            <span className="text-stone-400 group-open:rotate-180 transition-transform">▼</span>
          </summary>
          <div className="mt-3 max-h-96 overflow-auto rounded-xl bg-stone-900 p-4 text-xs text-green-400 shadow-inner">
            <pre className="font-mono whitespace-pre-wrap word-break">
              {JSON.stringify(analysis, null, 2)}
            </pre>
          </div>
        </details>
      </div> */}

      {/* ── Footer ────────────────────────────────────────────── */}
      <div className="flex justify-end border-t border-stone-200 bg-stone-50/90 px-6 py-5">
        <Button variant="outline" className="rounded-full border-stone-300 bg-white px-5" onClick={onReset}>
          Analyze Another
        </Button>
      </div>
    </motion.div>
  );
}

function ErrorCard({ message, onDismiss }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="w-full rounded-[28px] border border-red-200 bg-white/90 px-6 py-5 shadow-2xl"
    >
      <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-red-700">
        <TriangleAlert className="h-3.5 w-3.5" />
        Request Failed
      </div>
      <div className="text-sm leading-6 text-stone-700">{message}</div>
      <div className="mt-4 flex justify-end">
        <Button variant="outline" className="rounded-full border-stone-300 bg-white px-5" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </motion.div>
  );
}

function isUrl(str) {
  try {
    const u = new URL(str.startsWith("http") ? str : `https://${str}`);
    return u.hostname.includes(".");
  } catch { return false; }
}

function PromptInputWithActions({ input, setInput, isBusy, onSubmit, isActive }) {
  const handleSubmit = () => {
    if (input.trim()) onSubmit(input);
  };

  const inputIsUrl = isUrl(input.trim());

  return (
    <motion.div
      animate={{ maxWidth: isActive ? "940px" : "680px" }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="w-full"
    >
      <PromptInput
        value={input}
        onValueChange={setInput}
        isLoading={isBusy}
        onSubmit={handleSubmit}
        className={cn("w-full rounded-[28px] border border-stone-200 bg-white/90 p-2 shadow-xl transition-all duration-500")}
      >
        <PromptInputTextarea
          placeholder="Paste a URL or type a claim to verify…"
          className="min-h-[48px]"
        />

        <PromptInputActions className="flex items-center justify-between gap-2 pt-2">
          <div className="px-2 text-xs font-medium text-stone-500">
            {inputIsUrl
              ? "URL detected — we'll scrape and preview the article."
              : "Text detected — we'll run a direct claim analysis."}
          </div>

          <PromptInputAction tooltip={isBusy ? "Working" : (inputIsUrl ? "Fetch article" : "Analyze claim")}>
            <Button
              variant="default"
              className="rounded-full bg-stone-900 px-4 text-white hover:bg-stone-800"
              onClick={handleSubmit}
              disabled={isBusy}
            >
              {isBusy ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : (
                inputIsUrl ? <Globe className="mr-2 h-4 w-4" /> : <ShieldCheck className="mr-2 h-4 w-4" />
              )}
              {inputIsUrl ? "Fetch Article" : "Verify Claim"}
            </Button>
          </PromptInputAction>
        </PromptInputActions>
      </PromptInput>
    </motion.div>
  );
}

/* ─── Text Claim Result Card ──────────────────────────────────────── */
function TextClaimCard({ claimText, data, onReset }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.985 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="w-full overflow-hidden rounded-[28px] border border-stone-200/80 bg-white/85 shadow-2xl backdrop-blur-xl"
    >
      {/* Header */}
      <div className="border-b border-stone-200 bg-gradient-to-r from-violet-50 via-white to-indigo-50 px-6 py-5">
        <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-violet-700">
          <ShieldCheck className="h-3.5 w-3.5" />
          Claim Submitted
        </div>
        <h2 className="text-2xl font-semibold tracking-tight text-stone-900">
          Verification Queued
        </h2>
        <p className="mt-2 text-sm leading-6 text-stone-600">
          Your claim has been submitted for analysis. The agent pipeline is running in the background.
        </p>
      </div>

      {/* Claim Text */}
      <div className="px-6 py-5 border-b border-stone-200 bg-stone-50/80">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Claim Text</div>
        <div className="rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm leading-6 text-stone-700 italic">
          "{claimText}"
        </div>
      </div>

      {/* Status */}
      <div className="px-6 py-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-stone-200 bg-white/75 px-4 py-3 shadow-sm">
            <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">
              <FileText className="h-3.5 w-3.5" />
              Claim ID
            </div>
            <div className="text-sm font-medium text-stone-800 font-mono">{data?.claim_id || "—"}</div>
          </div>
          <div className="rounded-2xl border border-emerald-100 bg-emerald-50/50 px-4 py-3 shadow-sm">
            <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-600">
              <Sparkles className="h-3.5 w-3.5" />
              Status
            </div>
            <div className="text-sm font-semibold text-emerald-700 capitalize">{data?.status || "accepted"}</div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="flex flex-col gap-3 border-t border-stone-200 bg-stone-50/90 px-6 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-stone-500">
          The agent is processing this claim. Full results will be available once the pipeline completes.
        </div>
        <Button variant="outline" className="rounded-full border-stone-300 bg-white px-5" onClick={onReset}>
          Submit Another
        </Button>
      </div>
    </motion.div>
  );
}

function App() {
  const [input, setInput] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");
  const [previewData, setPreviewData] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [textClaimData, setTextClaimData] = useState(null);

  const isActive = Boolean(previewData || analysisData || textClaimData || error || isBusy);

  const handleSubmit = async (value) => {
    const trimmed = (value || "").trim();
    if (!trimmed) return;

    setIsBusy(true);
    setError("");
    setAnalysisData(null);
    setTextClaimData(null);
    setPreviewData(null);

    if (isUrl(trimmed)) {
      // ─── URL flow: scrape and preview ───
      try {
        const response = await fetch(`${API_BASE_URL}/preview/article`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: trimmed }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data?.detail || `Preview failed with status ${response.status}`);
        setPreviewData(data);
      } catch (err) {
        setError(err?.message || "Unable to preview this article.");
      } finally {
        setIsBusy(false);
      }
    } else {
      // ─── Text flow: run full agent pipeline via /analyze/claim ───
      try {
        const payload = {
          claim_id: `claim_${Date.now()}`,
          claim_text: trimmed,
          timestamp: new Date().toISOString(),
          initial_urls: [],
          entities: [],
          context: {},
          source_meta: {},
        };

        const response = await fetch(`${API_BASE_URL}/analyze/claim`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data?.detail || `Analysis failed with status ${response.status}`);
        // Shape it the same way as URL analysis for the AnalysisCard
        setAnalysisData({
          preview: { title: trimmed, domain: "Direct claim", summary: trimmed },
          analysis: data.analysis,
        });
        setInput("");
      } catch (err) {
        setError(err?.message || "Unable to analyze this claim.");
      } finally {
        setIsBusy(false);
      }
    }
  };

  const handleAnalyze = async () => {
    if (!previewData?.preview?.url) return;

    setIsBusy(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/analyze/article`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: previewData.preview.url,
          claim_text: previewData.claim_text,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || `Analysis failed with status ${response.status}`);
      }
      setAnalysisData(data);
    } catch (err) {
      setError(err?.message || "Unable to complete deeper analysis.");
    } finally {
      setIsBusy(false);
    }
  };

  const resetFlow = () => {
    setPreviewData(null);
    setAnalysisData(null);
    setTextClaimData(null);
    setError("");
    setIsBusy(false);
  };

  const geminiCap = (value, max = 100) => {
  const v = Number(value) || 0;
  return v > max ? max - (v - max) : v;
};

  return (
    <GradientBlurBgGrid className="overflow-hidden text-stone-900">
      <Header /><br />

      <motion.main
        className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col items-center px-4 py-10"
        animate={{
          justifyContent: isActive ? "flex-start" : "center",
        }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className={cn("w-full text-center transition-all duration-500", isActive ? "mb-8" : "mb-14")}>
          <h1 className="mx-auto max-w-4xl font-serif text-5xl font-semibold tracking-tight text-stone-900 sm:text-6xl">
            Verify any claim or news article with AI-powered intelligence.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-8 text-stone-600">
            Paste a <span className="font-semibold text-stone-800">URL</span> to scrape and preview an article, or type a <span className="font-semibold text-stone-800">claim</span> directly for instant verification.
          </p>
        </div>

        <div className="w-full max-w-3xl">
          <PromptInputWithActions
            input={input}
            setInput={setInput}
            isBusy={isBusy}
            onSubmit={handleSubmit}
            isActive={isActive}
          />
        </div>

        <div className="mt-8 w-full max-w-5xl">
          <AnimatePresence mode="wait">
            {error ? (
              <ErrorCard key="error" message={error} onDismiss={() => setError("")} />
            ) : analysisData ? (
              <AnalysisCard
                key="analysis"
                preview={analysisData.preview}
                analysis={analysisData.analysis}
                onReset={resetFlow}
              />
            ) : textClaimData ? (
              <TextClaimCard
                key="text-claim"
                claimText={textClaimData.claim_text}
                data={textClaimData}
                onReset={resetFlow}
              />
            ) : previewData ? (
              <PreviewCard
                key="preview"
                preview={previewData.preview}
                claimText={previewData.claim_text}
                onAnalyze={handleAnalyze}
                onCancel={resetFlow}
                isAnalyzing={isBusy}
              />
            ) : null}
          </AnimatePresence>
        </div>

        <AnimatePresence>
          {isActive && (
            <motion.button
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.25 }}
              onClick={resetFlow}
              className="fixed right-5 top-5 z-20 rounded-full border border-stone-300 bg-white/90 p-3 text-stone-600 shadow-lg transition hover:bg-white hover:text-stone-900"
            >
              <X className="h-4 w-4" />
            </motion.button>
          )}
        </AnimatePresence>
      </motion.main>
    </GradientBlurBgGrid>
  );
}

function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/finance" element={<Finance />} />
    </Routes>
  );
}

export default AppRouter;
