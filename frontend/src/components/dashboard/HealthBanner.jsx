/**
 * src/components/dashboard/HealthBanner.jsx — Overview System Status Banner.
 */

import React from "react";
import { ShieldCheck, ShieldAlert, CheckCircle, Database, Cpu, Activity } from "lucide-react";
import Badge from "../common/Badge";

export default function HealthBanner({ healthData, isError }) {
  const dbConnected = healthData && healthData.database === "connected";
  const allOperational = !isError && dbConnected;

  return (
    <div className={`p-4 rounded-lg border flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all duration-300 ${
      allOperational 
        ? "bg-emerald-950/20 border-emerald-500/25 text-emerald-200" 
        : "bg-red-950/20 border-red-500/25 text-red-200"
    }`}>
      {/* Title */}
      <div className="flex items-center gap-3">
        {allOperational ? (
          <div className="p-2 rounded-md bg-emerald-500/10 border border-emerald-500/20">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
          </div>
        ) : (
          <div className="p-2 rounded-md bg-red-500/10 border border-red-500/20">
            <ShieldAlert className="h-5 w-5 text-red-400 animate-pulse" />
          </div>
        )}
        <div>
          <h3 className="text-sm font-bold tracking-wide font-mono uppercase">
            {allOperational ? "ALL SYSTEMS OPERATIONAL" : "SYSTEM DEGRADED"}
          </h3>
          <p className="text-[11px] text-neutral-400 leading-none mt-1">
            {allOperational 
              ? "Observed services are fully healthy and operational." 
              : "Observability services are disrupted. Double check connections."}
          </p>
        </div>
      </div>

      {/* Badges Grid */}
      <div className="flex flex-wrap items-center gap-3 md:gap-5 text-xs font-mono">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-zinc-500" />
          <span className="text-zinc-500 uppercase">Database:</span>
          <Badge variant={dbConnected ? "success" : "error"}>
            {dbConnected ? "CONNECTED" : "DISCONNECTED"}
          </Badge>
        </div>

        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-zinc-500" />
          <span className="text-zinc-500 uppercase">Scheduler:</span>
          <Badge variant="success">ACTIVE</Badge>
        </div>

        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-zinc-500" />
          <span className="text-zinc-500 uppercase">Circuit Breaker:</span>
          <Badge variant="info">PERSISTED</Badge>
        </div>
      </div>
    </div>
  );
}
