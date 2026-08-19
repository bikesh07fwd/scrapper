/**
 * src/components/common/EmptyState.jsx — Nice empty placeholder state.
 */

import React from "react";
import { HardDrive } from "lucide-react";
import Button from "./Button";

export default function EmptyState({
  title = "No data found",
  description = "No items match your criteria or none have been ingested yet.",
  actionText = null,
  onAction = null,
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-zinc-800 rounded-lg bg-surface/20">
      <div className="p-4 rounded-full bg-zinc-900 border border-zinc-850 text-neutral-400 mb-4">
        <HardDrive className="h-6 w-6" />
      </div>
      <h3 className="text-sm font-semibold text-neutral-100 mb-1">{title}</h3>
      <p className="text-xs text-neutral-400 max-w-sm mb-6 leading-relaxed">
        {description}
      </p>
      {actionText && onAction && (
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionText}
        </Button>
      )}
    </div>
  );
}
