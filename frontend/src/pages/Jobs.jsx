/**
 * src/pages/Jobs.jsx — Ingested Jobs History Explorer.
 */

import React, { useState } from "react";
import JobsTable from "../components/dashboard/JobsTable";
import EmptyState from "../components/common/EmptyState";
import { Skeleton, TableSkeleton } from "../components/common/Skeleton";
import { useJobs } from "../api/queries";

export default function Jobs({ onRowClick, onTrigger }) {
  const [page, setPage] = useState(0);
  const limit = 10;
  
  const { data, isLoading, isError, refetch } = useJobs(limit, page * limit);

  const handlePageChange = (newPage) => {
    setPage(newPage);
  };

  if (isLoading) {
    return (
      <div className="bg-surface/50 border border-zinc-800/50 p-6 rounded-lg">
        <TableSkeleton cols={6} rows={8} />
      </div>
    );
  }

  const items = data?.items || [];

  return (
    <div className="space-y-4">
      {items.length === 0 ? (
        <EmptyState
          title="No jobs found in database"
          description="Execute a job ingestion run from the dashboard to poll public feeds and save records."
          actionText="Go to Dashboard"
          onAction={() => window.location.reload()} // Just refresh/reload to shift view
        />
      ) : (
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400">
              Database Job Repository ({data?.total || 0} Ingested)
            </h3>
          </div>
          <JobsTable
            jobsData={data}
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
