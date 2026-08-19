/**
 * src/components/common/Toast.jsx — Toast notification system provider.
 */

import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle, AlertTriangle, XCircle, Info, X } from "lucide-react";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "info", duration = 4000) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type }]);
    
    setTimeout(() => {
      removeToast(id);
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast: addToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-md w-full sm:w-96">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onClose={() => removeToast(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}

function ToastItem({ toast, onClose }) {
  const { message, type } = toast;
  
  const styles = {
    success: {
      bg: "bg-emerald-950/80 border-emerald-500/30 text-emerald-200",
      icon: <CheckCircle className="h-5 w-5 text-emerald-400 shrink-0" />,
    },
    error: {
      bg: "bg-red-950/80 border-red-500/30 text-red-200",
      icon: <XCircle className="h-5 w-5 text-red-400 shrink-0" />,
    },
    warning: {
      bg: "bg-amber-950/80 border-amber-500/30 text-amber-200",
      icon: <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0" />,
    },
    info: {
      bg: "bg-zinc-900/90 border-zinc-700/50 text-zinc-200",
      icon: <Info className="h-5 w-5 text-zinc-400 shrink-0" />,
    },
  }[type] || {
    bg: "bg-zinc-900/90 border-zinc-700/50 text-zinc-200",
    icon: <Info className="h-5 w-5 text-zinc-400 shrink-0" />,
  };

  return (
    <div
      className={`flex items-start justify-between gap-3 p-3.5 rounded-lg border backdrop-blur-md shadow-xl transition-all duration-300 animate-slide-in ${styles.bg}`}
      role="alert"
    >
      <div className="flex items-start gap-2.5">
        {styles.icon}
        <p className="text-sm font-medium leading-5">{message}</p>
      </div>
      <button
        onClick={onClose}
        className="text-neutral-400 hover:text-neutral-200 p-0.5 rounded transition-colors"
        aria-label="Close notification"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
