/**
 * src/App.jsx — Main Application Shell and layout structure.
 */

import React, { useState } from "react";
import { useHealth, useJobs, useRuns, useTriggerAdapter } from "./api/queries";
import Sidebar from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import Dashboard from "./pages/Dashboard";
import Jobs from "./pages/Jobs";
import Runs from "./pages/Runs";
import ResilienceLab from "./components/dashboard/ResilienceLab";
import Drawer from "./components/common/Drawer";
import Badge from "./components/common/Badge";
import ErrorState from "./components/common/ErrorState";
import { TableSkeleton } from "./components/common/Skeleton";
import { useToast } from "./components/common/Toast";
import { Globe2, Calendar, Link2, Key, HelpCircle, ServerCrash, Clock, AlertTriangle } from "lucide-react";

export default function App() {
  const { showToast } = useToast();
  const [currentView, setCurrentView] = useState("overview");
  
  // Drawer states
  const [selectedJob, setSelectedJob] = useState(null);
  const [selectedRun, setSelectedRun] = useState(null);

  // Queries
  const healthQuery = useHealth();
  const jobsQuery = useJobs(5, 0); // Limit 5 for preview card queries
  const runsQuery = useRuns(5, 0); // Limit 5 for preview card queries

  // Ingestion trigger mutation
  const triggerMutation = useTriggerAdapter();

  const handleRefresh = async () => {
    showToast("Refreshing latest telemetry data...", "info");
    await Promise.all([
      healthQuery.refetch(),
      jobsQuery.refetch(),
      runsQuery.refetch(),
    ]);
    showToast("Data refreshed.", "success");
  };

  const handleTrigger = async ({ adapter, scenario }) => {
    return triggerMutation.mutateAsync({ adapter, scenario });
  };

  const renderContent = () => {
    if (healthQuery.isError) {
      return (
        <ErrorState
          onRetry={() => {
            healthQuery.refetch();
            jobsQuery.refetch();
            runsQuery.refetch();
          }}
        />
      );
    }

    if (healthQuery.isLoading) {
      return (
        <div className="bg-surface/50 border border-zinc-800/50 p-6 rounded-lg space-y-6">
          <div className="h-6 bg-zinc-800/40 rounded animate-shimmer w-1/3" />
          <div className="grid grid-cols-4 gap-4">
            <div className="h-24 bg-zinc-800/40 rounded animate-shimmer" />
            <div className="h-24 bg-zinc-800/40 rounded animate-shimmer" />
            <div className="h-24 bg-zinc-800/40 rounded animate-shimmer" />
            <div className="h-24 bg-zinc-800/40 rounded animate-shimmer" />
          </div>
          <TableSkeleton cols={5} rows={6} />
        </div>
      );
    }

    switch (currentView) {
      case "overview":
        return (
          <Dashboard
            healthData={healthQuery.data}
            jobsData={jobsQuery.data}
            runsData={runsQuery.data}
            isError={healthQuery.isError}
            onTrigger={handleTrigger}
            isTriggering={triggerMutation.isPending}
            onRowClickRun={setSelectedRun}
            onRowClickJob={setSelectedJob}
            onTabChange={setCurrentView}
          />
        );
      case "jobs":
        return (
          <Jobs
            onRowClick={setSelectedJob}
            onTrigger={handleTrigger}
          />
        );
      case "runs":
        return (
          <Runs
            onRowClick={setSelectedRun}
          />
        );
      case "lab":
        return (
          <ResilienceLab
            onSimulate={handleTrigger}
            isSimulating={triggerMutation.isPending}
            healthData={healthQuery.data}
          />
        );
      default:
        return <div className="text-center font-mono text-zinc-500 py-12">Select navigation view.</div>;
    }
  };

  const getHeaderTitle = () => {
    switch (currentView) {
      case "overview":
        return "Telemetry Control Desk";
      case "jobs":
        return "Ingested Job Listings";
      case "runs":
        return "Ingestion Telemetry History";
      case "lab":
        return "Fault Resilience Lab";
      default:
        return "Dashboard";
    }
  };

  const isFetchingAny = healthQuery.isFetching || jobsQuery.isFetching || runsQuery.isFetching;

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar navigation */}
      <Sidebar
        currentView={currentView}
        onViewChange={setCurrentView}
        healthData={healthQuery.data}
        isError={healthQuery.isError}
      />

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header bar */}
        <Header
          title={getHeaderTitle()}
          onRefresh={handleRefresh}
          isFetching={isFetchingAny}
        />

        {/* Scrollable Workspace */}
        <main className="flex-1 overflow-y-auto p-8 max-w-7xl w-full mx-auto">
          {renderContent()}
        </main>
      </div>

      {/* Drawer: Job Details */}
      <Drawer
        isOpen={selectedJob !== null}
        onClose={() => setSelectedJob(null)}
        title="Job Metadata Telemetry"
      >
        {selectedJob && (
          <div className="space-y-6 font-mono text-xs text-neutral-300">
            {/* Header info */}
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-neutral-100 font-sans tracking-tight leading-snug">
                {selectedJob.title}
              </h3>
              <p className="text-sm font-semibold text-zinc-400">
                {selectedJob.company}
              </p>
              <div className="flex flex-wrap gap-2.5 pt-2">
                <span className="inline-flex items-center gap-1.5 text-zinc-400">
                  <Globe2 className="h-3.5 w-3.5" />
                  <span>{selectedJob.location || "Remote"}</span>
                </span>
                <span className="text-zinc-650">•</span>
                <span className="inline-flex items-center gap-1.5 text-zinc-400">
                  <Calendar className="h-3.5 w-3.5" />
                  <span>{new Date(selectedJob.published_at).toLocaleDateString()}</span>
                </span>
              </div>
            </div>

            {/* Tags and Category */}
            <div className="space-y-2 border-t border-zinc-850 pt-4">
              <span className="text-zinc-500 font-bold uppercase block text-[10px]">Metadata Parameters</span>
              <div className="flex flex-wrap gap-2 pt-1">
                <Badge variant="info">CATEGORY: {selectedJob.category.toUpperCase()}</Badge>
                {selectedJob.tags && selectedJob.tags.map((tag) => (
                  <Badge key={tag} variant="neutral">{tag}</Badge>
                ))}
              </div>
            </div>

            {/* Job Description */}
            <div className="space-y-2.5 border-t border-zinc-850 pt-4">
              <span className="text-zinc-500 font-bold uppercase block text-[10px]">Description</span>
              <div className="p-4 rounded border border-zinc-850 bg-zinc-900/30 leading-relaxed font-sans text-sm text-neutral-300 whitespace-pre-line">
                {selectedJob.description}
              </div>
            </div>

            {/* Connection URLs */}
            <div className="space-y-2 border-t border-zinc-850 pt-4">
              <span className="text-zinc-500 font-bold uppercase block text-[10px]">Ingestion Telemetry Details</span>
              <div className="space-y-2.5">
                <div className="flex justify-between items-center bg-zinc-900/60 p-2.5 rounded border border-zinc-850/60">
                  <span className="text-zinc-500 inline-flex items-center gap-1.5">
                    <Key className="h-3.5 w-3.5 shrink-0" />
                    <span>EXTERNAL ID:</span>
                  </span>
                  <span className="text-neutral-400 font-mono text-[10px] select-all">
                    {selectedJob.id}
                  </span>
                </div>
                {selectedJob.url && (
                  <a
                    href={selectedJob.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex justify-between items-center bg-zinc-900/60 p-2.5 rounded border border-zinc-850/60 hover:bg-zinc-850 transition-colors text-violet-400 hover:text-violet-300"
                  >
                    <span className="inline-flex items-center gap-1.5 font-bold uppercase">
                      <Link2 className="h-3.5 w-3.5 shrink-0" />
                      <span>Original Listing URL</span>
                    </span>
                    <span>→</span>
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </Drawer>

      {/* Drawer: Run Details */}
      <Drawer
        isOpen={selectedRun !== null}
        onClose={() => setSelectedRun(null)}
        title="Run Ingestion Telemetry"
      >
        {selectedRun && (
          <div className="space-y-6 font-mono text-xs text-neutral-300">
            {/* Header */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-zinc-500 uppercase font-bold text-[10px]">ADAPTER RUN:</span>
                <span className="text-neutral-100 font-bold uppercase">{selectedRun.adapter}</span>
              </div>
              <h3 className="text-sm font-bold text-neutral-400 leading-none select-all">
                ID: {selectedRun.run_id}
              </h3>
            </div>

            {/* Execution status parameters */}
            <div className="grid grid-cols-2 gap-4 border-t border-zinc-850 pt-4">
              <div className="p-3 bg-zinc-900/60 border border-zinc-850/60 rounded space-y-1">
                <span className="text-zinc-500 text-[10px] block">PIPELINE STATUS</span>
                <span className="font-bold text-neutral-200 uppercase">{selectedRun.status}</span>
              </div>
              <div className="p-3 bg-zinc-900/60 border border-zinc-850/60 rounded space-y-1">
                <span className="text-zinc-500 text-[10px] block">EXECUTION TIME</span>
                <span className="font-bold text-neutral-200">
                  {selectedRun.finished_at 
                    ? `${((new Date(selectedRun.finished_at) - new Date(selectedRun.started_at)) / 1000).toFixed(2)}s`
                    : "—"}
                </span>
              </div>
            </div>

            {/* Execution counts */}
            <div className="space-y-2 border-t border-zinc-850 pt-4">
              <span className="text-zinc-500 font-bold uppercase block text-[10px]">Ingested Counts Summary</span>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="p-2.5 bg-zinc-900/40 border border-zinc-850 rounded text-center">
                  <span className="text-zinc-500 block text-[9px]">FETCHED</span>
                  <span className="text-sm font-bold text-neutral-200">{selectedRun.fetched_count}</span>
                </div>
                <div className="p-2.5 bg-zinc-900/40 border border-zinc-850 rounded text-center">
                  <span className="text-zinc-500 block text-[9px]">PARSED</span>
                  <span className="text-sm font-bold text-neutral-200">{selectedRun.parsed_count}</span>
                </div>
                <div className="p-2.5 bg-zinc-900/40 border border-zinc-850 rounded text-center">
                  <span className="text-zinc-500 block text-[9px]">NEW JOBS</span>
                  <span className="text-sm font-bold text-emerald-400">+{selectedRun.new_count}</span>
                </div>
                <div className="p-2.5 bg-zinc-900/40 border border-zinc-850 rounded text-center">
                  <span className="text-zinc-500 block text-[9px]">DUPLICATES</span>
                  <span className="text-sm font-bold text-neutral-350">{selectedRun.duplicate_count}</span>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            <div className="space-y-2 border-t border-zinc-850 pt-4">
              <span className="text-zinc-500 font-bold uppercase block text-[10px]">Timing Metrics</span>
              <div className="space-y-2">
                <div className="flex justify-between items-center bg-zinc-900/60 p-2.5 rounded border border-zinc-850/60">
                  <span className="text-zinc-500 inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /><span>STARTED AT:</span></span>
                  <span className="text-neutral-300 font-semibold">{new Date(selectedRun.started_at).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center bg-zinc-900/60 p-2.5 rounded border border-zinc-850/60">
                  <span className="text-zinc-500 inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /><span>FINISHED AT:</span></span>
                  <span className="text-neutral-300 font-semibold">
                    {selectedRun.finished_at ? new Date(selectedRun.finished_at).toLocaleString() : "—"}
                  </span>
                </div>
              </div>
            </div>

            {/* Error logs */}
            {selectedRun.error_messages && selectedRun.error_messages.length > 0 && (
              <div className="space-y-2.5 border-t border-zinc-850 pt-4">
                <span className="text-red-400 font-bold uppercase block text-[10px] inline-flex items-center gap-1.5">
                  <AlertTriangle className="h-4 w-4 text-red-450" />
                  <span>Pipeline Failure Logs</span>
                </span>
                <div className="p-3.5 rounded border border-red-950/20 bg-red-950/5 text-red-300/90 font-mono whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto">
                  {selectedRun.error_messages.join("\n")}
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
