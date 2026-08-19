/**
 * src/components/layout/Sidebar.jsx — Sidebar navigation.
 */

import React from "react";
import { LayoutDashboard, Briefcase, FileClock, ShieldAlert, Cpu, CheckCircle2, AlertOctagon } from "lucide-react";

export default function Sidebar({ currentView, onViewChange, healthData, isError }) {
  const links = [
    { id: "overview", label: "Overview", icon: <LayoutDashboard className="h-4 w-4" /> },
    { id: "jobs", label: "Ingested Jobs", icon: <Briefcase className="h-4 w-4" /> },
    { id: "runs", label: "Ingestion Runs", icon: <FileClock className="h-4 w-4" /> },
    { id: "lab", label: "Resilience Lab", icon: <ShieldAlert className="h-4 w-4" /> },
  ];

  const dbHealthy = healthData && healthData.database === "connected";
  const systemStatus = !isError && dbHealthy ? "operational" : "degraded";

  return (
    <aside className="w-64 bg-surface border-r border-zinc-800/80 flex flex-col justify-between shrink-0 h-screen sticky top-0">
      {/* Brand & Links */}
      <div className="flex flex-col">
        {/* Brand */}
        <div className="h-16 px-6 border-b border-zinc-800/80 flex items-center gap-2.5">
          <div className="h-6 w-6 rounded bg-neutral-100 flex items-center justify-center shrink-0">
            <Cpu className="h-3.5 w-3.5 text-zinc-950 font-bold" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-neutral-100 uppercase tracking-wider font-mono">ACYDON</h1>
            <p className="text-[10px] text-zinc-500 font-mono tracking-tight -mt-0.5">OBSERVABILITY ENGINE</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1">
          {links.map((link) => {
            const isActive = currentView === link.id;
            return (
              <button
                key={link.id}
                onClick={() => onViewChange(link.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-xs font-medium rounded transition-all duration-200 ${
                  isActive
                    ? "bg-zinc-800 text-neutral-100"
                    : "text-zinc-400 hover:text-neutral-100 hover:bg-zinc-900/60"
                }`}
              >
                {link.icon}
                <span>{link.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* System Status Indicators */}
      <div className="p-4 border-t border-zinc-800/80 space-y-3 bg-elevated/10">
        <div className="flex items-center gap-2">
          {systemStatus === "operational" ? (
            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          ) : (
            <AlertOctagon className="h-4 w-4 text-red-400 shrink-0" />
          )}
          <div>
            <p className="text-xs font-semibold text-neutral-200 capitalize leading-3">
              {systemStatus === "operational" ? "All Systems Go" : "System Degraded"}
            </p>
            <p className="text-[10px] text-zinc-500 font-mono">
              {systemStatus === "operational" ? "FastAPI live" : "Check server status"}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-1.5 pt-1">
          <div className="flex justify-between items-center text-[10px] font-mono">
            <span className="text-zinc-500">DATABASE</span>
            <span className={dbHealthy ? "text-emerald-400" : "text-red-400 font-bold"}>
              {dbHealthy ? "CONNECTED" : "DISCONNECTED"}
            </span>
          </div>
          <div className="flex justify-between items-center text-[10px] font-mono">
            <span className="text-zinc-500">SCHEDULER</span>
            <span className="text-emerald-400">RUNNING</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
