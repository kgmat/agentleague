import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AgentsPage from "./pages/AgentsPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import BuilderPage from "./pages/BuilderPage";
import MonitorPage from "./pages/MonitorPage";
import RunDetailPage from "./pages/RunDetailPage";
import ChannelsPage from "./pages/ChannelsPage";
import SettingsPage from "./pages/SettingsPage";
import ThemeToggle from "./components/ThemeToggle";
import {
  Activity,
  Bot,
  LayoutDashboard,
  MessageSquare,
  Settings as SettingsIcon,
  Workflow,
  type LucideIcon,
} from "lucide-react";

const NAV: { to: string; label: string; icon: LucideIcon; end: boolean }[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/agents", label: "Agents", icon: Bot, end: false },
  { to: "/workflows", label: "Workflows", icon: Workflow, end: false },
  { to: "/monitor", label: "Live Monitor", icon: Activity, end: false },
  { to: "/channels", label: "Channels", icon: MessageSquare, end: false },
  { to: "/settings", label: "Settings", icon: SettingsIcon, end: false },
];

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand-wrap">
          <img src="/banner.png" alt="AgentLeague" className="brand-banner" />
        </div>
        {NAV.map((n) => {
          const Icon = n.icon;
          return (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
            >
              <span className="nav-ico"><Icon size={18} strokeWidth={2} /></span> {n.label}
            </NavLink>
          );
        })}
        <div className="nav-spacer" />
        <ThemeToggle />
        <div className="nav-foot">LangGraph · FastAPI · Ollama</div>
      </aside>

      {/* The builder uses a full-bleed canvas, so it manages its own scrolling. */}
      <Routes>
        <Route path="/workflows/:id" element={<BuilderPage />} />
        <Route
          path="*"
          element={
            <main className="main">
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/agents" element={<AgentsPage />} />
                <Route path="/workflows" element={<WorkflowsPage />} />
                <Route path="/monitor" element={<MonitorPage />} />
                <Route path="/runs/:id" element={<RunDetailPage />} />
                <Route path="/channels" element={<ChannelsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Routes>
            </main>
          }
        />
      </Routes>
    </div>
  );
}
