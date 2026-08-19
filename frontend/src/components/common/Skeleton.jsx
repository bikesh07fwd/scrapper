/**
 * src/components/common/Skeleton.jsx — Shimmer loader skeleton elements.
 */

import React from "react";

export function Skeleton({ className = "" }) {
  return (
    <div className={`bg-zinc-800/40 rounded animate-shimmer ${className}`} />
  );
}

export function MetricSkeleton() {
  return (
    <div className="bg-surface border border-zinc-800/50 p-5 rounded-lg space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-36" />
    </div>
  );
}

export function TableSkeleton({ cols = 5, rows = 5 }) {
  return (
    <div className="w-full space-y-4">
      {/* Header mock */}
      <div className="flex gap-4 border-b border-zinc-850 pb-3">
        {Array.from({ length: cols }).map((_, idx) => (
          <Skeleton key={idx} className="h-5 flex-1" />
        ))}
      </div>
      {/* Rows mock */}
      {Array.from({ length: rows }).map((_, rIdx) => (
        <div key={rIdx} className="flex gap-4 items-center py-2.5">
          {Array.from({ length: cols }).map((_, cIdx) => (
            <Skeleton key={cIdx} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function AdapterSkeleton() {
  return (
    <div className="bg-surface border border-zinc-800/50 p-5 rounded-lg space-y-4">
      <div className="flex justify-between items-center">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-16" />
      </div>
      <div className="space-y-2 pt-2">
        <div className="flex justify-between"><Skeleton className="h-3.5 w-28" /><Skeleton className="h-3.5 w-10" /></div>
        <div className="flex justify-between"><Skeleton className="h-3.5 w-24" /><Skeleton className="h-3.5 w-16" /></div>
        <div className="flex justify-between"><Skeleton className="h-3.5 w-24" /><Skeleton className="h-3.5 w-16" /></div>
      </div>
      <Skeleton className="h-9 w-full rounded" />
    </div>
  );
}
