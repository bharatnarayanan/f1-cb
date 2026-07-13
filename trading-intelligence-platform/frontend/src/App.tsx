import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchHealth } from "./api/client";
import { Dashboard } from "./pages/Dashboard";
import { PaperTrading } from "./pages/PaperTrading";
import { RecommendationDetail } from "./pages/RecommendationDetail";

type View = { name: "dashboard" } | { name: "detail"; id: string } | { name: "paper-trading" };

function App() {
  const [view, setView] = useState<View>({ name: "dashboard" });
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 60_000 });

  return (
    <div className="app-shell">
      <div className="top-nav">
        <span className="brand">TIP</span>
        <button className={view.name === "dashboard" ? "active" : ""} onClick={() => setView({ name: "dashboard" })}>
          Dashboard
        </button>
        <button
          className={view.name === "paper-trading" ? "active" : ""}
          onClick={() => setView({ name: "paper-trading" })}
        >
          Paper Trading
        </button>
        <div className="status-bar">
          {health && (
            <>
              <span className={`pill ${health.data_mode === "sample" ? "sample" : ""}`}>{health.data_mode}</span>
              <span>{health.status}</span>
            </>
          )}
        </div>
      </div>

      {view.name === "dashboard" && <Dashboard onSelect={(id) => setView({ name: "detail", id })} />}
      {view.name === "detail" && <RecommendationDetail id={view.id} onBack={() => setView({ name: "dashboard" })} />}
      {view.name === "paper-trading" && <PaperTrading />}
    </div>
  );
}

export default App;
