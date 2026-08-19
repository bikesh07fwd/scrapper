/**
 * src/components/dashboard/CircuitState.jsx — Stepper visual indicator for circuit breaker states.
 */

import React from "react";
import { CheckCircle2, ShieldAlert, RefreshCw, ArrowRight } from "lucide-react";

export default function CircuitState({ currentState }) {
  const states = [
    {
      id: "CLOSED",
      label: "CLOSED",
      description: "Healthy: Live feed queries enabled.",
      icon: <CheckCircle2 className="h-5 w-5" />,
      color: {
        active: "bg-emerald-500 text-zinc-950 border-emerald-400",
        inactive: "bg-zinc-900 border-zinc-800 text-zinc-600",
        line: "from-emerald-500/50",
      },
    },
    {
      id: "OPEN",
      label: "OPEN / TRIPPED",
      description: "Fault detected: Traffic blocked.",
      icon: <ShieldAlert className="h-5 w-5" />,
      color: {
        active: "bg-red-500 text-zinc-950 border-red-400",
        inactive: "bg-zinc-900 border-zinc-800 text-zinc-600",
        line: "to-red-500/50 from-red-500/50",
      },
    },
    {
      id: "HALF_OPEN",
      label: "HALF_OPEN",
      description: "Cooldown end: Probing for health.",
      icon: <RefreshCw className="h-5 w-5" />,
      color: {
        active: "bg-amber-500 text-zinc-950 border-amber-400",
        inactive: "bg-zinc-900 border-zinc-800 text-zinc-600",
        line: "to-amber-500/50",
      },
    },
  ];

  return (
    <div className="p-5 rounded-lg border border-zinc-800/50 bg-surface/50 space-y-4">
      <div>
        <h3 className="text-sm font-bold tracking-wider font-mono uppercase text-neutral-100">Circuit Control State</h3>
        <p className="text-[10px] text-zinc-500 font-mono tracking-tight -mt-0.5">RESILIENCE PIPELINE STATUS</p>
      </div>

      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-4 pt-3 border-t border-zinc-850">
        {states.map((state, idx) => {
          const isActive = currentState === state.id;
          const isLast = idx === states.length - 1;
          
          const iconStyle = isActive ? state.color.active : state.color.inactive;
          
          return (
            <React.Fragment key={state.id}>
              {/* State Step */}
              <div className={`flex items-start gap-3 p-3 rounded-lg border flex-1 transition-all duration-300 ${
                isActive 
                  ? "bg-zinc-800/40 border-zinc-700/60 shadow-md shadow-zinc-950/20" 
                  : "bg-zinc-900/10 border-transparent opacity-50"
              }`}>
                <div className={`p-2 rounded-md border shrink-0 transition-all duration-300 ${iconStyle}`}>
                  {state.icon}
                </div>
                <div>
                  <h4 className={`text-xs font-bold font-mono tracking-wide ${isActive ? "text-neutral-100" : "text-zinc-500"}`}>
                    {state.label}
                  </h4>
                  <p className="text-[10px] text-zinc-400 leading-relaxed mt-0.5">
                    {state.description}
                  </p>
                </div>
              </div>

              {/* Arrow separator (desktop-only) */}
              {!isLast && (
                <div className="hidden lg:flex items-center text-zinc-600 shrink-0">
                  <ArrowRight className="h-4 w-4" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
