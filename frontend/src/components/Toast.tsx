import { useEffect } from "react";
import styles from "./Toast.module.css";

export interface ToastState {
  message: string;
  kind: "success" | "error";
}

interface Props {
  toast: ToastState | null;
  onDismiss: () => void;
}

export function Toast({ toast, onDismiss }: Props) {
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(onDismiss, 3500);
    return () => clearTimeout(t);
  }, [toast, onDismiss]);

  if (!toast) return null;

  return (
    <div className={styles.toast} data-kind={toast.kind} role="status">
      <span className={styles.icon} aria-hidden>
        {toast.kind === "success" ? "✓" : "!"}
      </span>
      {toast.message}
    </div>
  );
}
