/**
 * src/pages/Dashboard.jsx — Overview Observability Dashboard.
 */

import React from "react";
import { Inbox, Activity, ShieldAlert, Cpu } from "lucide-react";
import HealthBanner from "../components/dashboard/HealthBanner";
import MetricCard from "../components/dashboard/MetricCard";
import AdapterCard from "../components/dashboard/AdapterCard";
import CircuitState from "../components/dashboard/CircuitState";
import TriggerPanel from "../components/dashboard/TriggerPanel";
import RunsTable from "../components/dashboard/RunsTable";
import JobsTable from "../components/dashboard/JobsTable";

export default function Dashboard({
  healthData,
  jobsData,
  runsData,
  isError,
  onTrigger,
  isTriggering,
  onRowClickRun,
  onRowClickJob,
  onTabChange,
}) {
  // Aggregate stats
  const totalJobs = jobsData?.total || 0;
  const totalRuns = runsData?.total || 0;
  
  // Calculate successful/failed runs
  const runsItems = runsData?.items || [];
  const successfulRuns = runsItems.filter((r) => r.status === "success").length;
  const failedRuns = runsItems.filter((r) => r.status === "failed").length;

  const sandboxState = healthData?.adapters?.sandbox?.state || "CLOSED";

  // Pre-slice top 5 for preview
  const recentRunsData = runsData ? { ...runsData, items: runsItems.slice(0, 5) } : null;
  const recentJobsData = jobsData ? { ...jobsData, items: (jobsData.items || []).slice(0, 5) } : null;

  return (
    <div className="space-y-6">
      {/* 1. System Health Status Banner */}
      <HealthBanner healthData={healthData} isError={isError} />

      {/* 2. Key Observability Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Ingested Jobs"
          value={totalJobs}
          icon={<Inbox className="h-4 w-4 text-violet-400" />}
          description="Cached in PostgreSQL storage"
          highlight={true}
        />
        <MetricCard
          title="Total Ingestion Runs"
          value={totalRuns}
          icon={<Activity className="h-4 w-4 text-emerald-400" />}
          description="Chronological pipeline executions"
        />
        <MetricCard
          title="Sandbox Circuit State"
          value={sandboxState}
          icon={<ShieldAlert className={`h-4 w-4 ${sandboxState === "CLOSED" ? "text-emerald-400" : "text-red-400 animate-pulse"}`} />}
          description={`Failures: ${healthData?.adapters?.sandbox?.consecutive_failures || 0} / 5`}
        />
        <MetricCard
          title="Ingestion Interval"
          value="30 Min"
          icon={<Cpu className="h-4 w-4 text-blue-400" />}
          description="Configured in backend scheduler"
        />
      </div>

      {/* 3. Circuit Breaker Control State Stepper */}
      <CircuitState currentState={sandboxState} />

      {/* 4. Adapters Health Observability Cards & Ingestion Trigger */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <AdapterCard
            name="remotive"
            stats={healthData?.adapters?.remotive}
            onTrigger={() => onTrigger({ adapter: "remotive" })}
            isTriggering={isTriggering}
          />
          <AdapterCard
            name="sandbox"
            stats={healthData?.adapters?.sandbox}
            onTrigger={() => onTrigger({ adapter: "sandbox", scenario: "happy_path" })}
            isTriggering={isTriggering}
          />
        </div>
        
        {/* Operations Trigger Panel */}
        <TriggerPanel onTrigger={onTrigger} isTriggering={isTriggering} />
      </div>

      {/* 5. Telemetry Previews (Top 5 Runs & Jobs) */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Recent Ingestion Runs */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400">
              Recent Telemetry Runs
            </h3>
            <button
              onClick={() => onTabChange("runs")}
              className="text-[10px] font-bold font-mono text-violet-400 hover:text-violet-300 uppercase tracking-tight"
            >
              View Full History →
            </button>
          </div>
          <RunsTable
            runsData={recentRunsData}
            onRowClick={onRowClickRun}
            page={0}
            onPageChange={() => {}}
            limit={5}
          />
        </div>

        {/* Recent Jobs */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-zinc-400">
              Recent Job Ingests
            </h3>
            <button
              onClick={() => onTabChange("jobs")}
              className="text-[10px] font-bold font-mono text-violet-400 hover:text-violet-300 uppercase tracking-tight"
            >
              View All Listings →
            </button>
          </div>
          <JobsTable
            jobsData={recentJobsData}
            onRowClick={onRowClickJob}
            page={0}
            onPageChange={() => {}}
            limit={5}
          />
        </div>
      </div>
    </div>
  );
}
