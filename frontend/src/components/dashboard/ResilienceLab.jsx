/**
 * src/components/dashboard/ResilienceLab.jsx — Simulation and testing suite for circuit breaker state machine.
 */

import React, { useState } from "react";
import { Terminal, Shield, RefreshCw, Cpu, Activity, Play } from "lucide-react";
import Button from "../common/Button";
import Badge from "../common/Badge";
import { useToast } from "../common/Toast";

export default function ResilienceLab({ onSimulate, isSimulating, healthData }) {
  const { showToast } = useToast();
  const [selectedScenario, setSelectedScenario] = useState("happy_path");
  const [outcome, setOutcome] = useState(null);

  const scenarios = {
    happy_path: {
      label: "HAPPY PATH",
      desc: "Simulates a standard feed. Fetches 2 valid jobs. Pipeline succeeds and resets consecutive failure counters.",
      indicator: "success",
    },
    rate_limit: {
      label: "RATE LIMIT",
      desc: "Simulates source returning HTTP 429. Pipeline handles the rate limit, logs failures, and increments consecutive failures.",
      indicator: "warning",
    },
    server_error: {
      label: "SERVER ERROR",
      desc: "Simulates source returning HTTP 500. The fetcher retries, fails, and increments failure count towards opening the circuit.",
      indicator: "error",
    },
    timeout: {
      label: "CONNECTION TIMEOUT",
      desc: "Simulates network connection timeouts. Triggers retry exhaustions, logs failures, and increases circuit failure count.",
      indicator: "error",
    },
    empty: {
      label: "EMPTY FEED",
      desc: "Simulates feed containing 0 jobs. Pipeline successfully completes with 0 records without incrementing circuit failures.",
      indicator: "info",
    },
    malformed: {
      label: "MALFORMED RECORDS",
      desc: "Simulates feed containing partially malformed entries. Valid entries are ingested while malformed ones are safely skipped.",
      indicator: "info",
    },
    schema_changed: {
      label: "SCHEMA CHANGED",
      desc: "Simulates critical feed schema format change. Triggers fatal parsing failures, immediately tripping circuit breaker state.",
      indicator: "error",
    },
    duplicates: {
      label: "DUPLICATE RUN",
      desc: "Ingests the same data repeatedly. Telemetry verifies that records are processed but skipped at the database level by the deduplicator.",
      indicator: "info",
    },
  };

  const handleSimulate = async () => {
    showToast(`Running simulation: ${scenarios[selectedScenario].label}...`, "info");
    
    try {
      const result = await onSimulate({
        adapter: "sandbox",
        scenario: selectedScenario,
      });

      // Update outcome display
      setOutcome({
        scenario: selectedScenario,
        status: result.status,
        fetched: result.fetched_count,
        newJobs: result.new_count,
        duplicates: result.duplicate_count,
        errors: result.error_count,
        reason: result.reason || "None",
      });

      showToast(`Simulation complete: Ingestion run ${result.status.toUpperCase()}`, "success");
    } catch (err) {
      setOutcome({
        scenario: selectedScenario,
        status: "failed",
        fetched: 0,
        newJobs: 0,
        duplicates: 0,
        errors: 1,
        reason: err.message || "Request failed",
      });
      showToast(err.message || "Simulation execution failed.", "error");
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "success":
        return <Badge variant="success">SUCCESS</Badge>;
      case "failed":
        return <Badge variant="error">FAILED</Badge>;
      case "skipped":
        return <Badge variant="warning">SKIPPED</Badge>;
      default:
        return <Badge variant="neutral">{status.toUpperCase()}</Badge>;
    }
  };

  // Resolve current live circuit status of sandbox adapter
  const sandboxLiveState = healthData?.adapters?.sandbox?.state || "CLOSED";
  const sandboxConsecFailures = healthData?.adapters?.sandbox?.consecutive_failures || 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scenario Selection Column */}
        <div className="lg:col-span-2 p-5 rounded-lg border border-zinc-800/50 bg-surface/50 space-y-4">
          <div>
            <h3 className="text-sm font-bold tracking-wider font-mono uppercase text-neutral-100">Simulation Controls</h3>
            <p className="text-[10px] text-zinc-500 font-mono tracking-tight -mt-0.5">RESILIENCE TESTING LABORATORY</p>
          </div>

          <div className="space-y-4 pt-2 border-t border-zinc-850">
            {/* Grid selector of scenarios */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.keys(scenarios).map((key) => {
                const isSelected = selectedScenario === key;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setSelectedScenario(key)}
                    disabled={isSimulating}
                    className={`p-2.5 rounded border text-left flex flex-col justify-between h-20 transition-all duration-200 ${
                      isSelected
                        ? "bg-zinc-850 border-zinc-600 text-neutral-100 shadow-md shadow-zinc-950/20"
                        : "bg-zinc-900/40 border-zinc-800/50 text-zinc-400 hover:text-neutral-200 hover:border-zinc-700/60"
                    }`}
                  >
                    <span className="text-[10px] font-bold font-mono uppercase truncate w-full">
                      {scenarios[key].label}
                    </span>
                    <Badge variant={scenarios[key].indicator}>
                      {scenarios[key].indicator.toUpperCase()}
                    </Badge>
                  </button>
                );
              })}
            </div>

            {/* Scenario Description */}
            <div className="p-4 rounded-lg bg-zinc-900/60 border border-zinc-850/60 space-y-2">
              <h4 className="text-xs font-bold font-mono tracking-wide text-neutral-200">
                SCENARIO: {scenarios[selectedScenario].label}
              </h4>
              <p className="text-[11px] text-zinc-400 leading-relaxed font-mono">
                {scenarios[selectedScenario].desc}
              </p>
            </div>

            {/* Run Button */}
            <Button
              variant="primary"
              size="md"
              onClick={handleSimulate}
              disabled={isSimulating}
              loading={isSimulating}
              icon={<Play className="h-4 w-4" />}
              className="w-full text-xs font-mono tracking-wider uppercase h-10"
            >
              Simulate Ingestion Scenario
            </Button>
          </div>
        </div>

        {/* Live Simulation Outcomes Column */}
        <div className="p-5 rounded-lg border border-zinc-800/50 bg-surface/50 flex flex-col justify-between">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-bold tracking-wider font-mono uppercase text-neutral-100">Live Outcome Metrics</h3>
              <p className="text-[10px] text-zinc-500 font-mono tracking-tight -mt-0.5">TELEMETRY MONITORING</p>
            </div>

            <div className="space-y-3.5 pt-2 border-t border-zinc-850">
              {/* Live Sandbox Status */}
              <div className="flex justify-between items-center text-xs font-mono">
                <span className="text-zinc-500">SANDBOX STATE:</span>
                <span className={`font-bold ${
                  sandboxLiveState === "CLOSED" 
                    ? "text-emerald-400" 
                    : sandboxLiveState === "OPEN" 
                    ? "text-red-400 animate-pulse" 
                    : "text-amber-400"
                }`}>
                  {sandboxLiveState}
                </span>
              </div>
              <div className="flex justify-between items-center text-xs font-mono">
                <span className="text-zinc-500">FAILURES:</span>
                <span className={sandboxConsecFailures > 0 ? "text-red-400 font-bold" : "text-neutral-300"}>
                  {sandboxConsecFailures} / 5
                </span>
              </div>
            </div>

            {/* Outcome Console Log */}
            <div className="p-4 rounded border border-zinc-850 bg-zinc-950/80 min-h-[140px] font-mono text-[10px] text-zinc-400 space-y-2.5 flex flex-col justify-between">
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-zinc-500 border-b border-zinc-900 pb-1.5 mb-2">
                  <Terminal className="h-3.5 w-3.5" />
                  <span>SIMULATION CONSOLE</span>
                </div>
                {outcome ? (
                  <div className="space-y-1.5 leading-relaxed">
                    <div>
                      <span className="text-zinc-500">SCENARIO:</span>{" "}
                      <span className="text-zinc-300 font-bold uppercase">{scenarios[outcome.scenario].label}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500">PIPELINE:</span> {getStatusBadge(outcome.status)}
                    </div>
                    <div className="grid grid-cols-2 gap-1 mt-1 text-zinc-400">
                      <div><span className="text-zinc-500">FETCHED:</span> {outcome.fetched}</div>
                      <div><span className="text-zinc-500">NEW:</span> {outcome.newJobs}</div>
                      <div><span className="text-zinc-500">DUPES:</span> {outcome.duplicates}</div>
                      <div><span className="text-zinc-500">ERRORS:</span> {outcome.errors}</div>
                    </div>
                    <div className="pt-1.5 border-t border-zinc-900/60 leading-normal truncate w-full text-zinc-500">
                      <span className="text-zinc-600">REASON:</span> {outcome.reason}
                    </div>
                  </div>
                ) : (
                  <p className="text-zinc-650 italic text-center py-6">
                    No simulation records collected yet. Run a scenario to output telemetry logs.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
