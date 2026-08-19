/**
 * src/components/common/Drawer.jsx — Accessible sliding side drawer.
 */

import React, { useEffect } from "react";
import { X } from "lucide-react";

export default function Drawer({ isOpen, onClose, title, children }) {
  // Handle escape key to close drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Prevent background scrolling when open
  useEffect(() => {
    if (isOpen) {
      document.body.classList.add("overflow-hidden");
    } else {
      document.body.classList.remove("overflow-hidden");
    }
    return () => document.body.classList.remove("overflow-hidden");
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 animate-fade-in"
        onClick={onClose}
      />
      
      {/* Drawer Content */}
      <div className="relative w-full max-w-lg md:max-w-2xl h-full bg-surface border-l border-zinc-800/80 shadow-2xl flex flex-col z-50 transform transition-transform duration-300 animate-slide-left">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-zinc-800/80 bg-elevated/40">
          <h2 className="text-base font-semibold text-neutral-100">{title}</h2>
          <button
            onClick={onClose}
            className="p-1 rounded text-neutral-400 hover:text-neutral-200 hover:bg-zinc-800 transition-all duration-200"
            aria-label="Close details"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {children}
        </div>
      </div>
    </div>
  );
}
