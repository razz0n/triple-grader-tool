import React, { createContext, useContext, useState, useEffect } from "react";
import { AlertCircle, HelpCircle, Trash2 } from "lucide-react";

const DialogContext = createContext(null);

export function DialogProvider({ children }) {
  const [dialogState, setDialogState] = useState({
    isOpen: false,
    type: "alert", // "alert" | "confirm"
    title: "",
    message: "",
    confirmText: "OK",
    cancelText: "Cancel",
    resolve: null,
  });

  // Handle escape key to cancel or close dialog
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!dialogState.isOpen) return;
      if (e.key === "Escape") {
        handleCancel();
      } else if (e.key === "Enter") {
        handleConfirm();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [dialogState.isOpen, dialogState.resolve]);

  const showAlert = (message, title = "Notification") => {
    return new Promise((resolve) => {
      setDialogState({
        isOpen: true,
        type: "alert",
        title,
        message,
        confirmText: "OK",
        cancelText: "Cancel",
        resolve,
      });
    });
  };

  const showConfirm = (message, title = "Confirmation", confirmText = "Confirm", cancelText = "Cancel") => {
    return new Promise((resolve) => {
      setDialogState({
        isOpen: true,
        type: "confirm",
        title,
        message,
        confirmText,
        cancelText,
        resolve,
      });
    });
  };

  const handleConfirm = () => {
    if (dialogState.resolve) {
      dialogState.resolve(true);
    }
    setDialogState((prev) => ({ ...prev, isOpen: false, resolve: null }));
  };

  const handleCancel = () => {
    if (dialogState.resolve) {
      dialogState.resolve(false);
    }
    setDialogState((prev) => ({ ...prev, isOpen: false, resolve: null }));
  };

  const isDestructive =
    dialogState.type === "confirm" &&
    (/delete|remove|clear|undo/i.test(dialogState.message) ||
      /delete|remove|clear/i.test(dialogState.title) ||
      /delete|remove|clear/i.test(dialogState.confirmText));

  return (
    <DialogContext.Provider value={{ showAlert, showConfirm }}>
      {children}
      {dialogState.isOpen && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-md transition-opacity duration-200">
          {/* Modal Container */}
          <div className="w-full max-w-md bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border border-slate-200/80 dark:border-slate-800/80 rounded-2xl shadow-2xl p-6 relative flex flex-col gap-4 animate-in zoom-in-95 duration-200 text-slate-800 dark:text-slate-100">
            {/* Header Content */}
            <div className="flex items-start gap-4">
              <div
                className={`p-3 rounded-xl shrink-0 ${
                  isDestructive
                    ? "bg-rose-50 dark:bg-rose-950/40 text-rose-600 dark:text-rose-400 border border-rose-100/30 dark:border-rose-900/20"
                    : dialogState.type === "confirm"
                    ? "bg-amber-50 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400 border border-amber-100/30 dark:border-amber-900/20"
                    : "bg-indigo-50 dark:bg-indigo-950/40 text-indigo-600 dark:text-indigo-400 border border-indigo-100/30 dark:border-indigo-900/20"
                }`}
              >
                {isDestructive ? (
                  <Trash2 size={22} />
                ) : dialogState.type === "confirm" ? (
                  <HelpCircle size={22} />
                ) : (
                  <AlertCircle size={22} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-base font-extrabold text-slate-900 dark:text-white leading-tight">
                  {dialogState.title}
                </h3>
                <div className="text-xs text-slate-550 dark:text-slate-400 mt-2.5 font-medium leading-relaxed break-words whitespace-pre-wrap">
                  {dialogState.message}
                </div>
              </div>
            </div>

            {/* Actions Footer */}
            <div className="flex items-center gap-2 justify-end mt-2 pt-1">
              {dialogState.type === "confirm" && (
                <button
                  onClick={handleCancel}
                  className="px-4 py-2 text-xs font-bold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200/60 dark:border-slate-700/60 text-slate-700 dark:text-slate-300 rounded-xl transition-all cursor-pointer active:scale-95"
                >
                  {dialogState.cancelText}
                </button>
              )}
              <button
                onClick={handleConfirm}
                className={`px-4.5 py-2 text-xs font-bold text-white rounded-xl transition-all cursor-pointer active:scale-95 shadow-md ${
                  isDestructive
                    ? "bg-rose-600 hover:bg-rose-700 hover:shadow-rose-950/10"
                    : dialogState.type === "confirm"
                    ? "bg-amber-600 hover:bg-amber-700 hover:shadow-amber-950/10"
                    : "bg-indigo-650 hover:bg-indigo-700 hover:shadow-indigo-950/10"
                }`}
              >
                {dialogState.confirmText}
              </button>
            </div>
          </div>
        </div>
      )}
    </DialogContext.Provider>
  );
}

export function useDialog() {
  const context = useContext(DialogContext);
  if (!context) {
    throw new Error("useDialog must be used within a DialogProvider");
  }
  return context;
}
