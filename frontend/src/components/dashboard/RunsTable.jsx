/**
 * src/components/dashboard/RunsTable.jsx — Observability table for past Ingestion Runs.
 */

import React from "react";
import Badge from "../common/Badge";
import { ChevronLeft, ChevronRight, Activity } from "lucide-react";

export default function RunsTable({ runsData, onRowClick, page, onPageChange, limit = 10 }) {
  const items = runsData?.items || [];
  const total = runsData?.total || 0;
  const totalPages = Math.ceil(total / limit) || 1;

  const getStatusBadge = (status) => {
    switch (status) {
      case "success":
        return <Badge variant="success">● SUCCESS</Badge>;
      case "failed":
        return <Badge variant="error">● FAILED</Badge>;
      case "skipped":
        return <Badge variant="warning">● SKIPPED</Badge>;
      case "partial":
        return <Badge variant="info">● PARTIAL</Badge>;
      default:
        return <Badge variant="neutral">{status.toUpperCase()}</Badge>;
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return "—";
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  const calculateDuration = (start, finish) => {
    if (!start || !finish) return "—";
    const elapsed = new Date(finish) - new Date(start);
    return `${(elapsed / 1000).toFixed(2)}s`;
  };

  return (
    <div className="bg-surface/30 border border-zinc-800/60 rounded-lg flex flex-col justify-between overflow-hidden">
      {/* Scrollable Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs font-mono">
          <thead>
            <tr className="bg-elevated/40 border-b border-zinc-800/80 text-zinc-400">
              <th className="p-3.5 font-semibold">TIME</th>
              <th className="p-3.5 font-semibold">ADAPTER</th>
              <th className="p-3.5 font-semibold">STATUS</th>
              <th className="p-3.5 font-semibold text-right">FETCHED</th>
              <th className="p-3.5 font-semibold text-right">NEW</th>
              <th className="p-3.5 font-semibold text-right">DUPLICATES</th>
              <th className="p-3.5 font-semibold text-right">ERRORS</th>
              <th className="p-3.5 font-semibold text-right">DURATION</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-850/60">
            {items.length === 0 ? (
              <tr>
                <td colSpan="8" className="p-8 text-center text-zinc-500">
                  No ingestion runs available. Run an ingestion to see telemetry.
                </td>
              </tr>
            ) : (
              items.map((run) => (
                <tr
                  key={run.run_id}
                  onClick={() => onRowClick(run)}
                  className="hover:bg-zinc-900/40 cursor-pointer transition-colors group"
                >
                  <td className="p-3.5 text-neutral-300 group-hover:text-neutral-100">
                    {formatTime(run.started_at)}
                  </td>
                  <td className="p-3.5 font-bold text-neutral-300 group-hover:text-neutral-100 uppercase">
                    {run.adapter}
                  </td>
                  <td className="p-3.5">
                    {getStatusBadge(run.status)}
                  </td>
                  <td className="p-3.5 text-right text-neutral-400 group-hover:text-neutral-100">
                    {run.fetched_count}
                  </td>
                  <td className="p-3.5 text-right text-emerald-400 font-semibold">
                    {run.new_count > 0 ? `+${run.new_count}` : "0"}
                  </td>
                  <td className="p-3.5 text-right text-neutral-400 group-hover:text-neutral-100">
                    {run.duplicate_count}
                  </td>
                  <td className={`p-3.5 text-right ${run.error_count > 0 ? "text-red-400 font-bold" : "text-neutral-400"}`}>
                    {run.error_count}
                  </td>
                  <td className="p-3.5 text-right text-zinc-500 font-semibold">
                    {calculateDuration(run.started_at, run.finished_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between p-3.5 bg-elevated/20 border-t border-zinc-800/80">
          <span className="text-[10px] text-zinc-500 font-mono">
            SHOWING RUNS {page * limit + 1} - {Math.min((page + 1) * limit, total)} OF {total}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page === 0}
              className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-850 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs text-zinc-400 font-mono px-2">
              PAGE {page + 1} OF {totalPages}
            </span>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages - 1}
              className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-850 disabled:opacity-30 disabled:hover:bg-transparent disabled:cursor-not-allowed transition-colors"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
