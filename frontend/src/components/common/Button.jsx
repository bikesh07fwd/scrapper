/**
 * src/components/common/Button.jsx — Premium button component.
 */

import React from "react";
import { Loader2 } from "lucide-react";

export default function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  className = "",
  icon = null,
}) {
  const baseStyle = "inline-flex items-center justify-center font-medium rounded transition-all duration-200 focus:outline-none focus:ring-1 focus:ring-zinc-600 disabled:opacity-50 disabled:cursor-not-allowed";
  
  const variants = {
    primary: "bg-neutral-100 hover:bg-neutral-200 text-zinc-950",
    secondary: "bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700/50",
    ghost: "hover:bg-zinc-900 text-zinc-400 hover:text-zinc-100",
    danger: "bg-red-950/40 hover:bg-red-900/60 text-red-300 border border-red-800/40",
  }[variant] || "bg-neutral-100 hover:bg-neutral-200 text-zinc-950";

  const sizes = {
    sm: "px-2.5 py-1.5 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-base gap-2.5",
  }[size] || "px-4 py-2 text-sm gap-2";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`${baseStyle} ${variants} ${sizes} ${className}`}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin shrink-0" />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      <span>{children}</span>
    </button>
  );
}
