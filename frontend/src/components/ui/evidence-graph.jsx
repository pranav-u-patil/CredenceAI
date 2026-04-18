import React, { useCallback, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MarkerType,
  Handle,
  Position,
} from "reactflow";
import "reactflow/dist/style.css";
import { AnimatePresence, motion } from "framer-motion";
import { Maximize2, Minimize2 } from "lucide-react";
import { cn } from "../../lib/utils";

/* ─────────────────────────────────────────────────────
 *  Custom Node Components
 * ─────────────────────────────────────────────────── */

function ClaimNode({ data }) {
  return (
    <div className="relative group" style={{ minWidth: 200, maxWidth: 270 }}>
      {/* Glow ring */}
      <div
        className="absolute -inset-[3px] rounded-2xl opacity-60 blur-sm"
        style={{
          background: `linear-gradient(135deg, ${data.glowFrom || "#818cf8"}, ${data.glowTo || "#6366f1"})`,
        }}
      />
      <div
        className="relative rounded-2xl px-5 py-4"
        style={{
          background: data.bg || "linear-gradient(135deg, #4f46e5, #6366f1)",
          color: "#fff",
          boxShadow: "0 8px 32px rgba(79,70,229,0.25)",
        }}
      >
        <div className="text-[10px] font-bold tracking-widest uppercase opacity-70 mb-2">
          {data.tag || "CLAIM"}
        </div>
        <p className="text-sm font-semibold leading-snug">{data.label}</p>
        {data.confidence != null && (
          <div className="mt-3 flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-white/20 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${data.confidence}%`, background: "rgba(255,255,255,0.8)" }}
              />
            </div>
            <span className="text-[10px] font-bold opacity-80">{data.confidence}%</span>
          </div>
        )}
      </div>
      <Handle type="target" position={Position.Left}   className="!w-2 !h-2 !bg-indigo-300 !border-indigo-500" />
      <Handle type="source" position={Position.Right}  className="!w-2 !h-2 !bg-indigo-300 !border-indigo-500" />
      <Handle type="target" position={Position.Top}    id="top"    className="!w-2 !h-2 !bg-indigo-300 !border-indigo-500" />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!w-2 !h-2 !bg-indigo-300 !border-indigo-500" />
    </div>
  );
}

function EvidenceNode({ data }) {
  const palette = {
    supports:    { border: "#10b981", bg: "#ecfdf5", text: "#065f46", icon: "✓", tagBg: "#d1fae5" },
    contradicts: { border: "#ef4444", bg: "#fef2f2", text: "#991b1b", icon: "✕", tagBg: "#fee2e2" },
    neutral:     { border: "#6b7280", bg: "#f9fafb", text: "#374151", icon: "─", tagBg: "#f3f4f6" },
  };
  const p = palette[data.relation] || palette.neutral;

  return (
    <div className="relative" style={{ minWidth: 185, maxWidth: 250 }}>
      <div
        className="rounded-xl px-4 py-3.5 border-2 transition-shadow hover:shadow-lg"
        style={{ borderColor: p.border, backgroundColor: p.bg, boxShadow: `0 4px 16px ${p.border}18` }}
      >
        <div className="flex items-center gap-1.5 mb-2">
          <span
            className="flex items-center justify-center w-4 h-4 rounded-full text-[9px] font-bold"
            style={{ background: p.tagBg, color: p.text }}
          >
            {p.icon}
          </span>
          <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: p.text }}>
            {data.tag || data.relation?.toUpperCase() || "SOURCE"}
          </span>
        </div>
        <p className="text-xs font-medium leading-snug" style={{ color: p.text }}>{data.label}</p>
        {data.source && (
          <p className="mt-1.5 text-[10px] opacity-50 truncate" style={{ color: p.text }}>
            Source: {data.source}
          </p>
        )}
        {data.credibility != null && (
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: `${p.border}25` }}>
              <div className="h-full rounded-full" style={{ width: `${data.credibility}%`, background: p.border }} />
            </div>
            <span className="text-[9px] font-bold" style={{ color: p.text }}>{data.credibility}%</span>
          </div>
        )}
      </div>
      <Handle type="target" position={Position.Left}   className="!w-2 !h-2 !border-gray-300" style={{ background: p.border }} />
      <Handle type="source" position={Position.Right}  className="!w-2 !h-2 !border-gray-300" style={{ background: p.border }} />
      <Handle type="target" position={Position.Top}    id="top"    className="!w-2 !h-2 !border-gray-300" style={{ background: p.border }} />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!w-2 !h-2 !border-gray-300" style={{ background: p.border }} />
    </div>
  );
}

