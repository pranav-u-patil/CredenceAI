import React, { useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { GridPattern } from "./components/ui/grid-pattern";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputActions,
  PromptInputAction,
} from "./components/ui/prompt-input";
import { Button } from "./components/ui/button";
import { ArrowUp, Paperclip, Square, X, ShieldCheck, GitFork } from "lucide-react";
import { cn } from "./lib/utils";
import EvidenceGraph from "./components/ui/evidence-graph";

/* ── Skeleton bars ────────────────────────────────── */
const skeletonBars = [
  { width: "90%",  delay: 0    },
  { width: "75%",  delay: 0.07 },
  { width: "85%",  delay: 0.14 },
  { width: "60%",  delay: 0.21 },
  { width: "80%",  delay: 0.28 },
];

function SkeletonContent() {
  return (
    <div className="flex flex-col gap-4 w-full">
      <div className="flex items-center gap-2 mb-1">
        <div className="h-4 w-4 rounded-full bg-gray-200 animate-pulse" />
        <div className="h-3 w-32 rounded-full bg-gray-200 animate-pulse" />
      </div>
      {skeletonBars.map((bar, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, scaleX: 0.6 }}
          animate={{ opacity: 1, scaleX: 1 }}
          transition={{ delay: bar.delay, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
          style={{ width: bar.width, height: "18px" }}
          className="rounded-full bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 animate-shimmer origin-left"
        />
      ))}
      <div className="flex flex-col gap-3 mt-2">
        {[{ w: "70%", d: 0.35 }, { w: "55%", d: 0.42 }].map((b, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, scaleX: 0.6 }}
            animate={{ opacity: 1, scaleX: 1 }}
            transition={{ delay: b.d, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            style={{ width: b.w, height: "18px" }}
            className="rounded-full bg-gradient-to-r from-gray-200 via-gray-100 to-gray-200 animate-shimmer origin-left"
          />
        ))}
      </div>
    </div>
  );
}

function ResultContent({ result }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="flex flex-col gap-5 w-full"
    >
      {/* ─ Summary section ─ */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheck className="h-4 w-4 text-green-500 flex-shrink-0" />
          <span className="text-xs font-semibold tracking-widest uppercase text-green-600">
            Analysis complete
          </span>
        </div>
        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{result}</p>
      </div>

      {/* ─ Evidence Graph section ─ */}
      <div>
        <div className="flex items-center gap-2 mb-3 pt-3 border-t border-gray-100">
          <GitFork className="h-4 w-4 text-indigo-500 flex-shrink-0" />
          <span className="text-xs font-semibold tracking-widest uppercase text-indigo-600">
            Evidence Graph
          </span>
        </div>
        <EvidenceGraph />
      </div>
    </motion.div>
  );
}

