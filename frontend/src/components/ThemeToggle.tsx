import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useTheme, type ThemeMode } from "../hooks/useTheme";

const OPTIONS: { mode: ThemeMode; label: string; icon: LucideIcon }[] = [
  { mode: "system", label: "System theme", icon: Monitor },
  { mode: "light", label: "Light theme", icon: Sun },
  { mode: "dark", label: "Dark theme", icon: Moon },
];

export default function ThemeToggle() {
  const { mode, setMode } = useTheme();
  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      {OPTIONS.map((o) => {
        const Icon = o.icon;
        return (
          <button
            key={o.mode}
            className={"tt-btn" + (mode === o.mode ? " active" : "")}
            title={o.label}
            aria-label={o.label}
            aria-pressed={mode === o.mode}
            onClick={() => setMode(o.mode)}
          >
            <Icon size={16} strokeWidth={2} />
          </button>
        );
      })}
    </div>
  );
}