function EntityNode({ data }) {
  return (
    <div style={{ minWidth: 130 }}>
      <div
        className="rounded-lg px-3 py-2.5 border border-gray-200 bg-white hover:shadow-md transition-shadow"
        style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
      >
        <div className="flex items-center gap-1.5 mb-1">
          <span className="text-[11px]">{data.emoji || "🏷"}</span>
          <span className="text-[9px] font-bold tracking-widest uppercase text-gray-400">{data.tag || "ENTITY"}</span>
        </div>
        <p className="text-xs font-medium text-gray-700 leading-snug">{data.label}</p>
      </div>
      <Handle type="target" position={Position.Left}   className="!w-1.5 !h-1.5 !bg-gray-300 !border-gray-400" />
      <Handle type="source" position={Position.Right}  className="!w-1.5 !h-1.5 !bg-gray-300 !border-gray-400" />
      <Handle type="target" position={Position.Top}    id="top"    className="!w-1.5 !h-1.5 !bg-gray-300 !border-gray-400" />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!w-1.5 !h-1.5 !bg-gray-300 !border-gray-400" />
    </div>
  );
}

/* ─────────────────────────────────────────────────────
 *  Edge helpers
 * ─────────────────────────────────────────────────── */
const mkSupport = (id, source, target, label, opts = {}) => ({
  id, source, target, label,
  animated: true,
  style: { stroke: "#10b981", strokeWidth: 2 },
  labelStyle: { fontSize: 9, fontWeight: 700, letterSpacing: "0.08em", fill: "#059669" },
  labelBgStyle: { fill: "#ecfdf5", fillOpacity: 0.9 },
  labelBgPadding: [6, 3],
  labelBgBorderRadius: 6,
  markerEnd: { type: MarkerType.ArrowClosed, color: "#10b981", width: 16, height: 16 },
  ...opts,
});

const mkContra = (id, source, target, label, opts = {}) => ({
  id, source, target, label,
  style: { stroke: "#ef4444", strokeWidth: 2, strokeDasharray: "5 3" },
  labelStyle: { fontSize: 9, fontWeight: 700, letterSpacing: "0.08em", fill: "#dc2626" },
  labelBgStyle: { fill: "#fef2f2", fillOpacity: 0.9 },
  labelBgPadding: [6, 3],
  labelBgBorderRadius: 6,
  markerEnd: { type: MarkerType.ArrowClosed, color: "#ef4444", width: 16, height: 16 },
  ...opts,
});

const mkRef = (id, source, target, label, opts = {}) => ({
  id, source, target, label,
  style: { stroke: "#9ca3af", strokeWidth: 1, strokeDasharray: "3 3" },
  labelStyle: { fontSize: 8, fontWeight: 700, letterSpacing: "0.08em", fill: "#6b7280" },
  labelBgStyle: { fill: "#f9fafb", fillOpacity: 0.9 },
  labelBgPadding: [4, 2],
  labelBgBorderRadius: 4,
  markerEnd: { type: MarkerType.ArrowClosed, color: "#9ca3af", width: 12, height: 12 },
  ...opts,
});

/* ─────────────────────────────────────────────────────
 *  Mock Data
 * ─────────────────────────────────────────────────── */
