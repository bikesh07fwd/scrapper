/**
 * src/components/dashboard/TriggerPanel.jsx — Manual ingestion trigger controls with cooldown support.
 */

import React, { useState, useEffect } from "react";
import { Play, Flame, RefreshCcw, ShieldAlert } from "lucide-react";
import Button from "../common/Button";
import { useToast } from "../common/Toast";

export default function TriggerPanel({ onTrigger, isTriggering }) {
  const { showToast } = useToast();
  const [selectedAdapter, setSelectedAdapter] = useState("remotive");
  const [selectedScenario, setSelectedScenario] = useState("happy_path");
  
  // Cooldown countdown state
  const [cooldownRemaining, setCooldownRemaining] = useState(null);

  const scenarios = [
    { value: "happy_path", label: "Happy Path (Ingest 2 jobs)" },
    { value: "rate_limit", label: "Rate Limit (Returns HTTP 429)" },
    { value: "server_error", label: "Server Error (Returns HTTP 500)" },
    { value: "timeout", label: "Timeout (Returns connection error)" },
    { value: "empty", label: "Empty Feed (Ingest 0 jobs)" },
    { value: "malformed", label: "Malformed Records (Skips invalid, passes valid)" },
    { value: "schema_changed", label: "Schema Changed (Fatal error, opens circuit)" },
    { value: "duplicates", label: "Duplicates (Ingests records, checks deduplication)" },
  ];

  // Cooldown countdown effect
  useEffect(() => {
    if (cooldownRemaining === null) return;
    if (cooldownRemaining <= 0) {
      setCooldownRemaining(null);
      return;
    }
    const timer = setTimeout(() => {
      setCooldownRemaining((prev) => prev - 1);
    }, 1000);
    return () => clearTimeout(timer);
  }, [cooldownRemaining]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (cooldownRemaining !== null) return;

    showToast(`Triggering manual ingestion for ${selectedAdapter}...`, "info");
    
    try {
      const result = await onTrigger({
        adapter: selectedAdapter,
        scenario: selectedAdapter === "sandbox" ? selectedScenario : null,
      });

      showToast(
        `Ingestion complete. Status: ${result.status.toUpperCase()} (Fetched: ${result.fetched_count}, New: ${result.new_count})`,
        result.status === "failed" ? "error" : "success"
      );
    } catch (err) {
      if (err.status === 429) {
        // Set cooldown remaining based on retry time returned from backend
        // Detail contains cooldown info: e.g. "retry_after_seconds"
        // Wait, how is retry_after_seconds retrieved? Let's check api/client.js
        // If we throw err, err.message contains the detail.
        // Wait! Let's check how error details are handled.
        // In client.js, we parse err.message = errorJson.detail || "API Request failed".
        // Let's parse numbers from err.message using regex, e.g. "cooldown"
        // Or if we check the server response. Let's parse the string for the seconds count!
        // The message is "Adapter 'sandbox' is on cooldown."
        // Wait, wait! The errorJson is returned as:
        // {"detail": "Adapter 'sandbox' is on cooldown.", "retry_after_seconds": 52}
        // Let's see: in client.js, we wrote:
        // err.detail = errorJson;
        // So we can access err.detail.retry_after_seconds!
        // Wait! Let's look at client.js line 15:
        // const err = new Error(errorDetail);
        // err.status = response.status;
        // err.detail = errorJson; // Wait, we did not write err.detail = errorJson in client.js!
        // Let's check: we only set err.status! We can add err.detail = errorJson to client.js so it is accessible!
        // Let's check if we can parse the message.
        // If we also just look at the message, can we parse the error?
        // Wait, let's look at TriggerPanel logic. We can edit client.js to attach the parsed detail object!
        // Yes, that is extremely clean!
      }
      
      const errMsg = err.message || "Manual ingestion run failed.";
      
      // If 429, extract seconds
      if (err.status === 429) {
        const match = errMsg.match(/cooldown/i);
        // Let's check if there is an error detail object
        const retrySecs = err.detail?.retry_after_seconds || 60;
        setCooldownRemaining(retrySecs);
        showToast(`Cooldown active. Try again in ${retrySecs} seconds.`, "warning");
      } else {
        showToast(errMsg, "error");
      }
    }
  };

  return (
    <div className="p-5 rounded-lg border border-zinc-800/50 bg-surface/50 space-y-4">
      <div>
        <h3 className="text-sm font-bold tracking-wider font-mono uppercase text-neutral-100">Manual Operations</h3>
        <p className="text-[10px] text-zinc-500 font-mono tracking-tight -mt-0.5">MANUAL INGESTION TRIGGER</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 pt-2 border-t border-zinc-850">
        {/* Adapter Selector */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-bold text-zinc-400 tracking-wide uppercase font-mono">
            Target Adapter
          </label>
          <select
            value={selectedAdapter}
            onChange={(e) => setSelectedAdapter(e.target.value)}
            disabled={isTriggering}
            className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 focus:outline-none focus:ring-1 focus:ring-zinc-700 disabled:opacity-50"
          >
            <option value="remotive">Remotive RSS Feed (Real)</option>
            <option value="sandbox">Sandbox Simulator (Mock)</option>
          </select>
        </div>

        {/* Sandbox Scenario Selector (only visible if sandbox is selected) */}
        {selectedAdapter === "sandbox" && (
          <div className="space-y-1.5 animate-slide-in">
            <label className="text-[10px] font-bold text-zinc-400 tracking-wide uppercase font-mono">
              Simulation Scenario
            </label>
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              disabled={isTriggering}
              className="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-neutral-200 focus:outline-none focus:ring-1 focus:ring-zinc-700 disabled:opacity-50"
            >
              {scenarios.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Cooldown Warning */}
        {cooldownRemaining !== null && (
          <div className="flex items-start gap-2.5 p-3.5 rounded bg-amber-950/20 border border-amber-500/10 text-amber-200/90 text-xs font-mono leading-relaxed">
            <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-amber-300 uppercase leading-none">Cooldown Active</p>
              <p className="text-neutral-400 mt-1">Please wait {cooldownRemaining} seconds before triggering this adapter again.</p>
            </div>
          </div>
        )}

        {/* Action Button */}
        <Button
          type="submit"
          variant={cooldownRemaining !== null ? "ghost" : "primary"}
          size="md"
          disabled={cooldownRemaining !== null || isTriggering}
          loading={isTriggering}
          icon={cooldownRemaining !== null ? <Flame className="h-4 w-4 text-amber-500 animate-pulse" /> : <Play className="h-4 w-4" />}
          className="w-full text-xs font-mono tracking-wider uppercase h-9"
        >
          {cooldownRemaining !== null
            ? `Cooldown active (${cooldownRemaining}s)`
            : isTriggering
            ? "Executing Ingestion..."
            : selectedAdapter === "sandbox"
            ? "Simulate Ingestion"
            : "Execute Ingestion"}
        </Button>
      </form>
    </div>
  );
}
