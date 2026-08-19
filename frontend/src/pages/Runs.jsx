/**
 * src/pages/Runs.jsx — Ingestion Runs Telemetry Explorer.
 */

import React, { useState } from "react";
import RunsTable from "../components/dashboard/RunsTable";
import EmptyState from "../components/common/EmptyState";
import { TableSkeleton } from "../components/common/Skeleton";
import { useRuns } from "../api/queries";

export default function Runs({ onRowClick }) {
  const [page, setPage] = useState(0);
  const limit = 10;
  
  const { data, isLoading, isError } = useRuns(limit, page * limit);

  const handlePageChange = (newPage) => {
    setPage(newPage);
  };

  if (isLoading) {
    return (
      <div className="bg-surface/50 border border-zinc-800/50 p-6 rounded-lg">
        <TableSkeleton cols={8} rows={8} />
      </div>
    );
  }

  const items = data?.items || [];

  return (
    <div className="space-y-4">
      {items.length === 0 ? (
        <EmptyState
          title="No ingestion runs recorded"
          description="Pipeline telemetry will collect run metadata, circuit breaker statuses, and transaction details here once triggered."
        />
      ) : (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400">
              Telemetry Log History ({data?.total || 0} Runs Recorded)
            </h3>
          </div>
          <RunsTable
            runsData={data}
            onRowClick={onRowClick}
            page={page}
            onPageChange={handlePageChange}
            limit={limit}
          />
        </div>
      )}
    </div>
  );
}
