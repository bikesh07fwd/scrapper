/**
 * src/components/layout/Header.jsx — Top header bar.
 */

import React, { useState, useEffect } from "react";
import { RefreshCw, Server } from "lucide-react";
import Button from "../common/Button";

export default function Header({ title, onRefresh, isFetching }) {
  const [secondsAgo, setSecondsAgo] = useState(0);

  // Update timer since last fetch
  useEffect(() => {
    setSecondsAgo(0);
    const interval = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [isFetching]);

  const getRefreshText = () => {
    if (isFetching) return "Refreshing...";
    if (secondsAgo === 0) return "Just now";
    return `${secondsAgo}s ago`;
  };

  return (
    <header className="h-16 px-8 border-b border-zinc-800/80 bg-surface/30 backdrop-blur-md flex items-center justify-between sticky top-0 z-30">
      {/* Title */}
      <div>
        <h2 className="text-sm font-semibold text-neutral-100 uppercase tracking-wider font-mono">{title}</h2>
      </div>

      {/* Stats and Refresh */}
      <div className="flex items-center gap-4">
        {/* Env badge */}
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-[10px] text-zinc-400 font-mono">
          <Server className="h-3 w-3 text-violet-400" />
          <span>ENVIRONMENT:</span>
          <span className="text-violet-300 font-bold">NEON CLOUD</span>
        </div>

        {/* Refresh button */}
        <div className="flex items-center gap-2.5">
          <span className="text-[10px] text-zinc-500 font-mono uppercase">
            Updated: {getRefreshText()}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            loading={isFetching}
            icon={<RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />}
            className="h-8 !px-2.5"
          />
        </div>
      </div>
    </header>
  );
}