const mockNodes = [
  { id: "claim-1", type: "claim", position: { x: 390, y: 155 },
    data: { label: "Earth is approximately spherical", tag: "PRIMARY CLAIM", confidence: 97,
            bg: "linear-gradient(135deg, #4f46e5, #7c3aed)", glowFrom: "#818cf8", glowTo: "#a78bfa" } },
  { id: "claim-2", type: "claim", position: { x: 390, y: 415 },
    data: { label: "Lunar eclipses show curved shadows", tag: "SUPPORTING CLAIM", confidence: 92,
            bg: "linear-gradient(135deg, #6366f1, #818cf8)" } },

  { id: "ev-1", type: "evidence", position: { x: 30,  y: 20  },
    data: { label: "Satellite imagery confirms spherical geometry",         tag: "DATASET",      relation: "supports",    source: "NASA",              credibility: 98 } },
  { id: "ev-2", type: "evidence", position: { x: 30,  y: 260 },
    data: { label: "Ships disappear hull-first over the horizon",           tag: "OBSERVATION",  relation: "supports",    source: "Marine Research",   credibility: 85 } },
  { id: "ev-3", type: "evidence", position: { x: 760, y: 20  },
    data: { label: "Gravity measurements show spherical mass distribution", tag: "PHYSICS",      relation: "supports",    source: "CERN",              credibility: 95 } },
  { id: "ev-5", type: "evidence", position: { x: 760, y: 170 },
    data: { label: "Atmospheric pressure gradients follow elevation",       tag: "METEOROLOGY",  relation: "supports",    source: "NOAA",              credibility: 88 } },
  { id: "ev-6", type: "evidence", position: { x: 30,  y: 540 },
    data: { label: "Star constellations shift predictably with latitude",   tag: "ASTRONOMY",    relation: "supports",    source: "Royal Observatory", credibility: 94 } },
  { id: "ev-4", type: "evidence", position: { x: 820, y: 450 },
    data: { label: "Perceived flat horizon on high-altitude balloon flights",tag: "DISPUTED",    relation: "contradicts", source: "Flat Earth Community", credibility: 8 } },

  { id: "ent-1", type: "entity", position: { x: 810, y: -65  }, data: { label: "NASA",         emoji: "🚀", tag: "AGENCY" } },
  { id: "ent-2", type: "entity", position: { x: -90, y: 360  }, data: { label: "Eratosthenes", emoji: "📐", tag: "HISTORICAL" } },
  { id: "ent-3", type: "entity", position: { x: 90,  y: -65  }, data: { label: "Aristotle",    emoji: "🏛",  tag: "HISTORICAL" } },
  { id: "ent-4", type: "entity", position: { x: 430, y: 585  }, data: { label: "ISS",          emoji: "🛸", tag: "FACILITY" } },
];

const mockEdges = [
  mkSupport("e-ev1-c1",  "ev-1",    "claim-1", "VERIFIED BY",  { targetHandle: "top" }),
  mkSupport("e-ev2-c1",  "ev-2",    "claim-1", "CONSISTENT"),
  mkSupport("e-ev3-c1",  "ev-3",    "claim-1", "EMPIRICAL",    { targetHandle: "top" }),
  mkSupport("e-ev5-c1",  "ev-5",    "claim-1", "SUPPORTS"),
  mkSupport("e-ev6-c2",  "ev-6",    "claim-2", "EVIDENTIARY"),
  mkSupport("e-c2-c1",   "claim-2", "claim-1", "SUB-ARGUMENT", {
    animated: false,
    style: { stroke: "#818cf8", strokeWidth: 2, strokeDasharray: "5 5" },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#818cf8", width: 14, height: 14 },
    labelStyle: { fontSize: 9, fontWeight: 700, letterSpacing: "0.08em", fill: "#6366f1" },
    labelBgStyle: { fill: "#eef2ff", fillOpacity: 0.9 },
  }),

  mkContra("e-ev4-c1",   "ev-4",  "claim-1", "CONTRADICTS"),
  mkContra("e-ev3-ev4",  "ev-3",  "ev-4",    "REFUTES",     { style: { stroke: "#ef4444", strokeWidth: 1.5, opacity: 0.55 } }),

  mkRef("e-ent1-ev1", "ent-1", "ev-1",    "PUBLISHED"),
  mkRef("e-ent1-ev3", "ent-1", "ev-3",    "CITED IN"),
  mkRef("e-ent2-ev2", "ent-2", "ev-2",    "PROPOSED"),
  mkRef("e-ent3-c2",  "ent-3", "claim-2"),
  mkRef("e-ent4-ev1", "ent-4", "ev-1",    "PLATFORM"),
];