/* ── Floating results panel ───────────────────────── */
function ResultsPanel({ isLoading, result, onClose }) {
  return (
    <AnimatePresence>
      {(isLoading || result) && (
        <motion.div
          key="results-panel"
          initial={{ opacity: 0, scale: 0.97, y: 16 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 8 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="absolute z-20 left-1/2 -translate-x-1/2"
          style={{ top: "4%", width: "min(1100px, 95vw)" }}
        >
          <div
            className="relative rounded-2xl border border-gray-200/80 shadow-2xl overflow-hidden"
            style={{
              background: "rgba(255,255,255,0.78)",
              backdropFilter: "blur(22px)",
              WebkitBackdropFilter: "blur(22px)",
            }}
          >
            <div className="h-[2px] w-full bg-gradient-to-r from-gray-300 via-gray-900 to-gray-300 opacity-20" />
            <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-gray-100/60">
              <div className="flex items-center gap-2">
                {isLoading ? (
                  <>
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gray-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-gray-500" />
                    </span>
                    <span className="text-xs font-semibold tracking-widest uppercase text-gray-400">
                      Running analysis…
                    </span>
                  </>
                ) : (
                  <span className="text-xs font-semibold tracking-widest uppercase text-gray-500">
                    Intelligence Report
                  </span>
                )}
              </div>
              {!isLoading && (
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600 transition-colors rounded-full p-1 hover:bg-gray-100"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="px-5 py-5 min-h-[180px] max-h-[75vh] overflow-y-auto">
              <AnimatePresence mode="wait">
                {isLoading ? (
                  <motion.div
                    key="skeleton"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <SkeletonContent />
                  </motion.div>
                ) : (
                  <ResultContent key="result" result={result} />
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/* ── Prompt input ─────────────────────────────────── */
function PromptInputWithActions({ input, setInput, isLoading, onSubmit, isActive }) {
  const [files, setFiles] = useState([]);
  const uploadInputRef = useRef(null);

  const handleSubmit = () => {
    if (input.trim() || files.length > 0) onSubmit(input);
  };

  const handleFileChange = (e) => {
    if (e.target.files) setFiles((p) => [...p, ...Array.from(e.target.files)]);
  };

  const handleRemoveFile = (idx) => {
    setFiles((p) => p.filter((_, i) => i !== idx));
    if (uploadInputRef?.current) uploadInputRef.current.value = "";
  };

  return (
    /* Animate width (shrink) and scale on submit */
    <motion.div
      animate={{
        maxWidth: isActive ? "940px" : "620px",
      }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="w-full"
    >
      <PromptInput
        value={input}
        onValueChange={setInput}
        isLoading={isLoading}
        onSubmit={handleSubmit}
        className={cn(
          "w-full shadow-xl transition-all duration-500",
          isActive ? "rounded-2xl p-1.5" : "rounded-3xl p-2"
        )}
      >
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 pb-2">
            {files.map((file, idx) => (
              <div
                key={idx}
                className="bg-gray-100 flex items-center gap-2 rounded-lg px-2 py-1 text-xs text-gray-700"
              >
                <Paperclip className="h-3 w-3" />
                <span className="max-w-[100px] truncate">{file.name}</span>
                <button
                  onClick={() => handleRemoveFile(idx)}
                  className="hover:bg-gray-200 rounded-full p-0.5"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        <PromptInputTextarea 
          placeholder="Ask me anything..." 
          className={cn(
            "transition-all duration-500",
            isActive ? "min-h-[32px] text-sm py-1" : "min-h-[44px]"
          )}
        />

        <PromptInputActions className={cn(
          "flex items-center justify-between gap-2",
          isActive ? "pt-1" : "pt-2"
        )}>
          <PromptInputAction tooltip="Attach files">
            <label
              htmlFor="file-upload"
              className="hover:bg-gray-100 flex h-8 w-8 cursor-pointer items-center justify-center rounded-2xl transition-colors"
            >
              <input
                type="file"
                multiple
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
                ref={uploadInputRef}
              />
              <Paperclip className="text-gray-500 h-5 w-5" />
            </label>
          </PromptInputAction>

          <PromptInputAction tooltip={isLoading ? "Stop generation" : "Send message"}>
            <Button
              variant="default"
              size="icon"
              className="h-8 w-8 rounded-full"
              onClick={handleSubmit}
            >
              {isLoading ? (
                <Square className="h-4 w-4 fill-current" />
              ) : (
                <ArrowUp className="h-4 w-4" />
              )}
            </Button>
          </PromptInputAction>
        </PromptInputActions>
      </PromptInput>
    </motion.div>
  );
}

/* ── App ─────────────────────────────────────────── */
function App() {
  const [input, setInput]         = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult]       = useState(null);
  const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

  const isActive = isLoading || result !== null;

  const handleSubmit = async (query) => {
    const trimmedQuery = (query || "").trim();
    if (!trimmedQuery) return;

    setResult(null);
    setIsLoading(true);

    try {
      const payload = {
        claim_id: `claim_${Date.now()}`,
        claim_text: trimmedQuery,
        timestamp: new Date().toISOString(),
        initial_urls: [],
        entities: [],
        context: {},
        source_meta: {},
      };

      const response = await fetch(`${API_BASE_URL}/ingest/scraper`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data?.detail || `Request failed with status ${response.status}`);
      }

      setResult(
        `Request accepted.\n\nClaim ID: ${data?.claim_id || payload.claim_id}\nStatus: ${data?.status || "accepted"}`
      );
      setInput("");
    } catch (error) {
      setResult(`Backend connection failed:\n\n${error?.message || "Unknown error"}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClosePanel = () => {
    setResult(null);
    setIsLoading(false);
  };

  return (
    <div className="min-h-screen bg-white flex flex-col relative overflow-hidden">
      <GridPattern
        squares={[
          [4, 4], [5, 1], [8, 2], [5, 3], [5, 5],
          [10, 10], [12, 15], [15, 10], [10, 15],
        ]}
        className={cn(
          "[mask-image:radial-gradient(800px_circle_at_center,white,transparent)]",
          "inset-x-0 inset-y-[-30%] h-[200%] skew-y-12"
        )}
      />

      {/* ─ Main layout: transitions from center to bottom ─ */}
      <motion.main
        className="relative z-10 w-full flex flex-col items-center px-4 max-w-4xl mx-auto"
        animate={{
          justifyContent: isActive ? "flex-end" : "center",
          paddingBottom: isActive ? "40px" : "0px",
          marginTop: isActive ? "auto" : "auto",
          height: "100vh",
        }}
        style={{ display: "flex" }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        {/* ─ Hero: fades away when isActive ─ */}
        <AnimatePresence>
          {!isActive && (
            <motion.div
              key="hero"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12, transition: { duration: 0.25 } }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="mb-12 text-center"
            >
              <h1 className="text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl mb-6 bg-clip-text text-transparent bg-gradient-to-br from-gray-900 via-gray-800 to-gray-500">
                Crisis Intelligence
              </h1>
              <p className="text-xl text-gray-600 max-w-2xl mx-auto leading-relaxed">
                Real-time verification &amp; risk analysis engine. <br />
                Ask a question or submit a claim to begin analysis.
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ─ Input: shrinks + moves down on submit ─ */}
        <div className="w-full flex justify-center">
          <PromptInputWithActions
            input={input}
            setInput={setInput}
            isLoading={isLoading}
            onSubmit={handleSubmit}
            isActive={isActive}
          />
        </div>
      </motion.main>

      {/* ─ Floating glass results panel ─ */}
      <ResultsPanel
        isLoading={isLoading}
        result={result}
        onClose={handleClosePanel}
      />
    </div>
  );
}

export default App;
