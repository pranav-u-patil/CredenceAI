import React, { useState } from "react";
import { Routes, Route } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Globe, ShieldCheck, Sparkles, X, LoaderCircle, FileText, Link2, CalendarDays, TriangleAlert } from "lucide-react";
import { GridPattern } from "./components/ui/grid-pattern";
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

function AnalysisCard({ preview, analysis, onReset }) {
  const actions = analysis?.actions || [];
  const evidenceCount = analysis?.evidence_units?.length || 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 18, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 10, scale: 0.985 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="w-full overflow-hidden rounded-[28px] border border-stone-200/80 bg-white/85 shadow-2xl backdrop-blur-xl"
    >
      <div className="border-b border-stone-200 bg-gradient-to-r from-emerald-50 via-white to-cyan-50 px-6 py-5">
        <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-700">
          <ShieldCheck className="h-3.5 w-3.5" />
          Analysis Complete
        </div>
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-stone-900">{preview?.title || "Article analysis"}</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600">{analysis?.explanation || "No explanation returned."}</p>
          </div>
          <div className="rounded-3xl border border-emerald-200 bg-white px-5 py-4 text-right shadow-sm">
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-emerald-600">Credibility</div>
            <div className="mt-1 text-3xl font-semibold text-stone-900">{analysis?.credibility_score ?? "--"}</div>
            <div className="text-sm capitalize text-stone-500">{analysis?.bucket || "unknown"}</div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 border-b border-stone-200 bg-stone-50/80 px-6 py-5 md:grid-cols-3">
        <SummaryTile label="P(true)" value={String(analysis?.p_true ?? "--")} icon={Sparkles} />
        <SummaryTile label="Evidence Units" value={String(evidenceCount)} icon={FileText} />
        <SummaryTile label="Source" value={preview?.domain || "Unknown"} icon={Globe} />
      </div>

      <div className="grid gap-6 px-6 py-5 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Evidence summary</div>
          <div className="max-h-[36vh] overflow-y-auto rounded-2xl border border-stone-200 bg-white px-4 py-4 text-sm leading-7 text-stone-700">
            {(analysis?.evidence_units || []).length > 0 ? (
              (analysis.evidence_units || []).map((unit, index) => (
                <div key={`${unit.id || index}-${index}`} className="border-b border-stone-100 py-3 last:border-b-0">
                  <div className="font-medium text-stone-800">{unit.domain || unit.provenance || "Unknown source"}</div>
                  <div className="mt-1 text-stone-600">{unit.raw_snippet || unit.snippet || "No snippet available."}</div>
                </div>
              ))
            ) : (
              <div>No evidence units were returned.</div>
            )}
          </div>
        </div>

        <div>
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-500">Recommended actions</div>
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
      </div>

      <div className="flex justify-end border-t border-stone-200 bg-stone-50/90 px-6 py-5">
        <Button variant="outline" className="rounded-full border-stone-300 bg-white px-5" onClick={onReset}>
          Analyze Another URL
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

function PromptInputWithActions({ input, setInput, isBusy, onSubmit, isActive }) {
  const handleSubmit = () => {
    if (input.trim()) onSubmit(input);
  };

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
          placeholder="Paste a news article URL to scrape and preview it..."
          className="min-h-[48px]"
        />

        <PromptInputActions className="flex items-center justify-between gap-2 pt-2">
          <div className="px-2 text-xs font-medium text-stone-500">
            Step 1: preview the article. Step 2: choose deeper analysis.
          </div>

          <PromptInputAction tooltip={isBusy ? "Working" : "Preview article"}>
            <Button
              variant="default"
              className="rounded-full bg-stone-900 px-4 text-white hover:bg-stone-800"
              onClick={handleSubmit}
              disabled={isBusy}
            >
              {isBusy ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Globe className="mr-2 h-4 w-4" />}
              Fetch Article
            </Button>
          </PromptInputAction>
        </PromptInputActions>
      </PromptInput>
    </motion.div>
  );
}

function App() {
  const [input, setInput] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");
  const [previewData, setPreviewData] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);

  const isActive = Boolean(previewData || analysisData || error || isBusy);

  const handlePreview = async (value) => {
    const url = (value || "").trim();
    if (!url) return;

    setIsBusy(true);
    setError("");
    setAnalysisData(null);

    try {
      const response = await fetch(`${API_BASE_URL}/preview/article`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data?.detail || `Preview failed with status ${response.status}`);
      }
      setPreviewData(data);
    } catch (err) {
      setPreviewData(null);
      setError(err?.message || "Unable to preview this article.");
    } finally {
      setIsBusy(false);
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
    setError("");
    setIsBusy(false);
  };

  return (
    <div className="min-h-screen overflow-hidden bg-[#f6f0e8] text-stone-900">
      <Header />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(245,158,11,0.18),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(16,185,129,0.16),_transparent_32%),linear-gradient(180deg,_rgba(255,255,255,0.8),_rgba(246,240,232,0.95))]" />

      <GridPattern
        squares={[[4, 4], [5, 1], [8, 2], [5, 3], [5, 5], [10, 10], [12, 15], [15, 10], [10, 15]]}
        className={cn("[mask-image:radial-gradient(900px_circle_at_center,white,transparent)]", "inset-x-0 inset-y-[-30%] h-[200%] skew-y-12 opacity-35")}
      />

      <motion.main
        className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col items-center px-4 py-10"
        animate={{
          justifyContent: isActive ? "flex-start" : "center",
        }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className={cn("w-full text-center transition-all duration-500", isActive ? "mb-8" : "mb-14")}>
          {/* <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-stone-300/80 bg-white/80 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-stone-600 shadow-sm">
            <Sparkles className="h-3.5 w-3.5 text-amber-600" />
            URL-first newsroom workflow
          </div> */}
          <h1 className="mx-auto max-w-4xl font-serif text-5xl font-semibold tracking-tight text-stone-900 sm:text-6xl">
            Paste a news link, preview the story, then decide if it deserves deeper verification.
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg leading-8 text-stone-600">
            The frontend now scrapes and displays the article first, then lets the user continue with <span className="font-semibold text-stone-800">More Analysis</span> or back out with <span className="font-semibold text-stone-800">Cancel</span>.
          </p>
        </div>

        <div className="w-full max-w-3xl">
          <PromptInputWithActions
            input={input}
            setInput={setInput}
            isBusy={isBusy}
            onSubmit={handlePreview}
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
    </div>
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
