/**
 * src/components/common/Badge.jsx — Reusable semantic badges.
 */

import React from "react";

export default function Badge({ children, variant = "info" }) {
  const styles = {
    success: "bg-emerald-950/40 border-emerald-500/20 text-emerald-400",
    error: "bg-red-950/40 border-red-500/20 text-red-400",
    warning: "bg-amber-950/40 border-amber-500/20 text-amber-400",
    info: "bg-violet-950/40 border-violet-500/20 text-violet-400",
    neutral: "bg-zinc-800/40 border-zinc-700/20 text-zinc-400",
  }[variant] || "bg-zinc-800/40 border-zinc-700/20 text-zinc-400";

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono border ${styles}`}>
      {children}
    </span>
  );
}