import { createPortal } from "react-dom";

/* ─────────────────────────────────────────────────────
 *  Shared graph canvas
 * ─────────────────────────────────────────────────── */
function GraphCanvas({ nodes, edges, padding = 0.12, interactive = true }) {
  const nodeTypes = useMemo(() => ({
    claim:    ClaimNode,
    evidence: EvidenceNode,
    entity:   EntityNode,
  }), []);

  const onInit = useCallback((instance) => {
    setTimeout(() => instance.fitView({ padding }), 120);
  }, [padding]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onInit={onInit}
      fitView
      fitViewOptions={{ padding }}
      minZoom={0.2}
      maxZoom={2}
      nodesDraggable={interactive}
      nodesConnectable={interactive}
      elementsSelectable={interactive}
      panOnDrag={interactive}
      zoomOnScroll={interactive}
      zoomOnPinch={interactive}
      panOnScroll={false} // Always false to prevent scroll hijacking
      preventScrolling={interactive}
      proOptions={{ hideAttribution: true }}
      defaultEdgeOptions={{ type: "smoothstep" }}
    >
      <Background color="#e5e7eb" gap={24} size={1} />
      <Controls
        showInteractive={false}
        className={cn(
          "!bg-white/90 !backdrop-blur-sm !border-gray-200 !rounded-lg !shadow-md transition-opacity duration-300",
          !interactive && "opacity-0 pointer-events-none"
        )}
      />
    </ReactFlow>
  );
}

/* ─────────────────────────────────────────────────────
 *  Evidence Graph Component
 * ─────────────────────────────────────────────────── */
export default function EvidenceGraph({ nodes, edges }) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const graphNodes = nodes || mockNodes;
  const graphEdges = edges || mockEdges;

  const fullscreenUI = (
    <AnimatePresence>
      {isFullscreen && (
        <>
          {/* Blurred backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            onClick={() => setIsFullscreen(false)}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 9998,
              background: "rgba(0,0,0,0.4)",
              backdropFilter: "blur(14px)",
              WebkitBackdropFilter: "blur(14px)",
            }}
          />

          {/* Fullscreen graph panel */}
          <motion.div
            key="fullscreen"
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 9999,
              background: "#ffffff",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-6 py-4 flex-shrink-0"
              style={{ borderBottom: "1px solid rgba(0,0,0,0.06)", background: "#f9fafb" }}
            >
              <div className="flex items-center gap-3">
                <div className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-pulse" />
                <span className="text-sm font-bold tracking-widest uppercase text-gray-500">
                  Global Evidence Graph
                </span>
              </div>
              <button
                onClick={() => setIsFullscreen(false)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-gray-600 hover:text-gray-900 hover:bg-white transition-all duration-150 shadow-sm border border-gray-100"
                style={{ fontSize: 12 }}
              >
                <Minimize2 size={14} />
                <span className="font-bold uppercase tracking-wider">Close Analysis</span>
              </button>
            </div>

            {/* Graph fills remaining space */}
            <div className="flex-1 min-h-0 bg-white">
              <GraphCanvas nodes={graphNodes} edges={graphEdges} padding={0.04} interactive={true} />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );

  return (
    <>
      {/* ── Inline preview ── */}
      <div
        className="relative w-full rounded-xl overflow-hidden border border-gray-100"
        style={{ height: 420 }}
      >
        <GraphCanvas nodes={graphNodes} edges={graphEdges} interactive={false} />

        {/* Fullscreen button */}
        <button
          onClick={() => setIsFullscreen(true)}
          className="absolute top-3 right-3 z-10 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-gray-500 hover:text-gray-800 transition-all duration-200"
          style={{
            background: "rgba(255,255,255,0.85)",
            backdropFilter: "blur(8px)",
            border: "1px solid rgba(0,0,0,0.08)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
          }}
        >
          <Maximize2 size={13} />
          <span className="text-[10px] font-semibold tracking-wide">Fullscreen</span>
        </button>
      </div>

      {/* Render fullscreen portal at body level to escape parent transforms */}
      {typeof document !== "undefined" && createPortal(fullscreenUI, document.body)}
    </>
  );
}
