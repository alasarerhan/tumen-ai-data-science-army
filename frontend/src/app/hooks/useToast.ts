import { toast } from "sonner";

export interface ToastApi {
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
}

function showToast(
  variant: "success" | "error" | "warning" | "info",
  title: string,
  description?: string,
): void {
  toast[variant](title, description ? { description } : undefined);
}

export function useToast(): ToastApi {
  return {
    success: (title, description) => showToast("success", title, description),
    error: (title, description) => showToast("error", title, description),
    warning: (title, description) => showToast("warning", title, description),
    info: (title, description) => showToast("info", title, description),
  };
}
