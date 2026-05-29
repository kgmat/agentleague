import { Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import AgentsPage from "./pages/AgentsPage";
import WorkflowsPage from "./pages/WorkflowsPage";
import BuilderPage from "./pages/BuilderPage";
import MonitorPage from "./pages/MonitorPage";
import RunDetailPage from "./pages/RunDetailPage";
import ChannelsPage from "./pages/ChannelsPage";
import SettingsPage from "./pages/SettingsPage";

const NAV = [
  { to: "/", label: "Dashboard", icon: "◧", end: true },
  { to: "/agents", label: "Agents", icon: "🤖", end: false },
  { to: "/workflows", label: "Workflows", icon: "🕸", end: false },
  { to: "/monitor", label: "Live Monitor", icon: "📡", end: false },
  { to: "/channels", label: "Channels", icon: "💬", end: false },
  { to: "/settings", label: "Settings", icon: "⚙", end: false },
];

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          Agent<span>League</span>
        </div>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
          >
            <span>{n.icon}</span> {n.label}
          </NavLink>
        ))}
        <div className="nav-spacer" />
        <div style={{ color: "var(--text-faint)", fontSize: 11, padding: "0 12px" }}>
          LangGraph · FastAPI · Ollama
        </div>
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
