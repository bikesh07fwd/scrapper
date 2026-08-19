/**
 * src/components/common/ErrorState.jsx — Nice state overlay for API disconnects.
 */

import React from "react";
import { AlertCircle, RotateCcw } from "lucide-react";
import Button from "./Button";

export default function ErrorState({
  title = "API Connection Failure",
  description = "The FastAPI backend server could not be reached. Please check that it is running on http://127.0.0.1:8000.",
  onRetry,
}) {
  return (
    <div className="flex flex-col items-center justify-center p-10 text-center border border-red-900/20 rounded-lg bg-red-950/5 max-w-lg mx-auto my-8">
      <div className="p-3.5 rounded-full bg-red-950/50 border border-red-900/40 text-red-400 mb-4 animate-pulse">
        <AlertCircle className="h-6 w-6" />
      </div>
      <h3 className="text-sm font-semibold text-neutral-100 mb-1">{title}</h3>
      <p className="text-xs text-neutral-400 leading-relaxed mb-6">
        {description}
      </p>
      {onRetry && (
        <Button
          variant="secondary"
          size="sm"
          onClick={onRetry}
          icon={<RotateCcw className="h-3.5 w-3.5" />}
        >
          Retry Connection
        </Button>
      )}
    </div>
  );
}
