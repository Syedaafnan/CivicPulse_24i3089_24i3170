import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { getConfig } from "./config";
import { DashboardPage } from "./pages/DashboardPage";
import { StatsPage } from "./pages/StatsPage";
import { SubmitPage } from "./pages/SubmitPage";

export function App() {
  const { environment } = getConfig();
  return (
    <>
      <header className="topbar">
        <span className="brand">CivicPulse</span>
        <nav>
          <NavLink to="/submit">Submit</NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/stats">Stats</NavLink>
        </nav>
        <span className="env" title="Runtime environment from /config.js">{environment}</span>
      </header>
      <main>
        {/* One boundary per view: a crash in Stats doesn't take down Submit. */}
        <Routes>
          <Route path="/" element={<Navigate to="/submit" replace />} />
          <Route path="/submit" element={<ErrorBoundary><SubmitPage /></ErrorBoundary>} />
          <Route path="/dashboard" element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
          <Route path="/stats" element={<ErrorBoundary><StatsPage /></ErrorBoundary>} />
          <Route path="*" element={<p className="card">Page not found.</p>} />
        </Routes>
      </main>
    </>
  );
}
