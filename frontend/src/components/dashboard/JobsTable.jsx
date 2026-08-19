/**
 * src/components/dashboard/JobsTable.jsx — Observability table for paginated Job listings.
 */

import React from "react";
import Badge from "../common/Badge";
import { ChevronLeft, ChevronRight, Globe2 } from "lucide-react";

export default function JobsTable({ jobsData, onRowClick, page, onPageChange, limit = 10 }) {
  const items = jobsData?.items || [];
  const total = jobsData?.total || 0;
  const totalPages = Math.ceil(total / limit) || 1;

  const formatDate = (isoString) => {
    if (!isoString) return "—";
    const date = new Date(isoString);
    return date.toLocaleDateString();
  };

  const getSourceBadge = (source) => {
    switch (source) {
      case "remotive":
        return <Badge variant="info">REMOTIVE</Badge>;
      case "sandbox":
        return <Badge variant="neutral">SANDBOX</Badge>;
      default:
        return <Badge variant="neutral">{source.toUpperCase()}</Badge>;
    }
  };

  return (
    <div className="bg-surface/30 border border-zinc-800/60 rounded-lg flex flex-col justify-between overflow-hidden">
      {/* Scrollable Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs font-mono">
          <thead>
            <tr className="bg-elevated/40 border-b border-zinc-800/80 text-zinc-400">
              <th className="p-3.5 font-semibold">TITLE</th>
              <th className="p-3.5 font-semibold">COMPANY</th>
              <th className="p-3.5 font-semibold">LOCATION</th>
              <th className="p-3.5 font-semibold">CATEGORY</th>
              <th className="p-3.5 font-semibold">PUBLISHED</th>
              <th className="p-3.5 font-semibold">SOURCE</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-850/60">
            {items.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-8 text-center text-zinc-500 font-mono">
                  No jobs found in database. Execute an ingestion run to ingest records.
                </td>
              </tr>
            ) : (
              items.map((job) => (
                <tr
                  key={job.id}
                  onClick={() => onRowClick(job)}
                  className="hover:bg-zinc-900/40 cursor-pointer transition-colors group"
                >
                  <td className="p-3.5 font-bold text-neutral-300 group-hover:text-neutral-100 max-w-xs truncate">
                    {job.title}
                  </td>
                  <td className="p-3.5 text-neutral-400 group-hover:text-neutral-100">
                    {job.company}
                  </td>
                  <td className="p-3.5 text-neutral-400 group-hover:text-neutral-100">
                    <span className="inline-flex items-center gap-1.5">
                      <Globe2 className="h-3 w-3 text-zinc-500 shrink-0" />
                      <span>{job.location || "Remote"}</span>
                    </span>
                  </td>
                  <td className="p-3.5 text-neutral-400 group-hover:text-neutral-100 uppercase">
                    {job.category}
                  </td>
                  <td className="p-3.5 text-zinc-500 font-semibold">
                    {formatDate(job.published_at)}
                  </td>
                  <td className="p-3.5">
                    {getSourceBadge(job.source || "remotive")}
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
            SHOWING JOBS {page * limit + 1} - {Math.min((page + 1) * limit, total)} OF {total}
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
