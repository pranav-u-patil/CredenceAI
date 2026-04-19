import { cn } from "@/lib/utils";

/**
 * Purple gradient grid background — radial purple glow anchored to the right.
 */
export function GradientBlurBgPurple({ className, children }) {
  return (
    <div className={cn("min-h-screen w-full bg-white relative", className)}>
      <div
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `
            linear-gradient(to right, #f0f0f0 1px, transparent 1px),
            linear-gradient(to bottom, #f0f0f0 1px, transparent 1px),
            radial-gradient(circle 800px at 100% 200px, #d5c5ff, transparent)
          `,
          backgroundSize: "96px 64px, 96px 64px, 100% 100%",
        }}
      />
      {children}
    </div>
  );
}

/**
 * Top-fade grid background — fine grid that fades out from the top center.
 */
export function GradientBlurBgGrid({ className, children }) {
  return (
    <div className={cn("min-h-screen w-full bg-[#f8fafc] relative", className)}>
      <div
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `
            linear-gradient(to right, #e2e8f0 1px, transparent 1px),
            linear-gradient(to bottom, #e2e8f0 1px, transparent 1px)
          `,
          backgroundSize: "20px 30px",
          WebkitMaskImage:
            "radial-gradient(ellipse 70% 60% at 50% 0%, #000 60%, transparent 100%)",
          maskImage:
            "radial-gradient(ellipse 70% 60% at 50% 0%, #000 60%, transparent 100%)",
        }}
      />
      {children}
    </div>
  );
}
