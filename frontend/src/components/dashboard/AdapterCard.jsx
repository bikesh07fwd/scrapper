/**
 * src/components/dashboard/AdapterCard.jsx — Observability cards for adapter circuit states.
 */

import React from "react";
import { Zap, Play, HelpCircle, ShieldAlert } from "lucide-react";
import Badge from "../common/Badge";
import Button from "../common/Button";

export default function AdapterCard({ name, stats, onTrigger, isTriggering }) {
  const { state, consecutive_failures, last_success, last_failure } = stats || {
    state: "CLOSED",
    consecutive_failures: 0,
    last_success: null,
    last_failure: null,
  };

  const getCircuitBadge = () => {
    switch (state) {
      case "CLOSED":
        return <Badge variant="success">CLOSED / HEALTHY</Badge>;
      case "OPEN":
        return <Badge variant="error">OPEN / TRIPPED</Badge>;
      case "HALF_OPEN":
        return <Badge variant="warning">HALF_OPEN / PROBING</Badge>;
      default:
        return <Badge variant="neutral">{state}</Badge>;
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "Never";
    try {
      const date = new Date(dateStr);
      // Format as e.g. "12:34:56" or elapsed time
      return date.toLocaleTimeString();
    } catch {
      return "Invalid date";
    }
  };

  return (
    <div className={`p-5 rounded-lg border bg-surface/50 flex flex-col justify-between h-full border-zinc-800/50 hover:border-zinc-700/80 transition-all duration-200`}>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-sm font-bold tracking-wider font-mono uppercase text-neutral-100">{name}</h3>
            <p className="text-[10px] text-zinc-500 font-mono tracking-tight -mt-0.5">ADAPTER MODULE</p>
          </div>
          {getCircuitBadge()}
        </div>

        {/* Info Rows */}
        <div className="space-y-2 pt-2 border-t border-zinc-850">
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-500">FAILURE COUNT:</span>
            <span className={consecutive_failures > 0 ? "text-red-400 font-bold" : "text-neutral-300"}>
              {consecutive_failures} / 5
            </span>
          </div>

          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-500">LAST SUCCESS:</span>
            <span className="text-neutral-300">{formatDate(last_success)}</span>
          </div>

          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-500">LAST FAILURE:</span>
            <span className={last_failure ? "text-red-400" : "text-neutral-300"}>
              {formatDate(last_failure)}
            </span>
          </div>
        </div>

        {/* Warning if OPEN */}
        {state === "OPEN" && (
          <div className="flex items-start gap-2.5 p-3 rounded bg-red-950/20 border border-red-500/10 text-red-200/90 text-[11px] font-mono leading-relaxed">
            <ShieldAlert className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold text-red-300 uppercase leading-none">Circuit Block Active</p>
              <p className="text-neutral-400 mt-1">Simulated external connections are disabled. Outgoing queries are skipped.</p>
            </div>
          </div>
        )}
      </div>

      {/* Manual run button */}
      <div className="pt-5 border-t border-zinc-850 mt-4">
        {name === "remotive" ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={onTrigger}
            loading={isTriggering}
            icon={<Play className="h-3 w-3" />}
            className="w-full text-xs font-mono tracking-wider uppercase h-9"
          >
            Run Ingestion
          </Button>
        ) : (
          <div className="flex items-center gap-2 p-2 rounded bg-zinc-900/60 border border-zinc-850/60 text-[10px] text-zinc-500 font-mono">
            <HelpCircle className="h-4.5 w-4.5 text-zinc-500 shrink-0" />
            <span>Use the Resilience Lab to test sandbox circuit breaker triggers.</span>
          </div>
        )}
      </div>
    </div>
  );
}
