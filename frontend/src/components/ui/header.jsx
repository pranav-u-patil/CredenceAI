import React from "react";
import { useNavigate } from "react-router-dom";

/* ─── SVG Icons (inline for zero-dependency) ─────────────────────────── */

const TelegramIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
    <path
      d="M21.198 2.394a1.4 1.4 0 0 0-1.425-.147L3.32 8.959a1.4 1.4 0 0 0 .08 2.587l4.124 1.545 1.642 5.272a1.4 1.4 0 0 0 2.346.538l2.26-2.522 4.238 3.16a1.4 1.4 0 0 0 2.178-.82l3.16-15.2a1.4 1.4 0 0 0-.55-1.325Z"
      fill="currentColor"
    />
  </svg>
);

const DiscordIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
    <path
      d="M19.27 5.33a18.34 18.34 0 0 0-4.53-1.4.07.07 0 0 0-.07.03c-.2.35-.41.8-.56 1.15a16.92 16.92 0 0 0-5.08 0 11.4 11.4 0 0 0-.57-1.15.07.07 0 0 0-.07-.03 18.3 18.3 0 0 0-4.53 1.4.06.06 0 0 0-.03.02C1.35 9.18.63 12.9.98 16.58a.08.08 0 0 0 .03.05 18.44 18.44 0 0 0 5.55 2.8.07.07 0 0 0 .08-.03c.43-.58.81-1.2 1.14-1.84a.07.07 0 0 0-.04-.1 12.15 12.15 0 0 1-1.74-.83.07.07 0 0 1 0-.12c.12-.09.23-.18.34-.27a.07.07 0 0 1 .07-.01c3.65 1.67 7.6 1.67 11.21 0a.07.07 0 0 1 .08.01c.11.09.23.18.34.27a.07.07 0 0 1 0 .12c-.55.33-1.13.6-1.74.83a.07.07 0 0 0-.04.1c.34.65.72 1.26 1.14 1.84a.07.07 0 0 0 .08.03 18.39 18.39 0 0 0 5.56-2.8.08.08 0 0 0 .03-.05c.42-4.35-.7-8.12-2.97-11.47a.06.06 0 0 0-.03-.02ZM8.02 14.18c-.99 0-1.8-.91-1.8-2.03s.8-2.03 1.8-2.03 1.82.92 1.8 2.03c0 1.12-.8 2.03-1.8 2.03Zm6.66 0c-1 0-1.8-.91-1.8-2.03s.79-2.03 1.8-2.03 1.81.92 1.8 2.03c0 1.12-.8 2.03-1.8 2.03Z"
      fill="currentColor"
    />
  </svg>
);

const WhatsAppIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" className="h-[18px] w-[18px]">
    <path
      d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347Z"
      fill="currentColor"
    />
    <path
      d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2 22l4.983-1.41A9.96 9.96 0 0 0 12 22c5.523 0 10-4.477 10-10S17.523 2 12 2Zm0 18a7.96 7.96 0 0 1-4.29-1.248l-.307-.184-2.96.838.835-2.893-.2-.316A7.96 7.96 0 0 1 4 12c0-4.411 3.589-8 8-8s8 3.589 8 8-3.589 8-8 8Z"
      fill="currentColor"
    />
  </svg>
);

const FinanceIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
    <path d="M12 2L2 7l10 5 10-5-10-5Z" fill="currentColor" opacity="0.85" />
    <path d="M2 17l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="none" />
    <path d="M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" fill="none" />
  </svg>
);

/* ─── Icon Button ────────────────────────────────────────────────────── */

function IconButton({ children, glowColor, hoverBg, label, onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      className={`
        group relative flex h-9 w-9 items-center justify-center
        rounded-full border border-white/[0.12]
        bg-white/[0.06] backdrop-blur-md
        transition-all duration-300 ease-out
        hover:scale-110 hover:shadow-lg hover:border-white/20
        ${hoverBg}
        cursor-pointer
        active:scale-95
      `}
      style={{
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.08)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = `
          inset 0 1px 0 rgba(255,255,255,0.15),
          0 0 20px ${glowColor}40,
          0 4px 16px rgba(0,0,0,0.12)
        `;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.08)";
      }}
    >
      {children}
    </button>
  );
}

/* ─── Header ─────────────────────────────────────────────────────────── */

