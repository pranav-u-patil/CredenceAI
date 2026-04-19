import React from "react";
import { GridPattern } from "../components/ui/grid-pattern";
import { Header } from "../components/ui/header";
import { cn } from "../lib/utils";

export default function Finance() {
  return (
    <div className="min-h-screen overflow-hidden bg-[#fdf6ee] text-stone-900">
      <Header />

      {/* Background gradients */}
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(251,146,60,0.15),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(234,179,8,0.12),_transparent_32%),linear-gradient(180deg,_rgba(255,255,255,0.8),_rgba(253,246,238,0.95))]" />

      <GridPattern
        squares={[[3, 3], [6, 1], [9, 2], [4, 4], [7, 6], [11, 10], [13, 14], [16, 9]]}
        className={cn(
          "[mask-image:radial-gradient(900px_circle_at_center,white,transparent)]",
          "inset-x-0 inset-y-[-30%] h-[200%] skew-y-12 opacity-30"
        )}
      />
    </div>
  );
}