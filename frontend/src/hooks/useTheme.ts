import { useSyncExternalStore } from "react";

export type ThemeMode = "light" | "dark" | "system";
type Resolved = "light" | "dark";

const KEY = "agentleague-theme";
const mq = () => window.matchMedia("(prefers-color-scheme: dark)");

export function getStoredMode(): ThemeMode {
  const v = localStorage.getItem(KEY);
  return v === "light" || v === "dark" || v === "system" ? v : "system";
}

export function resolveTheme(mode: ThemeMode): Resolved {
  return mode === "system" ? (mq().matches ? "dark" : "light") : mode;
}

/** Apply a mode to <html data-theme>. Safe to call before React mounts. */
export function applyTheme(mode: ThemeMode): void {
  document.documentElement.setAttribute("data-theme", resolveTheme(mode));
}

// --- Tiny shared store so every component reflects the same theme ---
let currentMode: ThemeMode = getStoredMode();
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());

export function setThemeMode(mode: ThemeMode): void {
  currentMode = mode;
  localStorage.setItem(KEY, mode);
  applyTheme(mode);
  emit();
}

// Re-resolve + notify when the OS preference changes while in "system" mode.
mq().addEventListener("change", () => {
  if (currentMode === "system") {
    applyTheme("system");
    emit();
  }
});

export function useTheme() {
  const mode = useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => currentMode,
  );
  return { mode, resolved: resolveTheme(mode), setMode: setThemeMode };
}
