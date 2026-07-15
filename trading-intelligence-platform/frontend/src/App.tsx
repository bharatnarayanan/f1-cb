import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { clearToken, getToken } from "./api/auth";
import { fetchHealth } from "./api/client";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";
import { PaperTrading } from "./pages/PaperTrading";
import { RecommendationDetail } from "./pages/RecommendationDetail";
import { SettingsScreen } from "./pages/SettingsScreen";
import { StrategyMarketplace } from "./pages/StrategyMarketplace";
import { TradeJournal } from "./pages/TradeJournal";

type View =
  | { name: "dashboard" }
  | { name: "detail"; id: string }
  | { name: "paper-trading" }
  | { name: "strategies" }
  | { name: "journal"; prefillRecommendationId?: string }
  | { name: "settings" };

function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });
  const [isAuthenticated, setIsAuthenticated] = useState(() => getToken() !== null);
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 60_000,
    enabled: isAuthenticated,
  });

  const navButton = (label: string, target: View, matches: (v: View) => boolean) => (
    <button className={matches(view) ? "active" : ""} onClick={() => setView(target)}>
      {label}
    </button>
  );

  const handleLogout = () => {
    clearToken();
    setIsAuthenticated(false);
  };

  if (!isAuthenticated) {
    return <Login onLoginSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="app-shell">
      <div className="top-nav">
        <span className="brand">TIP</span>
        {navButton("Dashboard", { name: "dashboard" }, (v) => v.name === "dashboard" || v.name === "detail")}
        {navButton("Paper Trading", { name: "paper-trading" }, (v) => v.name === "paper-trading")}
        {navButton("Strategies", { name: "strategies" }, (v) => v.name === "strategies")}
        {navButton("Journal", { name: "journal" }, (v) => v.name === "journal")}
        {navButton("Settings", { name: "settings" }, (v) => v.name === "settings")}
        <div className="status-bar">
          {health && (
            <>
              <span className={`pill ${health.data_mode === "sample" ? "sample" : ""}`}>{health.data_mode}</span>
              <span>{health.status}</span>
            </>
          )}
          <button onClick={handleLogout}>Logout</button>
        </div>
      </div>

      {view.name === "dashboard" && <Dashboard onSelect={(id) => setView({ name: "detail", id })} />}
      {view.name === "detail" && (
        <RecommendationDetail
          id={view.id}
          onBack={() => setView({ name: "dashboard" })}
          onLogOutcome={(id) => setView({ name: "journal", prefillRecommendationId: id })}
        />
      )}
      {view.name === "paper-trading" && <PaperTrading />}
      {view.name === "strategies" && <StrategyMarketplace />}
      {view.name === "journal" && <TradeJournal prefillRecommendationId={view.prefillRecommendationId} />}
      {view.name === "settings" && <SettingsScreen />}
    </div>
  );
}

export default App;
