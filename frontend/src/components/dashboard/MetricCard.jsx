/**
 * src/components/dashboard/MetricCard.jsx — Premium metric display cards.
 */

import React from "react";

export default function MetricCard({ title, value, icon, description, highlight = false }) {
  return (
    <div className={`p-5 rounded-lg border bg-surface/50 transition-all duration-200 ${
      highlight 
        ? "border-violet-500/20 shadow-lg shadow-violet-950/5 bg-gradient-to-br from-surface to-violet-950/5" 
        : "border-zinc-800/50 hover:border-zinc-700/80"
    }`}>
      <div className="flex justify-between items-start">
        <span className="text-[10px] font-bold text-zinc-400 tracking-wider uppercase font-mono">
          {title}
        </span>
        {icon && <div className="text-zinc-500">{icon}</div>}
      </div>

      <div className="mt-2.5 flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono tracking-tight text-neutral-100">
          {value}
        </span>
      </div>

      {description && (
        <p className="text-[10px] text-zinc-500 mt-2 font-mono leading-none">
          {description}
        </p>
      )}
    </div>
  );
}