export function Header() {
  const navigate = useNavigate();

  return (
    <header
      className="fixed top-4 left-1/2 z-50 -translate-x-1/2"
      style={{ width: "min(960px, 92vw)" }}
    >
      {/* ── Ambient under-glow (antigravity illusion) ──────────────── */}
      <div
        className="pointer-events-none absolute -bottom-3 left-[8%] right-[8%] h-8 rounded-[50%]"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(139,92,246,0.12) 0%, rgba(6,182,212,0.06) 50%, transparent 80%)",
          filter: "blur(12px)",
        }}
      />

      {/* ── Glass bar ─────────────────────────────────────────────── */}
      <div
        className="
          relative flex h-[52px] items-center justify-between
          rounded-2xl px-5
          border border-white/[0.12]
        "
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.03) 100%)",
          backdropFilter: "blur(24px) saturate(1.5)",
          WebkitBackdropFilter: "blur(24px) saturate(1.5)",
          boxShadow: `
            0 1px 0 0 rgba(255,255,255,0.06) inset,
            0 -1px 0 0 rgba(0,0,0,0.04) inset,
            0 8px 32px -4px rgba(0,0,0,0.14),
            0 2px 8px -2px rgba(0,0,0,0.08)
          `,
        }}
      >
        {/* Inner top-edge highlight */}
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-px rounded-t-2xl"
          style={{
            background:
              "linear-gradient(90deg, transparent 5%, rgba(255,255,255,0.15) 40%, rgba(255,255,255,0.15) 60%, transparent 95%)",
          }}
        />

        {/* ── LEFT: Brand ─────────────────────────────────────────── */}
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 select-none cursor-pointer bg-transparent border-0 p-0"
        >
          <span
            className="text-lg font-bold tracking-wide"
            style={{
              background: "linear-gradient(135deg, #e2e8f0 0%, #94a3b8 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              textShadow: "0 0 24px rgba(148,163,184,0.15)",
            }}
          >
            CredenseAI
          </span>
        </button>

        {/* ── RIGHT: Action buttons ───────────────────────────────── */}
        <div className="flex items-center gap-2.5">
          {/* Telegram */}
          <IconButton
            label="Telegram"
            glowColor="#38bdf8"
            hoverBg="hover:bg-sky-500/[0.12]"
          >
            <span className="text-sky-400 transition-colors duration-200 group-hover:text-sky-300">
              <TelegramIcon />
            </span>
          </IconButton>

          {/* Discord */}
          <IconButton
            label="Discord"
            glowColor="#a78bfa"
            hoverBg="hover:bg-purple-500/[0.12]"
          >
            <span className="text-purple-400 transition-colors duration-200 group-hover:text-purple-300">
              <DiscordIcon />
            </span>
          </IconButton>

          {/* WhatsApp */}
          <IconButton
            label="WhatsApp"
            glowColor="#4ade80"
            hoverBg="hover:bg-emerald-500/[0.12]"
          >
            <span className="text-emerald-400 transition-colors duration-200 group-hover:text-emerald-300">
              <WhatsAppIcon />
            </span>
          </IconButton>

          {/* Divider */}
          <div className="mx-1 h-6 w-px bg-white/[0.08]" />

          {/* Finance — special pill CTA */}
          <button
            onClick={() => navigate("/finance")}
            className="
              group relative flex h-8 items-center gap-2
              rounded-full border border-amber-400/20
              bg-gradient-to-r from-amber-500/[0.12] to-orange-500/[0.08]
              px-4
              backdrop-blur-md
              transition-all duration-300 ease-out
              hover:scale-105 hover:border-amber-400/35
              hover:from-amber-500/[0.2] hover:to-orange-500/[0.15]
              cursor-pointer
              active:scale-95
            "
            style={{
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = `
                inset 0 1px 0 rgba(255,255,255,0.1),
                0 0 20px rgba(251,191,36,0.18),
                0 4px 14px rgba(0,0,0,0.1)
              `;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = "inset 0 1px 0 rgba(255,255,255,0.06)";
            }}
          >
            <span className="text-amber-400 transition-colors duration-200 group-hover:text-amber-300">
              <FinanceIcon />
            </span>
            <span className="text-[13px] font-semibold tracking-wide text-amber-300/90 transition-colors duration-200 group-hover:text-amber-200">
              Finance
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}
